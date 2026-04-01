#!/usr/bin/env python3
"""
AutoResearch v4.5 — BEIR 检索评测指标集成
新增功能:
  - NDCG-like: 检索结果排序质量
  - MAP: 平均精度均值
  - Recall@K: 召回率
  - Simpson Diversity: 源多样性
  - Relevance Score: 关键词相关性
"""
import os, sys, json, time, asyncio, aiohttp, math
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
# 1. BEIR 检索评测指标
# ════════════════════════════════════════════════════════════════

class RetrievalMetrics:
    """
    基于 BEIR 基准的检索评测指标
    BEIR: A Heterogeneous Benchmark for Information Retrieval
    https://github.com/beir-cellar/beir
    """

    @staticmethod
    def relevance_scores(results: list, query: str) -> list:
        """
        计算每个结果与查询的相关性得分
        基于关键词重叠 + 语义匹配
        """
        query_words = set(query.lower().split())

        # 扩展关键词 (同义词 + 相关词)
        semantic_expansions = {
            "llm": ["language model", "gpt", "transformer", "chatgpt"],
            "ai": ["artificial intelligence", "ml", "machine learning"],
            "model": ["network", "architecture", "deep learning"],
            "research": ["paper", "academic", "study", "survey"],
            "benchmark": ["evaluation", "metric", "test", "leaderboard"],
            "retrieval": ["search", "find", "ranking", "rerank"],
            "quantization": ["quant", "int8", "int4", "compressed"],
            "optimization": ["optimise", "improve", "enhance", "performance"],
            "training": ["train", "fine-tune", "finetune", "learn"],
            "inference": ["infer", "predict", "serve", "deployment"],
        }

        expanded_query = query_words.copy()
        for word in list(query_words):
            if word in semantic_expansions:
                expanded_query.update(semantic_expansions[word])

        scores = []
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            text_words = set(text.split())

            # 精确匹配
            exact = len(query_words & text_words)
            # 语义匹配
            semantic = len(expanded_query & text_words) - exact

            # 标题匹配加权
            title = (r.get("title") or "").lower()
            title_match = any(qw in title for qw in query_words)

            # 综合得分
            score = exact * 1.0 + semantic * 0.5 + (1.0 if title_match else 0.0)
            scores.append(score)

        return scores

    @staticmethod
    def dcg(scores: list) -> float:
        """DCG: Discounted Cumulative Gain"""
        dcg_value = 0.0
        for i, score in enumerate(scores[:10]):  # 只看前10个
            dcg_value += score / math.log2(i + 2)  # i+2 因为 i 从0开始
        return dcg_value

    @staticmethod
    def ndcg(results: list, query: str) -> float:
        """
        NDCG@10: Normalized Discounted Cumulative Gain
        衡量检索结果排序质量，1.0 为完美排序
        """
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0

        dcg = RetrievalMetrics.dcg(scores)

        # 理想排序: 降序排列
        ideal_scores = sorted(scores, reverse=True)
        idcg = RetrievalMetrics.dcg(ideal_scores)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    @staticmethod
    def map(results: list, query: str) -> float:
        """
        MAP: Mean Average Precision
        衡量所有相关结果在排序中的位置质量
        """
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0

        # 设定阈值: 得分 > 0 则视为相关
        threshold = 0.5
        relevant_positions = [i+1 for i, s in enumerate(scores) if s >= threshold]

        if not relevant_positions:
            return 0.0

        # 计算每个相关结果位置的精度
        precisions = []
        for pos in relevant_positions:
            # 该位置之前的相关结果数 / 该位置
            k = relevant_positions.index(pos) + 1
            precisions.append(k / pos)

        return sum(precisions) / len(precisions)

    @staticmethod
    def recall_at_k(results: list, query: str, k: int = 20) -> float:
        """
        Recall@K: 召回率
        在前 K 个结果中召回的相关结果比例
        """
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0

        threshold = 0.5
        top_k = scores[:k]
        relevant_in_k = sum(1 for s in top_k if s >= threshold)
        total_relevant = sum(1 for s in scores if s >= threshold)

        if total_relevant == 0:
            return 0.0

        return relevant_in_k / total_relevant

    @staticmethod
    def mrr(results: list, query: str) -> float:
        """
        MRR: Mean Reciprocal Rank
        首个相关结果的倒数排名
        """
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0

        threshold = 0.5
        for i, s in enumerate(scores):
            if s >= threshold:
                return 1.0 / (i + 1)

        return 0.0

    @staticmethod
    def simpson_diversity(results: list) -> float:
        """
        Simpson 多样性指数
        衡量结果来源的多样性，1.0 为完全多样
        """
        if not results:
            return 0.0

        sources = Counter(r.get("source", "unknown") for r in results)
        n = len(results)
        return 1.0 - sum((c / n) ** 2 for c in sources.values())

    @staticmethod
    def coverage_score(results: list, query: str) -> float:
        """
        覆盖度: 查询关键词在结果中的覆盖程度
        """
        query_words = set(query.lower().split())
        if not query_words:
            return 0.0

        covered = 0
        for word in query_words:
            for r in results:
                text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
                if word in text:
                    covered += 1
                    break

        return covered / len(query_words)

# ════════════════════════════════════════════════════════════════
# 2. 增强质量评分系统 v4.5
# ════════════════════════════════════════════════════════════════

class EnhancedQualityScorer:
    """
    9 维度评分 (v4.5):
      Authority, Academic, StarPower, Diversity
      Usability, Applicability, Coverage
      + NDCG, MAP, MRR (新增 BEIR 检索指标)
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

        # ── 原有维度 ──────────────────────────────────────────
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
            ) / n * 2,
            1.0
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

        # ── BEIR 检索指标 (v4.5 新增) ─────────────────────────
        # 使用 topic 作为查询
        ndcg = RetrievalMetrics.ndcg(findings, topic)
        map_score = RetrievalMetrics.map(findings, topic)
        mrr = RetrievalMetrics.mrr(findings, topic)
        recall = RetrievalMetrics.recall_at_k(findings, topic, k=10)
        simpson = RetrievalMetrics.simpson_diversity(findings)

        # 综合检索质量 (BEIR 风格)
        retrieval_quality = ndcg * 0.4 + map_score * 0.3 + mrr * 0.2 + recall * 0.1

        # ── 综合评分 ──────────────────────────────────────────
        final_score = (
            authority        * 0.12 +
            academic         * 0.12 +
            star_score       * 0.08 +
            diversity        * 0.08 +
            usability        * 0.10 +
            applicability     * 0.10 +
            coverage         * 0.05 +
            ndcg             * 0.15 +   # BEIR NDCG
            retrieval_quality * 0.20     # 综合检索质量
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
                "authority":    round(authority, 3),
                "academic":     round(academic, 3),
                "star_power":   round(star_score, 3),
                "diversity":    round(diversity, 3),
                "usability":   round(usability, 3),
                "applicability": round(applicability, 3),
                "coverage":    round(coverage, 3),
                # BEIR 检索指标
                "ndcg":        round(ndcg, 3),
                "map":         round(map_score, 3),
                "mrr":         round(mrr, 3),
                "recall":      round(recall, 3),
            },
            "sources_breakdown": dict(sources)
        }

# ════════════════════════════════════════════════════════════════
# 3. 趋势分析
# ════════════════════════════════════════════════════════════════

class TrendAnalyzer:
    def __init__(self):
        self.history_file = TRENDS_DIR / "history.json"
        self.trend_data = self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                return json.load(open(self.history_file))
            except:
                pass
        return {"topics": {}, "overall": []}

    def _save(self):
        json.dump(self.trend_data, open(self.history_file, 'w'), indent=2)

    def record(self, topic: str, findings: list, quality: dict):
        ts = datetime.now().isoformat()
        if topic not in self.trend_data["topics"]:
            self.trend_data["topics"][topic] = []

        dims = quality.get("dimensions", {})
        self.trend_data["topics"][topic].append({
            "timestamp": ts,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "grade": quality.get("grade", "?"),
            "ndcg": dims.get("ndcg", 0),
            "map": dims.get("map", 0),
            "mrr": dims.get("mrr", 0),
        })

        self.trend_data["overall"].append({
            "timestamp": ts,
            "topic": topic,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "grade": quality.get("grade", "?"),
            "ndcg": dims.get("ndcg", 0),
        })

        self.trend_data["overall"] = self.trend_data["overall"][-50:]
        self._save()

    def get_summary(self) -> dict:
        if not self.trend_data["overall"]:
            return {}
        recent = self.trend_data["overall"][-20:]
        top = sorted(recent, key=lambda x: x.get("quality_score", 0), reverse=True)[:10]
        counts = Counter(d["topic"] for d in recent)

        # 计算平均 NDCG
        avg_ndcg = sum(d.get("ndcg", 0) for d in recent) / len(recent) if recent else 0

        return {
            "total_researches": len(self.trend_data["overall"]),
            "avg_ndcg": round(avg_ndcg, 3),
            "hot_topics": counts.most_common(5),
            "top_quality": top,
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
            headers={"User-Agent": "AutoResearch/4.5 (educational)"}
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
    TrendAnalyzer().record(topic, findings, quality)

    dims = quality.get("dimensions", {})
    print(f"\n  Grade: {quality['grade']} | Score: {quality['quality_score']:.3f}")
    print(f"  [BEIR] NDCG={dims.get('ndcg',0):.3f} MAP={dims.get('map',0):.3f} "
          f"MRR={dims.get('mrr',0):.3f} Recall={dims.get('recall',0):.3f}")
    print(f"  [SRC] authority={dims.get('authority',0):.2f} academic={dims.get('academic',0):.2f} "
          f"usability={dims.get('usability',0):.2f} applicability={dims.get('applicability',0):.2f}")
    print(f"  Saved: {saved.name}")

    return result

# ════════════════════════════════════════════════════════════════
# 6. 主入口
# ════════════════════════════════════════════════════════════════

DAILY_TOPICS = [
    "LLM optimization", "AI agents", "RAG retrieval",
    "model quantization", "fine-tuning LLMs",
]

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.5 - BEIR Metrics")
    p.add_argument("--topic", "-t", default="")
    p.add_argument("--daily", "-d", action="store_true")
    p.add_argument("--trends", action="store_true")
    p.add_argument("--regrade", action="store_true", help="Re-score with v4.5")
    args = p.parse_args()

    if args.trends:
        s = TrendAnalyzer().get_summary()
        print(f"\n=== TREND ANALYSIS v4.5 ===")
        print(f"Total researches: {s.get('total_researches', 0)}")
        print(f"Average NDCG: {s.get('avg_ndcg', 0):.3f}")
        print("\nTop Quality:")
        for t in s.get("top_quality", []):
            grade = t.get('grade', '?')
            ndcg = t.get('ndcg', 0)
            print(f"  [{grade}] {t['topic'][:40]:<40} {t['quality_score']:.3f} NDCG={ndcg:.3f}")
        return

    if args.regrade:
        print("Re-scoring with v4.5 (BEIR metrics)...")
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
                      f"ndcg={dims.get('ndcg',0):.3f} map={dims.get('map',0):.3f}")
            except Exception as e:
                print(f"  [ERROR] {f.name}: {e}")
        return

    if args.daily:
        async def run():
            for topic in DAILY_TOPICS:
                await research_topic(topic)
                await asyncio.sleep(1)
        asyncio.run(run())
        return

    if args.topic:
        asyncio.run(research_topic(args.topic))
        return

    print("AutoResearch v4.5 - BEIR Metrics")
    print("Usage:")
    print("  python autorun_evolve_v4.5.py --topic 'AI agents'")
    print("  python autorun_evolve_v4.5.py --regrade")
    print("  python autorun_evolve_v4.5.py --trends")

if __name__ == "__main__":
    main()
