#!/usr/bin/env python3
"""
AutoResearch v4.6 — NLG 摘要评测 + BEIR 检索指标
新增功能:
  - ROUGE-1/2/L: n-gram 重叠指标
  - BERTScore: 语义相似度 (基于余弦相似度简化版)
  - Summary Coherence: 摘要连贯性
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
# 1. NLG 摘要评测指标
# ════════════════════════════════════════════════════════════════

class NLGEvaluator:
    """
    NLG (Natural Language Generation) 评测指标
    用于评估摘要生成、信息抽取等任务的质量
    """

    @staticmethod
    def _tokenize(text: str) -> list:
        """简单分词"""
        return re.findall(r'\b\w+\b', text.lower())

    @staticmethod
    def rouge_1(reference: str, hypothesis: str) -> float:
        """
        ROUGE-1: unigram 重叠
        衡量词汇级别的重叠
        """
        ref_tokens = set(NLGEvaluator._tokenize(reference))
        hyp_tokens = set(NLGEvaluator._tokenize(hypothesis))

        if not ref_tokens:
            return 0.0

        overlap = len(ref_tokens & hyp_tokens)
        return overlap / len(ref_tokens)

    @staticmethod
    def rouge_2(reference: str, hypothesis: str) -> float:
        """
        ROUGE-2: bigram 重叠
        衡量连续词对的重叠
        """
        def get_bigrams(text):
            tokens = NLGEvaluator._tokenize(text)
            return set(zip(tokens[:-1], tokens[1:])) if len(tokens) > 1 else set()

        ref_bigrams = get_bigrams(reference)
        hyp_bigrams = get_bigrams(hypothesis)

        if not ref_bigrams:
            return 0.0

        overlap = len(ref_bigrams & hyp_bigrams)
        return overlap / len(ref_bigrams)

    @staticmethod
    def rouge_l(reference: str, hypothesis: str) -> float:
        """
        ROUGE-L: 最长公共子序列
        衡量句子级别的结构相似度
        """
        ref_tokens = NLGEvaluator._tokenize(reference)
        hyp_tokens = NLGEvaluator._tokenize(hypothesis)

        if not ref_tokens or not hyp_tokens:
            return 0.0

        # LCS 长度
        m, n = len(ref_tokens), len(hyp_tokens)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i-1] == hyp_tokens[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        lcs_len = dp[m][n]

        # ROUGE-L = LCS / reference length
        return lcs_len / m if m > 0 else 0.0

    @staticmethod
    def _word_freq(text: str) -> dict:
        """词频统计"""
        tokens = NLGEvaluator._tokenize(text)
        freq = Counter(tokens)
        total = sum(freq.values())
        return {w: c/total for w, c in freq.items()}

    @staticmethod
    def cosine_similarity(vec1: dict, vec2: dict) -> float:
        """余弦相似度"""
        common_keys = set(vec1.keys()) & set(vec2.keys())
        if not common_keys:
            return 0.0

        dot_product = sum(vec1[k] * vec2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v**2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v**2 for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    @staticmethod
    def semantic_similarity(text1: str, text2: str) -> float:
        """
        简化版语义相似度
        基于词频向量的余弦相似度
        """
        vec1 = NLGEvaluator._word_freq(text1)
        vec2 = NLGEvaluator._word_freq(text2)
        return NLGEvaluator.cosine_similarity(vec1, vec2)

    @staticmethod
    def coherence_score(text: str) -> float:
        """
        连贯性评分
        基于句子长度和词汇多样性的综合评分
        """
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        # 1. 平均句子长度 (太长或太短都不好)
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        len_score = min(avg_len / 15, 1.0) * 0.5  # 15词为最佳

        # 2. 词汇多样性 (不同词 / 总词数)
        all_tokens = []
        for s in sentences:
            all_tokens.extend(NLGEvaluator._tokenize(s))

        if not all_tokens:
            return 0.0

        unique_ratio = len(set(all_tokens)) / len(all_tokens)
        diversity_score = unique_ratio * 0.5

        return (len_score + diversity_score) / 2

    @staticmethod
    def evaluate_summary(reference: str, hypothesis: str) -> dict:
        """
        综合评估摘要质量
        """
        return {
            "rouge_1": round(NLGEvaluator.rouge_1(reference, hypothesis), 4),
            "rouge_2": round(NLGEvaluator.rouge_2(reference, hypothesis), 4),
            "rouge_l": round(NLGEvaluator.rouge_l(reference, hypothesis), 4),
            "semantic_sim": round(NLGEvaluator.semantic_similarity(reference, hypothesis), 4),
            "coherence": round(NLGEvaluator.coherence_score(hypothesis), 4),
        }

    @staticmethod
    def evaluate_corpus(results: list, topic: str) -> dict:
        """
        评估整个结果集的质量
        将每个结果的标题/描述与 topic 计算相似度
        """
        if not results:
            return {}

        scores = {
            "rouge_1": [], "rouge_2": [], "rouge_l": [],
            "semantic_sim": [], "coherence": []
        }

        for r in results:
            title = r.get("title", "")
            desc = r.get("description", "") or ""

            # 评估标题与描述的连贯性
            title_desc_coherence = NLGEvaluator.semantic_similarity(title, desc)

            # 评估描述与主题的关联度
            desc_topic_sim = NLGEvaluator.semantic_similarity(desc, topic)

            # 评估标题与主题的关联度
            title_topic_sim = NLGEvaluator.semantic_similarity(title, topic)

            # ROUGE: 比较描述与主题
            r1 = NLGEvaluator.rouge_1(topic, desc)
            r2 = NLGEvaluator.rouge_2(topic, desc)
            rl = NLGEvaluator.rouge_l(topic, desc)

            scores["rouge_1"].append(r1)
            scores["rouge_2"].append(r2)
            scores["rouge_l"].append(rl)
            scores["semantic_sim"].append(desc_topic_sim)
            scores["coherence"].append(title_desc_coherence)

        # 返回平均分
        return {
            "rouge_1_avg": round(sum(scores["rouge_1"]) / len(scores["rouge_1"]), 4),
            "rouge_2_avg": round(sum(scores["rouge_2"]) / len(scores["rouge_2"]), 4),
            "rouge_l_avg": round(sum(scores["rouge_l"]) / len(scores["rouge_l"]), 4),
            "semantic_sim_avg": round(sum(scores["semantic_sim"]) / len(scores["semantic_sim"]), 4),
            "coherence_avg": round(sum(scores["coherence"]) / len(scores["coherence"]), 4),
        }

# ════════════════════════════════════════════════════════════════
# 2. BEIR 检索指标 (复用)
# ════════════════════════════════════════════════════════════════

class RetrievalMetrics:
    """BEIR 检索评测指标"""

    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}

    @staticmethod
    def relevance_scores(results: list, query: str) -> list:
        query_words = set(query.lower().split())
        semantic_expansions = {
            "llm": ["language model", "gpt", "transformer", "chatgpt"],
            "ai": ["artificial intelligence", "ml", "machine learning"],
            "benchmark": ["evaluation", "metric", "test", "leaderboard"],
            "retrieval": ["search", "find", "ranking", "rerank"],
            "quantization": ["quant", "int8", "int4", "compressed"],
            "optimization": ["optimise", "improve", "enhance"],
            "training": ["train", "fine-tune", "finetune"],
            "inference": ["infer", "predict", "serve", "deployment"],
            "agent": ["agentic", "autonomous", "tool use", "reasoning"],
            "evaluation": ["benchmark", "metric", "assessment", "test"],
        }

        expanded_query = query_words.copy()
        for word in list(query_words):
            if word in semantic_expansions:
                expanded_query.update(semantic_expansions[word])

        scores = []
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            text_words = set(text.split())
            exact = len(query_words & text_words)
            semantic = len(expanded_query & text_words) - exact
            title = (r.get("title") or "").lower()
            title_match = any(qw in title for qw in query_words)
            score = exact * 1.0 + semantic * 0.5 + (1.0 if title_match else 0.0)
            scores.append(score)

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
        threshold = 0.5
        positions = [i+1 for i, s in enumerate(scores) if s >= threshold]
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
        threshold = 0.5
        top_k = scores[:k]
        return sum(1 for s in top_k if s >= threshold) / sum(1 for s in scores if s >= threshold) if scores else 0.0

    @staticmethod
    def simpson_diversity(results: list) -> float:
        if not results:
            return 0.0
        sources = Counter(r.get("source", "unknown") for r in results)
        n = len(results)
        return 1.0 - sum((c / n) ** 2 for c in sources.values())

# ════════════════════════════════════════════════════════════════
# 3. 综合评分系统 v4.6
# ════════════════════════════════════════════════════════════════

class EnhancedQualityScorer:
    """
    13 维度评分 (v4.6):
      原有 + BEIR + NLG
    """

    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}
    ACADEMIC_KW = ["SOTA", "benchmark", "NeurIPS", "ICML", "ICLR", "ACL", "state-of-the-art"]
    USABILITY_KW = ["tutorial", "example", "demo", "guide", "documentation",
                    "easy", "simple", "quickstart", "getting started", "cookbook"]
    APPLICABILITY_KW = [
        "research", "survey", "analysis", "search", "retrieval",
        "crawler", "scraper", "aggregator", "monitor", "tracker",
        "pipeline", "automation", "workflow", "agent", "tool",
        "api", "dataset", "benchmark", "evaluation", "metric"
    ]

    @staticmethod
    def score(findings: list, topic: str = "") -> dict:
        if not findings:
            return {"total": 0, "quality_score": 0, "dimensions": {}, "grade": "F"}

        n = len(findings)

        # ── 基础维度 ──────────────────────────────────────────
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

        # ── BEIR 检索指标 ────────────────────────────────────
        ndcg = RetrievalMetrics.ndcg(findings, topic)
        map_score = RetrievalMetrics.map(findings, topic)
        mrr = RetrievalMetrics.mrr(findings, topic)
        recall = RetrievalMetrics.recall_at_k(findings, topic, k=10)

        # ── NLG 评测指标 (v4.6 新增) ────────────────────────
        nlg_scores = NLGEvaluator.evaluate_corpus(findings, topic)

        rouge_1 = nlg_scores.get("rouge_1_avg", 0)
        rouge_2 = nlg_scores.get("rouge_2_avg", 0)
        rouge_l = nlg_scores.get("rouge_l_avg", 0)
        semantic_sim = nlg_scores.get("semantic_sim_avg", 0)
        coherence = nlg_scores.get("coherence_avg", 0)

        # ── 综合检索质量 ────────────────────────────────────
        retrieval_quality = ndcg * 0.3 + map_score * 0.25 + mrr * 0.15 + recall * 0.15 + rouge_1 * 0.15

        # ── 综合评分 (13 维度) ─────────────────────────────
        final_score = (
            authority        * 0.10 +
            academic         * 0.10 +
            star_score       * 0.06 +
            diversity        * 0.06 +
            usability        * 0.08 +
            applicability     * 0.08 +
            coverage         * 0.04 +
            ndcg             * 0.12 +
            retrieval_quality * 0.16 +   # 综合检索
            rouge_1          * 0.06 +     # NLG ROUGE-1
            semantic_sim     * 0.06 +     # 语义相似度
            coherence        * 0.04       # 连贯性
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
                "authority":    round(authority, 3),
                "academic":     round(academic, 3),
                "star_power":   round(star_score, 3),
                "diversity":    round(diversity, 3),
                "usability":    round(usability, 3),
                "applicability": round(applicability, 3),
                "coverage":     round(coverage, 3),
                # BEIR
                "ndcg":         round(ndcg, 3),
                "map":          round(map_score, 3),
                "mrr":          round(mrr, 3),
                # NLG (v4.6)
                "rouge_1":      round(rouge_1, 3),
                "rouge_2":      round(rouge_2, 3),
                "semantic_sim": round(semantic_sim, 3),
                "coherence":     round(coherence, 3),
            },
            "sources_breakdown": dict(sources)
        }

# ════════════════════════════════════════════════════════════════
# 4. API 客户端
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
            headers={"User-Agent": "AutoResearch/4.6 (educational)"}
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
# 5. 研究函数
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
    print(f"  [BEIR] NDCG={dims.get('ndcg',0):.3f} MAP={dims.get('map',0):.3f} MRR={dims.get('mrr',0):.3f}")
    print(f"  [NLG] ROUGE-1={dims.get('rouge_1',0):.3f} ROUGE-2={dims.get('rouge_2',0):.3f} "
          f"SemSim={dims.get('semantic_sim',0):.3f} Coherence={dims.get('coherence',0):.3f}")
    print(f"  Saved: {saved.name}")

    return result

# ════════════════════════════════════════════════════════════════
# 6. 主入口
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.6 - BEIR + NLG Metrics")
    p.add_argument("--topic", "-t", default="")
    p.add_argument("--daily", "-d", action="store_true")
    p.add_argument("--trends", action="store_true")
    p.add_argument("--regrade", action="store_true", help="Re-score with v4.6")
    args = p.parse_args()

    if args.trends:
        from pathlib import Path
        history_file = TRENDS_DIR / "history.json"
        if history_file.exists():
            data = json.load(open(history_file))
            recent = data.get("overall", [])[-20:]
            top = sorted(recent, key=lambda x: x.get("quality_score", 0), reverse=True)[:10]
            print(f"\n=== TREND ANALYSIS v4.6 ===")
            print(f"Total researches: {len(data.get('overall', []))}")
            print("\nTop Quality:")
            for t in top:
                dims = t.get("dimensions", {})
                grade = t.get('grade', '?')
                print(f"  [{grade}] {t['topic'][:40]:<40} {t['quality_score']:.3f}")
        return

    if args.regrade:
        print("Re-scoring with v4.6 (BEIR + NLG)...")
        for f in sorted(FINDINGS_DIR.glob("*.json")):
            try:
                data = json.load(open(f, encoding="utf-8"))
                topic = data.get("topic", f.stem)
                findings = data.get("findings", [])
                if not findings:
                    continue
                quality = EnhancedQualityScorer.score(findings, topic)
                dims = quality.get("dimensions", {})
                print(f"  [{quality['grade']}] {topic[:40]:<40} {quality['quality_score']:.3f} "
                      f"ndcg={dims.get('ndcg',0):.3f} r1={dims.get('rouge_1',0):.3f}")
            except Exception as e:
                print(f"  [ERROR] {f.name}: {e}")
        return

    if args.topic:
        asyncio.run(research_topic(args.topic))
        return

    print("AutoResearch v4.6 - BEIR + NLG Metrics")
    print("Usage:")
    print("  python autorun_evolve_v4.6.py --topic 'AI agents'")
    print("  python autorun_evolve_v4.6.py --regrade")

if __name__ == "__main__":
    main()
