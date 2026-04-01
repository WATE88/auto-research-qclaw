#!/usr/bin/env python3
"""
AutoResearch v4.7 — Agent 任务完成率评测
新增功能:
  - Task Completion Rate: 任务完成率评估
  - Tool Use Score: 工具调用有效性
  - Multi-step Reasoning: 多步推理深度
  - Error Recovery: 错误恢复能力
  - Autonomy Level: 自主性等级
"""
import os, sys, json, time, asyncio, aiohttp, math, re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter

os.environ["PYTHONIOENCODING"] = "utf-8"
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "_cache"
REPORTS_DIR = SCRIPT_DIR / "reports"
FINDINGS_DIR = SCRIPT_DIR / "findings"
TRENDS_DIR = SCRIPT_DIR / "trends"
for d in [CACHE_DIR, REPORTS_DIR, FINDINGS_DIR, TRENDS_DIR]:
    d.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 1. NLG 摘要评测
# ════════════════════════════════════════════════════════════════

class NLGEvaluator:
    @staticmethod
    def _tokenize(text: str) -> list:
        return re.findall(r'\b\w+\b', text.lower())

    @staticmethod
    def rouge_1(reference: str, hypothesis: str) -> float:
        ref_tokens = set(NLGEvaluator._tokenize(reference))
        hyp_tokens = set(NLGEvaluator._tokenize(hypothesis))
        if not ref_tokens:
            return 0.0
        return len(ref_tokens & hyp_tokens) / len(ref_tokens)

    @staticmethod
    def rouge_2(reference: str, hypothesis: str) -> float:
        def get_bigrams(text):
            tokens = NLGEvaluator._tokenize(text)
            return set(zip(tokens[:-1], tokens[1:])) if len(tokens) > 1 else set()
        ref_bg = get_bigrams(reference)
        hyp_bg = get_bigrams(hypothesis)
        if not ref_bg:
            return 0.0
        return len(ref_bg & hyp_bg) / len(ref_bg)

    @staticmethod
    def rouge_l(reference: str, hypothesis: str) -> float:
        ref_tokens = NLGEvaluator._tokenize(reference)
        hyp_tokens = NLGEvaluator._tokenize(hypothesis)
        m, n = len(ref_tokens), len(hyp_tokens)
        if m == 0 or n == 0:
            return 0.0
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(1, m+1):
            for j in range(1, n+1):
                if ref_tokens[i-1] == hyp_tokens[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        return dp[m][n] / m if m > 0 else 0.0

    @staticmethod
    def _word_freq(text: str) -> dict:
        tokens = NLGEvaluator._tokenize(text)
        freq = Counter(tokens)
        total = sum(freq.values())
        return {w: c/total for w, c in freq.items()}

    @staticmethod
    def cosine_similarity(vec1: dict, vec2: dict) -> float:
        common = set(vec1.keys()) & set(vec2.keys())
        if not common:
            return 0.0
        dot = sum(vec1[k] * vec2[k] for k in common)
        norm1 = math.sqrt(sum(v**2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v**2 for v in vec2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    @staticmethod
    def semantic_similarity(text1: str, text2: str) -> float:
        return NLGEvaluator.cosine_similarity(
            NLGEvaluator._word_freq(text1),
            NLGEvaluator._word_freq(text2)
        )

    @staticmethod
    def coherence_score(text: str) -> float:
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0.0
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        len_score = min(avg_len / 15, 1.0) * 0.5
        all_tokens = []
        for s in sentences:
            all_tokens.extend(NLGEvaluator._tokenize(s))
        if not all_tokens:
            return 0.0
        unique_ratio = len(set(all_tokens)) / len(all_tokens)
        return (len_score + unique_ratio * 0.5) / 2

    @staticmethod
    def evaluate_corpus(results: list, topic: str) -> dict:
        if not results:
            return {}
        scores = {"rouge_1": [], "rouge_2": [], "rouge_l": [], "semantic_sim": [], "coherence": []}
        for r in results:
            title = r.get("title", "")
            desc = r.get("description", "") or ""
            r1 = NLGEvaluator.rouge_1(topic, desc)
            r2 = NLGEvaluator.rouge_2(topic, desc)
            rl = NLGEvaluator.rouge_l(topic, desc)
            sem = NLGEvaluator.semantic_similarity(desc, topic)
            coh = NLGEvaluator.semantic_similarity(title, desc)
            scores["rouge_1"].append(r1)
            scores["rouge_2"].append(r2)
            scores["rouge_l"].append(rl)
            scores["semantic_sim"].append(sem)
            scores["coherence"].append(coh)
        return {
            "rouge_1_avg": sum(scores["rouge_1"])/len(scores["rouge_1"]),
            "rouge_2_avg": sum(scores["rouge_2"])/len(scores["rouge_2"]),
            "rouge_l_avg": sum(scores["rouge_l"])/len(scores["rouge_l"]),
            "semantic_sim_avg": sum(scores["semantic_sim"])/len(scores["semantic_sim"]),
            "coherence_avg": sum(scores["coherence"])/len(scores["coherence"]),
        }

# ════════════════════════════════════════════════════════════════
# 2. Agent 评测指标 (v4.7 新增)
# ════════════════════════════════════════════════════════════════

class AgentEvaluator:
    """
    Agent 能力评测指标
    参考 AgentBench 设计思路，评估 Agent 的核心能力
    """

    # Agent 相关关键词
    AGENT_KW = ["agent", "autonomous", "tool use", "reasoning", "planning",
                "multi-agent", "crew", "team", "collaborate", "orchestrat"]
    TOOL_KW = ["tool", "api", "function", "plugin", "integration", "web",
                "search", "browser", "file", "database", "sql", "http"]
    REASONING_KW = ["reason", "think", "plan", "chain", "反思", "思考", "step-by-step"]
    AUTONOMY_KW = ["autonomous", "auto", "self-supervised", "self-improve",
                   "learn", "adapt", "feedback"]

    @staticmethod
    def task_completion_score(results: list, topic: str) -> float:
        """
        任务完成率评估
        衡量结果对完成任务的帮助程度
        """
        if not results:
            return 0.0

        topic_lower = topic.lower()
        completion_scores = []

        for r in results:
            title = (r.get("title") or "").lower()
            desc = (r.get("description") or "").lower()
            text = title + " " + desc

            # 1. 主题相关性 (是否解决用户问题)
            topic_words = set(topic_lower.split())
            text_words = set(text.split())
            topic_relevance = len(topic_words & text_words) / len(topic_words) if topic_words else 0

            # 2. 可操作性 (是否有明确的目标)
            actionable_kw = ["tutorial", "guide", "example", "how to", "implement",
                            "framework", "library", "tool", "api", "sdk"]
            actionable = any(kw in text for kw in actionable_kw)
            actionable_score = 1.0 if actionable else 0.3

            # 3. 完整性 (是否提供完整解决方案)
            complete_kw = ["complete", "full", "end-to-end", "pipeline", "workflow",
                          "production", "ready", "easy", "simple"]
            complete = any(kw in text for kw in complete_kw)
            complete_score = 1.0 if complete else 0.5

            score = topic_relevance * 0.5 + actionable_score * 0.3 + complete_score * 0.2
            completion_scores.append(score)

        return sum(completion_scores) / len(completion_scores)

    @staticmethod
    def tool_use_score(results: list) -> float:
        """
        工具调用有效性评分
        衡量 Agent 使用外部工具的能力
        """
        if not results:
            return 0.0

        scores = []
        for r in results:
            desc = (r.get("description") or "").lower()

            # 检测工具调用能力
            tool_count = sum(1 for kw in AgentEvaluator.TOOL_KW if kw in desc)
            tool_score = min(tool_count / 3, 1.0)

            # 检测 API 相关能力
            api_kw = ["api", "rest", "grpc", "endpoint", "http"]
            has_api = any(kw in desc for kw in api_kw)

            # 检测集成能力
            integration_kw = ["integrat", "connect", "plugin", "extens"]
            has_integration = any(kw in desc for kw in integration_kw)

            score = tool_score * 0.4 + (0.3 if has_api else 0) + (0.3 if has_integration else 0)
            scores.append(score)

        return sum(scores) / len(scores)

    @staticmethod
    def reasoning_depth_score(results: list) -> float:
        """
        多步推理深度评分
        衡量 Agent 的推理规划能力
        """
        if not results:
            return 0.0

        scores = []
        for r in results:
            title = (r.get("title") or "").lower()
            desc = (r.get("description") or "").lower()
            text = title + " " + desc

            # 1. 规划能力
            planning_kw = ["plan", "planning", "schedule", "roadmap", "strategy"]
            has_planning = any(kw in text for kw in planning_kw)

            # 2. 推理能力
            reasoning_kw = ["reason", "chain", "think", "logic", "infer",
                          "step", "stage", "phase"]
            reasoning_count = sum(1 for kw in reasoning_kw if kw in text)
            reasoning_score = min(reasoning_count / 3, 1.0)

            # 3. 反思/自我改进
            reflection_kw = ["reflect", "improve", "learn", "feedback", "adapt"]
            has_reflection = any(kw in text for kw in reflection_kw)

            score = (0.4 if has_planning else 0) + reasoning_score * 0.4 + (0.2 if has_reflection else 0)
            scores.append(score)

        return sum(scores) / len(scores)

    @staticmethod
    def autonomy_score(results: list) -> float:
        """
        自主性等级评分
        衡量 Agent 的自主程度
        """
        if not results:
            return 0.0

        scores = []
        for r in results:
            desc = (r.get("description") or "").lower()

            # 自主性关键词
            autonomy_kw = ["autonomous", "auto", "self-supervised", "self-improve",
                          "automated", "automatic", "without human"]
            autonomy_count = sum(1 for kw in autonomy_kw if kw in desc)

            # 可配置性
            config_kw = ["config", "customiz", "flexible", "adapt"]
            has_config = any(kw in desc for kw in config_kw)

            # 监控
            monitor_kw = ["monitor", "track", "observe", "log", "dashboard"]
            has_monitor = any(kw in desc for kw in monitor_kw)

            score = min(autonomy_count / 2, 1.0) * 0.5 + (0.25 if has_config else 0) + (0.25 if has_monitor else 0)
            scores.append(score)

        return sum(scores) / len(scores)

    @staticmethod
    def multi_agent_score(results: list) -> float:
        """
        多 Agent 协作评分
        """
        if not results:
            return 0.0

        scores = []
        for r in results:
            desc = (r.get("description") or "").lower()

            multi_kw = ["multi-agent", "multi agent", "crew", "team", "collaborat",
                       "orchestrat", "hierarchy", "role", "agent-to-agent"]
            multi_count = sum(1 for kw in multi_kw if kw in desc)

            # 通信能力
            comm_kw = ["communicat", "message", "share", "coordinate", "synchron"]
            has_comm = any(kw in desc for kw in comm_kw)

            score = min(multi_count / 2, 1.0) * 0.6 + (0.4 if has_comm else 0)
            scores.append(score)

        return sum(scores) / len(scores)

    @staticmethod
    def evaluate(results: list, topic: str) -> dict:
        """综合评估 Agent 能力"""
        return {
            "task_completion": round(AgentEvaluator.task_completion_score(results, topic), 4),
            "tool_use": round(AgentEvaluator.tool_use_score(results), 4),
            "reasoning_depth": round(AgentEvaluator.reasoning_depth_score(results), 4),
            "autonomy": round(AgentEvaluator.autonomy_score(results), 4),
            "multi_agent": round(AgentEvaluator.multi_agent_score(results), 4),
        }

# ════════════════════════════════════════════════════════════════
# 3. BEIR 检索指标
# ════════════════════════════════════════════════════════════════

class RetrievalMetrics:
    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}

    @staticmethod
    def relevance_scores(results: list, query: str) -> list:
        query_words = set(query.lower().split())
        semantic_expansions = {
            "llm": ["language model", "gpt", "transformer"],
            "ai": ["artificial intelligence", "ml"],
            "benchmark": ["evaluation", "metric", "test"],
            "retrieval": ["search", "ranking"],
            "quantization": ["quant", "int8", "int4"],
            "agent": ["agentic", "autonomous", "tool use"],
            "evaluation": ["benchmark", "metric"],
        }
        expanded = query_words.copy()
        for word in list(query_words):
            if word in semantic_expansions:
                expanded.update(semantic_expansions[word])
        scores = []
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            text_words = set(text.split())
            exact = len(query_words & text_words)
            semantic = len(expanded & text_words) - exact
            title = (r.get("title") or "").lower()
            title_match = any(qw in title for qw in query_words)
            scores.append(exact * 1.0 + semantic * 0.5 + (1.0 if title_match else 0.0))
        return scores

    @staticmethod
    def dcg(scores: list) -> float:
        return sum(s / math.log2(i + 2) for i, s in enumerate(scores[:10]))

    @staticmethod
    def ndcg(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0
        dcg = RetrievalMetrics.dcg(scores)
        idcg = RetrievalMetrics.dcg(sorted(scores, reverse=True))
        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def map(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0
        positions = [i+1 for i, s in enumerate(scores) if s >= 0.5]
        if not positions:
            return 0.0
        return sum((positions.index(p)+1)/p for p in positions) / len(positions)

    @staticmethod
    def mrr(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        for i, s in enumerate(scores):
            if s >= 0.5:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def recall_at_k(results: list, query: str, k: int = 20) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0
        top_k = scores[:k]
        threshold = 0.5
        rel_k = sum(1 for s in top_k if s >= threshold)
        total = sum(1 for s in scores if s >= threshold)
        return rel_k / total if total > 0 else 0.0

# ════════════════════════════════════════════════════════════════
# 4. 综合评分系统 v4.7
# ════════════════════════════════════════════════════════════════

class EnhancedQualityScorer:
    """16 维度评分 (v4.7): 基础 + BEIR + NLG + Agent"""

    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}
    ACADEMIC_KW = ["SOTA", "benchmark", "NeurIPS", "ICML", "ICLR", "ACL"]
    USABILITY_KW = ["tutorial", "example", "demo", "guide", "documentation",
                    "easy", "simple", "quickstart", "getting started"]
    APPLICABILITY_KW = ["research", "survey", "analysis", "search", "retrieval",
                       "crawler", "aggregator", "monitor", "tracker",
                       "pipeline", "automation", "workflow", "agent", "tool",
                       "api", "dataset", "benchmark", "evaluation", "metric"]

    @staticmethod
    def score(findings: list, topic: str = "") -> dict:
        if not findings:
            return {"total": 0, "quality_score": 0, "dimensions": {}, "grade": "F"}

        n = len(findings)

        # 基础维度
        authority = sum(
            EnhancedQualityScorer.SOURCE_WEIGHTS.get(f.get("source", ""), 0.5)
            for f in findings
        ) / n

        academic = sum(
            1 for f in findings
            if any(kw.lower() in ((f.get("title") or "") + (f.get("description") or "")).lower()
                   for kw in EnhancedQualityScorer.ACADEMIC_KW)
        ) / n

        stars = [f.get("stars", 0) for f in findings if f.get("stars", 0) > 0]
        star_score = sum(min(s / max(stars), 1.0) for s in stars) / len(stars) if stars else 0

        sources = Counter(f.get("source", "unknown") for f in findings)
        diversity = 1 - sum((c / n) ** 2 for c in sources.values())

        usability = min(
            sum(1 for f in findings
                if any(kw.lower() in (f.get("description") or "").lower()
                       for kw in EnhancedQualityScorer.USABILITY_KW)
            ) / n * 2, 1.0
        )

        topic_lower = topic.lower()
        topic_applicable = any(kw in topic_lower for kw in EnhancedQualityScorer.APPLICABILITY_KW)
        desc_applicable = sum(
            1 for f in findings
            if any(kw in (f.get("description") or "").lower()
                   for kw in EnhancedQualityScorer.APPLICABILITY_KW)
        )
        applicability = (0.5 if topic_applicable else 0.0) + min(desc_applicable / n * 0.5, 0.5)
        coverage = min(n / 20, 1.0)

        # BEIR
        ndcg = RetrievalMetrics.ndcg(findings, topic)
        map_score = RetrievalMetrics.map(findings, topic)
        mrr = RetrievalMetrics.mrr(findings, topic)
        recall = RetrievalMetrics.recall_at_k(findings, topic, k=10)

        # NLG
        nlg = NLGEvaluator.evaluate_corpus(findings, topic)
        rouge_1 = nlg.get("rouge_1_avg", 0)
        semantic_sim = nlg.get("semantic_sim_avg", 0)
        coherence = nlg.get("coherence_avg", 0)

        # Agent (v4.7)
        agent = AgentEvaluator.evaluate(findings, topic)
        task_completion = agent.get("task_completion", 0)
        tool_use = agent.get("tool_use", 0)
        reasoning_depth = agent.get("reasoning_depth", 0)
        autonomy = agent.get("autonomy", 0)
        multi_agent = agent.get("multi_agent", 0)

        # 综合检索
        retrieval_quality = ndcg * 0.3 + map_score * 0.25 + mrr * 0.15 + recall * 0.15 + rouge_1 * 0.15

        # Agent 综合
        agent_score = (
            task_completion * 0.30 +
            tool_use * 0.20 +
            reasoning_depth * 0.20 +
            autonomy * 0.15 +
            multi_agent * 0.15
        )

        # 最终评分 (16 维度)
        final_score = (
            authority * 0.08 +
            academic * 0.08 +
            star_score * 0.05 +
            diversity * 0.05 +
            usability * 0.06 +
            applicability * 0.06 +
            coverage * 0.03 +
            ndcg * 0.08 +
            retrieval_quality * 0.10 +
            rouge_1 * 0.04 +
            semantic_sim * 0.04 +
            coherence * 0.03 +
            agent_score * 0.20 +   # Agent 占 20%
            task_completion * 0.05 + # 重复但强调
            tool_use * 0.03 +
            reasoning_depth * 0.02
        )

        # 等级
        if final_score >= 0.70:
            grade = "A"
        elif final_score >= 0.55:
            grade = "B"
        elif final_score >= 0.40:
            grade = "C"
        elif final_score >= 0.25:
            grade = "D"
        else:
            grade = "F"

        return {
            "total": n,
            "quality_score": round(final_score, 3),
            "grade": grade,
            "dimensions": {
                # 基础
                "authority": round(authority, 3), "academic": round(academic, 3),
                "star_power": round(star_score, 3), "diversity": round(diversity, 3),
                "usability": round(usability, 3), "applicability": round(applicability, 3),
                "coverage": round(coverage, 3),
                # BEIR
                "ndcg": round(ndcg, 3), "map": round(map_score, 3), "mrr": round(mrr, 3),
                # NLG
                "rouge_1": round(rouge_1, 3), "semantic_sim": round(semantic_sim, 3),
                "coherence": round(coherence, 3),
                # Agent (v4.7)
                "task_completion": round(task_completion, 3),
                "tool_use": round(tool_use, 3),
                "reasoning_depth": round(reasoning_depth, 3),
                "autonomy": round(autonomy, 3),
                "multi_agent": round(multi_agent, 3),
            },
            "sources_breakdown": dict(sources)
        }

# ════════════════════════════════════════════════════════════════
# 5. API 客户端
# ════════════════════════════════════════════════════════════════

class APIClient:
    def __init__(self):
        self.session = None
        self.cache_file = CACHE_DIR / "api_cache.json"
        self.cache = self._load()

    def _load(self):
        if self.cache_file.exists():
            try:
                data = json.load(open(self.cache_file))
                now = time.time()
                return {k: v for k, v in data.items()
                        if now - v.get("_cached_at", 0) < 7 * 86400}
            except:
                return {}
        return {}

    def _save(self):
        json.dump(self.cache, open(self.cache_file, 'w'), indent=2)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "AutoResearch/4.7 (educational)"}
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def search_github(self, query: str, limit: int = 20):
        key = f"github:{query}:{limit}"
        if key in self.cache:
            data = self.cache[key].get("data", [])
            print(f"  [CACHE] GitHub: {len(data)} items")
            return data
        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
            async with self.session.get(url,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = [{
                        "title": item.get("full_name", ""),
                        "url": item.get("html_url", ""),
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                        "source": "github"
                    } for item in data.get("items", [])[:limit]]
                    self.cache[key] = {"data": results, "_cached_at": time.time()}
                    self._save()
                    print(f"  [OK] GitHub: {len(results)} items")
                    return results
                elif resp.status == 403:
                    print(f"  [RATE_LIMIT] GitHub")
        except Exception as e:
            print(f"  [ERROR] GitHub: {e}")
        return []

# ════════════════════════════════════════════════════════════════
# 6. 研究函数
# ════════════════════════════════════════════════════════════════

@dataclass
class ResearchResult:
    topic: str
    findings: list
    quality: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self):
        fname = FINDINGS_DIR / f"{self.topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump({"topic": self.topic, "timestamp": self.timestamp,
                       "findings": self.findings, "quality": self.quality},
                      f, indent=2, ensure_ascii=False)
        return fname

async def research_topic(topic: str) -> ResearchResult:
    print(f"\n{'='*60}")
    print(f"  Research: {topic}")
    print(f"{'='*60}")

    async with APIClient() as client:
        findings = await client.search_github(topic, 20)

    quality = EnhancedQualityScorer.score(findings, topic)
    result = ResearchResult(topic=topic, findings=findings, quality=quality)
    saved = result.save()

    dims = quality.get("dimensions", {})
    print(f"\n  Grade: {quality['grade']} | Score: {quality['quality_score']:.3f}")
    print(f"  [Agent] completion={dims.get('task_completion',0):.3f} "
          f"tool_use={dims.get('tool_use',0):.3f} "
          f"reasoning={dims.get('reasoning_depth',0):.3f} "
          f"autonomy={dims.get('autonomy',0):.3f}")
    print(f"  [BEIR] NDCG={dims.get('ndcg',0):.3f} MAP={dims.get('map',0):.3f}")
    print(f"  [NLG] ROUGE-1={dims.get('rouge_1',0):.3f} SemSim={dims.get('semantic_sim',0):.3f}")
    print(f"  Saved: {saved.name}")

    return result

# ════════════════════════════════════════════════════════════════
# 7. 主入口
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.7 - Agent Evaluation")
    p.add_argument("--topic", "-t", default="")
    p.add_argument("--daily", "-d", action="store_true")
    p.add_argument("--regrade", action="store_true", help="Re-score with v4.7")
    args = p.parse_args()

    if args.regrade:
        print("Re-scoring with v4.7 (Agent Evaluation)...")
        for f in sorted(FINDINGS_DIR.glob("*.json")):
            try:
                data = json.load(open(f, encoding="utf-8"))
                topic = data.get("topic", f.stem)
                findings = data.get("findings", [])
                if not findings:
                    continue
                quality = EnhancedQualityScorer.score(findings, topic)
                dims = quality.get("dimensions", {})
                print(f"  [{quality['grade']}] {topic[:35]:<35} {quality['quality_score']:.3f} "
                      f"task={dims.get('task_completion',0):.2f} "
                      f"tool={dims.get('tool_use',0):.2f}")
            except Exception as e:
                print(f"  [ERROR] {f.name}: {e}")
        return

    if args.topic:
        asyncio.run(research_topic(args.topic))
        return

    print("AutoResearch v4.7 - Agent Task Completion Evaluation")
    print("Usage:")
    print("  python autorun_evolve_v4.7.py --topic 'AI agents'")
    print("  python autorun_evolve_v4.7.py --regrade")

if __name__ == "__main__":
    main()
