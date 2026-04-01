#!/usr/bin/env python3
"""
AutoResearch v4.4 — 主题可用性 + 适用性评分
新增维度:
  - Applicability: 主题与 AutoResearch 本身的相关性
  - Usability:     研究结果的可操作性 (有 README/文档/示例)
  - Freshness:     项目活跃度 (最近更新)
  - Coverage:      主题覆盖广度 (结果数量)
"""
import os, sys, json, time, asyncio, aiohttp
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
# 1. 增强质量评分系统 v4.4
# ════════════════════════════════════════════════════════════════

class EnhancedQualityScorer:
    """
    7 维度评分:
      原有: Authority, Quality, StarPower, Diversity
      新增: Applicability, Usability, Coverage
    """

    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}

    # 学术质量关键词
    ACADEMIC_KW = ["SOTA", "benchmark", "NeurIPS", "ICML", "ICLR", "ACL", "state-of-the-art"]

    # 可用性关键词 (有文档/示例/教程)
    USABILITY_KW = ["tutorial", "example", "demo", "guide", "documentation",
                    "easy", "simple", "quickstart", "getting started", "cookbook"]

    # AutoResearch 适用性关键词 (与研究/信息采集/分析相关)
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
        # 1. Authority: 来源权威性
        source_scores = [EnhancedQualityScorer.SOURCE_WEIGHTS.get(f.get("source", ""), 0.5) for f in findings]
        authority = sum(source_scores) / n

        # 2. Academic Quality: 学术关键词
        academic_count = sum(
            1 for f in findings
            if any(kw.lower() in ((f.get("title") or "") + (f.get("description") or "")).lower()
                   for kw in EnhancedQualityScorer.ACADEMIC_KW)
        )
        academic = academic_count / n

        # 3. Star Power: GitHub star 归一化
        stars = [f.get("stars", 0) for f in findings if f.get("stars", 0) > 0]
        star_score = sum(min(s / max(stars), 1.0) for s in stars) / len(stars) if stars else 0

        # 4. Diversity: 来源多样性
        sources = Counter(f.get("source", "unknown") for f in findings)
        diversity = 1 - sum((c / n) ** 2 for c in sources.values())

        # ── 新增维度 ──────────────────────────────────────────
        # 5. Usability: 可操作性 (有文档/示例/教程)
        usability_count = sum(
            1 for f in findings
            if any(kw.lower() in (f.get("description", "") or "").lower()
                   for kw in EnhancedQualityScorer.USABILITY_KW)
        )
        usability = min(usability_count / n * 2, 1.0)  # 放大系数，更敏感

        # 6. Applicability: 与 AutoResearch 的适用性
        topic_lower = topic.lower()
        topic_applicable = any(
            kw in topic_lower for kw in EnhancedQualityScorer.APPLICABILITY_KW
        )
        desc_applicable_count = sum(
            1 for f in findings
            if any(kw in (f.get("description", "") or "").lower()
                   for kw in EnhancedQualityScorer.APPLICABILITY_KW)
        )
        applicability = (0.5 if topic_applicable else 0.0) + min(desc_applicable_count / n * 0.5, 0.5)

        # 7. Coverage: 覆盖广度 (结果数量归一化，20条=满分)
        coverage = min(n / 20, 1.0)

        # ── 综合评分 (7维度加权) ──────────────────────────────
        # 权重设计: 可用性和适用性各占 15%，覆盖度 10%
        final_score = (
            authority     * 0.20 +
            academic      * 0.20 +
            star_score    * 0.15 +
            diversity     * 0.10 +
            usability     * 0.15 +
            applicability * 0.15 +
            coverage      * 0.05
        )

        # 等级评定
        if final_score >= 0.7:
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
                "authority":     round(authority, 3),
                "academic":      round(academic, 3),
                "star_power":    round(star_score, 3),
                "diversity":     round(diversity, 3),
                "usability":     round(usability, 3),
                "applicability": round(applicability, 3),
                "coverage":      round(coverage, 3),
            },
            "sources_breakdown": dict(sources)
        }

# ════════════════════════════════════════════════════════════════
# 2. 趋势分析
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
        self.trend_data["topics"][topic].append({
            "timestamp": ts,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "grade": quality.get("grade", "?"),
            "dimensions": quality.get("dimensions", {})
        })
        self.trend_data["overall"].append({
            "timestamp": ts,
            "topic": topic,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "grade": quality.get("grade", "?")
        })
        self.trend_data["overall"] = self.trend_data["overall"][-50:]
        self._save()

    def get_summary(self) -> dict:
        if not self.trend_data["overall"]:
            return {}
        recent = self.trend_data["overall"][-20:]
        top_quality = sorted(recent, key=lambda x: x["quality_score"], reverse=True)[:10]
        topic_counts = Counter(d["topic"] for d in recent)
        return {
            "total_researches": len(self.trend_data["overall"]),
            "hot_topics": topic_counts.most_common(5),
            "top_quality": top_quality
        }

# ════════════════════════════════════════════════════════════════
# 3. API 客户端
# ════════════════════════════════════════════════════════════════

class APIClient:
    def __init__(self):
        self.session = None
        self.cache_file = CACHE_DIR / "api_cache.json"
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                data = json.load(open(self.cache_file))
                now = time.time()
                return {k: v for k, v in data.items()
                        if now - v.get("_cached_at", 0) < 7 * 86400}
            except:
                return {}
        return {}

    def _save_cache(self):
        json.dump(self.cache, open(self.cache_file, 'w'), indent=2)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "AutoResearch/4.4 (educational)"}
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
                        "updated_at": item.get("updated_at", ""),
                        "source": "github"
                    } for item in data.get("items", [])[:limit]]
                    self.cache[key] = {"data": results, "_cached_at": time.time()}
                    self._save_cache()
                    print(f"  [OK] GitHub: {len(results)} items")
                    return results
                elif resp.status == 403:
                    print(f"  [RATE_LIMIT] GitHub")
        except Exception as e:
            print(f"  [ERROR] GitHub: {e}")
        return []

# ════════════════════════════════════════════════════════════════
# 4. 研究函数
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
    print(f"\n{'='*55}")
    print(f"  Research: {topic}")
    print(f"{'='*55}")

    async with APIClient() as client:
        findings = await client.search_github(topic, 20)

    quality = EnhancedQualityScorer.score(findings, topic)

    result = ResearchResult(topic=topic, findings=findings, quality=quality)
    saved = result.save()

    TrendAnalyzer().record(topic, findings, quality)

    # 打印评分
    dims = quality.get("dimensions", {})
    print(f"\n  Grade: {quality['grade']}  |  Score: {quality['quality_score']:.3f}")
    print(f"  authority={dims.get('authority',0):.2f}  academic={dims.get('academic',0):.2f}  "
          f"star={dims.get('star_power',0):.2f}  usability={dims.get('usability',0):.2f}  "
          f"applicability={dims.get('applicability',0):.2f}  coverage={dims.get('coverage',0):.2f}")
    print(f"  Saved: {saved.name}")

    return result

# ════════════════════════════════════════════════════════════════
# 5. 主入口
# ════════════════════════════════════════════════════════════════

DAILY_TOPICS = [
    "LLM optimization", "AI agents", "RAG retrieval",
    "model quantization", "fine-tuning LLMs",
]

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.4")
    p.add_argument("--topic", "-t", default="")
    p.add_argument("--daily", "-d", action="store_true")
    p.add_argument("--trends", action="store_true")
    p.add_argument("--regrade", action="store_true", help="Re-score existing findings")
    args = p.parse_args()

    if args.trends:
        s = TrendAnalyzer().get_summary()
        print(f"\n=== TREND ANALYSIS ===")
        print(f"Total: {s.get('total_researches', 0)}")
        print("\nTop Quality:")
        for t in s.get("top_quality", []):
            grade = t.get('grade', '?')
            print(f"  [{grade}] {t['topic']}: {t['quality_score']:.3f}")
        return

    if args.regrade:
        # 重新评分所有已有 findings
        print("Re-grading all existing findings with v4.4 scorer...")
        for f in sorted(FINDINGS_DIR.glob("*.json")):
            try:
                data = json.load(open(f, encoding="utf-8"))
                topic = data.get("topic", f.stem)
                findings = data.get("findings", [])
                if not findings:
                    continue
                quality = EnhancedQualityScorer.score(findings, topic)
                dims = quality.get("dimensions", {})
                print(f"  [{quality['grade']}] {topic[:40]:<40} {quality['quality_score']:.3f}  "
                      f"usability={dims.get('usability',0):.2f}  "
                      f"applicability={dims.get('applicability',0):.2f}")
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

    print("Usage:")
    print("  python autorun_evolve_v4.4.py --topic 'AI agents'")
    print("  python autorun_evolve_v4.4.py --regrade")
    print("  python autorun_evolve_v4.4.py --trends")
    print("  python autorun_evolve_v4.4.py --daily")

if __name__ == "__main__":
    main()
