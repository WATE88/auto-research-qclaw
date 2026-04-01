#!/usr/bin/env python3
"""
AutoResearch v4.3 — Crossref 替代 ArXiv
- GitHub API (缓存)
- Crossref API (论文, 无限流)
"""
import os, sys, json, time, random, asyncio, aiohttp
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
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
FINDINGS_DIR.mkdir(exist_ok=True)
TRENDS_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 1. 质量评分系统
# ════════════════════════════════════════════════════════════════

class QualityScorer:
    SOURCE_WEIGHTS = {"github": 0.9, "crossref": 1.0}
    HIGH_QUALITY_KW = ["SOTA", "benchmark", "state-of-the-art", "ACL", "NeurIPS", "ICML", "ICLR"]
    
    @staticmethod
    def score(findings: list) -> dict:
        if not findings:
            return {"total": 0, "quality_score": 0, "dimensions": {}}
        
        n = len(findings)
        
        source_scores = [QualityScorer.SOURCE_WEIGHTS.get(f.get("source", ""), 0.5) for f in findings]
        authority = sum(source_scores) / n
        
        quality_count = sum(
            1 for f in findings
            if any(kw.lower() in f.get("title", "").lower() for kw in QualityScorer.HIGH_QUALITY_KW)
        )
        quality = quality_count / n
        
        stars = [f.get("stars", 0) for f in findings if f.get("stars", 0) > 0]
        star_score = sum(min(s / max(stars), 1.0) for s in stars) / len(stars) if stars else 0
        
        sources = Counter(f.get("source", "unknown") for f in findings)
        diversity = 1 - sum((c / n) ** 2 for c in sources.values())
        
        final_score = authority * 0.3 + quality * 0.3 + star_score * 0.2 + diversity * 0.2
        
        return {
            "total": n,
            "quality_score": round(final_score, 3),
            "dimensions": {
                "authority": round(authority, 3),
                "quality": round(quality, 3),
                "star_power": round(star_score, 3),
                "diversity": round(diversity, 3)
            },
            "sources_breakdown": dict(sources)
        }

# ════════════════════════════════════════════════════════════════
# 2. 趋势分析
# ════════════════════════════════════════════════════════════════

class TrendAnalyzer:
    def __init__(self):
        self.history_file = TRENDS_DIR / "history.json"
        self.trend_data = self._load_history()
    
    def _load_history(self):
        if self.history_file.exists():
            try:
                return json.load(open(self.history_file))
            except:
                return {"topics": {}, "overall": []}
        return {"topics": {}, "overall": []}
    
    def _save_history(self):
        json.dump(self.trend_data, open(self.history_file, 'w'), indent=2)
    
    def record_topic(self, topic: str, findings: list, quality: dict):
        ts = datetime.now().isoformat()
        
        if topic not in self.trend_data["topics"]:
            self.trend_data["topics"][topic] = []
        
        self.trend_data["topics"][topic].append({
            "timestamp": ts,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "sources": quality.get("sources_breakdown", {})
        })
        
        self.trend_data["overall"].append({
            "timestamp": ts,
            "topic": topic,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0)
        })
        
        self.trend_data["overall"] = self.trend_data["overall"][-30:]
        self._save_history()
    
    def get_overall_trends(self) -> dict:
        if not self.trend_data["overall"]:
            return {}
        
        recent = self.trend_data["overall"][-10:]
        
        topic_counts = Counter(d["topic"] for d in recent)
        hot_topics = topic_counts.most_common(5)
        
        top_quality = sorted(recent, key=lambda x: x["quality_score"], reverse=True)[:5]
        
        return {
            "hot_topics": [{"topic": t, "count": c} for t, c in hot_topics],
            "top_quality": [{"topic": d["topic"], "score": d["quality_score"]} for d in top_quality],
            "total_researches": len(self.trend_data["overall"])
        }

# ════════════════════════════════════════════════════════════════
# 3. API 客户端 (v4.3)
# ════════════════════════════════════════════════════════════════

class RealAPIClient:
    def __init__(self):
        self.session = None
        self.cache_file = CACHE_DIR / "api_cache.json"
        self.api_cache = self._load_cache()
        self.crossref_delay = 0
    
    def _load_cache(self):
        if self.cache_file.exists():
            try:
                data = json.load(open(self.cache_file))
                now = time.time()
                cleaned = {}
                for k, v in data.items():
                    if now - v.get("_cached_at", 0) < 7 * 86400:
                        cleaned[k] = v
                return cleaned
            except:
                return {}
        return {}
    
    def _save_cache(self):
        json.dump(self.api_cache, open(self.cache_file, 'w'), indent=2)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "AutoResearch/4.3 (educational research)"}
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def search_github(self, query: str, limit: int = 20):
        cache_key = f"github:{query}:{limit}"
        
        if cache_key in self.api_cache:
            cached = self.api_cache[cache_key].get("data", [])
            print(f"  [CACHE] GitHub: {len(cached)} items")
            return cached
        
        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = [{
                        "title": item.get("full_name", ""),
                        "url": item.get("html_url", ""),
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                        "source": "github"
                    } for item in data.get('items', [])[:limit]]
                    
                    self.api_cache[cache_key] = {"data": results, "_cached_at": time.time()}
                    self._save_cache()
                    
                    print(f"  [OK] GitHub: {len(results)} items")
                    return results
                elif resp.status == 403:
                    print(f"  [RATE_LIMIT] GitHub 限流")
        
        except Exception as e:
            print(f"  [ERROR] GitHub: {e}")
        
        return []
    
    async def search_crossref(self, query: str, limit: int = 20):
        """Crossref 论文搜索 - 无官方限流"""
        cache_key = f"crossref:{query}:{limit}"
        
        if cache_key in self.api_cache:
            cached = self.api_cache[cache_key].get("data", [])
            print(f"  [CACHE] Crossref: {len(cached)} items")
            return cached
        
        # 礼貌性延迟
        elapsed = time.time() - self.crossref_delay
        if elapsed < 1:
            await asyncio.sleep(1 - elapsed + 0.5)
        
        self.crossref_delay = time.time()
        
        try:
            url = f"https://api.crossref.org/works?query={query}&rows={limit}&sort=published-date-desc"
            
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    
                    for item in data.get('message', {}).get('items', []):
                        title = item.get('title', [''])[0]
                        year = item.get('published-print', {}).get('date-parts', [['']])[0][0] or \
                               item.get('published-online', {}).get('date-parts', [['']])[0][0] or ''
                        
                        # 获取 DOI URL
                        doi = item.get('DOI', '')
                        url_link = f"https://doi.org/{doi}" if doi else ''
                        
                        results.append({
                            "title": title,
                            "url": url_link,
                            "year": year,
                            "source": "crossref"
                        })
                    
                    if results:
                        self.api_cache[cache_key] = {"data": results, "_cached_at": time.time()}
                        self._save_cache()
                        print(f"  [OK] Crossref: {len(results)} papers")
                    else:
                        print(f"  [EMPTY] Crossref: 无结果")
                    return results
        
        except Exception as e:
            print(f"  [ERROR] Crossref: {e}")
        
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
            json.dump({
                "topic": self.topic,
                "timestamp": self.timestamp,
                "findings": self.findings,
                "quality": self.quality
            }, f, indent=2, ensure_ascii=False)
        return fname

async def research_topic(topic: str, sources: list = None) -> ResearchResult:
    if sources is None:
        sources = ["github", "crossref"]
    
    print(f"\n{'='*50}")
    print(f"Research: {topic}")
    print(f"{'='*50}")
    
    all_findings = []
    
    async with RealAPIClient() as client:
        tasks = []
        if "github" in sources:
            tasks.append(("github", client.search_github(topic, 20)))
        if "crossref" in sources:
            tasks.append(("crossref", client.search_crossref(topic, 20)))
        
        for name, task in tasks:
            try:
                results = await task
                all_findings.extend(results)
            except Exception as e:
                print(f"  {name}: Error - {e}")
    
    quality = QualityScorer.score(all_findings)
    
    result = ResearchResult(topic=topic, findings=all_findings, quality=quality)
    saved_file = result.save()
    
    analyzer = TrendAnalyzer()
    analyzer.record_topic(topic, all_findings, quality)
    
    print(f"\nQuality Score: {quality['quality_score']:.3f}")
    print(f"Total: {quality['total']} findings")
    print(f"Saved: {saved_file.name}")
    
    return result

# ════════════════════════════════════════════════════════════════
# 5. 主入口
# ════════════════════════════════════════════════════════════════

DAILY_TOPICS = [
    "LLM optimization",
    "AI agents",
    "RAG retrieval",
    "model quantization",
    "fine-tuning LLMs",
]

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.3")
    p.add_argument("--topic", "-t", default="", help="Research topic")
    p.add_argument("--daily", "-d", action="store_true", help="Run daily research")
    p.add_argument("--trends", action="store_true", help="Show trends")
    args = p.parse_args()
    
    if args.trends:
        analyzer = TrendAnalyzer()
        print("\n=== TREND ANALYSIS ===\n")
        overall = analyzer.get_overall_trends()
        if overall:
            print(f"Total researches: {overall.get('total_researches', 0)}")
            print("\nHot Topics:")
            for t in overall.get("hot_topics", []):
                print(f"  - {t['topic']}: {t['count']}")
            print("\nTop Quality:")
            for t in overall.get("top_quality", []):
                print(f"  - {t['topic']}: {t['score']}")
        else:
            print("No trend data yet!")
        return
    
    if args.daily:
        async def run():
            results = []
            for topic in DAILY_TOPICS:
                try:
                    result = await research_topic(topic)
                    results.append(result)
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"  [!] Error: {e}")
            return results
        asyncio.run(run())
        return
    
    if args.topic:
        result = asyncio.run(research_topic(args.topic))
        print(f"\nFinal Quality: {result.quality['quality_score']:.3f}")
        return
    
    print("Usage:")
    print("  python autorun_evolve_v4.3.py --topic 'LLM optimization'")
    print("  python autorun_evolve_v4.3.py --daily")
    print("  python autorun_evolve_v4.3.py --trends")

if __name__ == "__main__":
    main()
