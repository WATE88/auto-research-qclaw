#!/usr/bin/env python3
"""
AutoResearch v4.1 — 增强版：趋势分析 + 质量评分 + 定时任务
"""
import os, sys, json, time, random, asyncio, aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter, defaultdict

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
    """多维度质量评分"""
    
    SOURCE_WEIGHTS = {"github": 0.9, "arxiv": 1.0, "hackernews": 0.8}
    HIGH_QUALITY_KW = ["SOTA", "benchmark", "state-of-the-art", "ACL", "NeurIPS", "ICML"]
    MEDIUM_KW = ["implementation", "framework", "tutorial", "guide"]
    
    @staticmethod
    def score(findings: list) -> dict:
        if not findings:
            return {"total": 0, "quality_score": 0, "dimensions": {}}
        
        n = len(findings)
        
        # 1. 来源权威性
        source_scores = [QualityScorer.SOURCE_WEIGHTS.get(f.get("source", ""), 0.5) for f in findings]
        authority = sum(source_scores) / n
        
        # 2. 质量关键词
        quality_count = 0
        for f in findings:
            title = f.get("title", "").lower()
            if any(kw.lower() in title for kw in QualityScorer.HIGH_QUALITY_KW):
                quality_count += 1
        
        quality = quality_count / n
        
        # 3. GitHub star 评分（归一化）
        stars = [f.get("stars", 0) for f in findings if f.get("stars", 0) > 0]
        star_score = 0
        if stars:
            max_star = max(stars)
            star_score = sum(min(s / max_star, 1.0) for s in stars) / len(stars)
        
        # 4. 多样性
        sources = Counter(f.get("source", "unknown") for f in findings)
        diversity = 1 - sum((c / n) ** 2 for c in sources.values())
        
        # 综合评分
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
# 2. 趋势分析系统
# ════════════════════════════════════════════════════════════════

class TrendAnalyzer:
    """趋势分析"""
    
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
        """记录主题发现"""
        ts = datetime.now().isoformat()
        
        # 提取关键词趋势
        keywords = self._extract_keywords(findings)
        
        if topic not in self.trend_data["topics"]:
            self.trend_data["topics"][topic] = []
        
        self.trend_data["topics"][topic].append({
            "timestamp": ts,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0),
            "top_keywords": keywords[:10],
            "sources": quality.get("sources_breakdown", {})
        })
        
        # 记录全局趋势
        self.trend_data["overall"].append({
            "timestamp": ts,
            "topic": topic,
            "findings_count": len(findings),
            "quality_score": quality.get("quality_score", 0)
        })
        
        # 只保留最近30条
        self.trend_data["overall"] = self.trend_data["overall"][-30:]
        
        self._save_history()
    
    def _extract_keywords(self, findings: list) -> list:
        """提取关键词"""
        import re
        word_freq = Counter()
        
        for f in findings:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', f.get("title", "").lower())
            for w in words:
                if w not in ["https", "github", "arxiv", "http"]:
                    word_freq[w] += 1
        
        return [w for w, _ in word_freq.most_common(20)]
    
    def get_trend(self, topic: str) -> dict:
        """获取主题趋势"""
        if topic not in self.trend_data["topics"]:
            return {}
        
        data = self.trend_data["topics"][topic]
        if len(data) < 2:
            return {"trend": "insufficient_data", "data_points": len(data)}
        
        # 计算趋势
        scores = [d["quality_score"] for d in data]
        first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        
        if second_half > first_half * 1.1:
            trend = "rising"
        elif second_half < first_half * 0.9:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "data_points": len(data),
            "avg_quality": round(sum(scores) / len(scores), 3),
            "max_quality": max(scores),
            "evolution": data
        }
    
    def get_overall_trends(self) -> dict:
        """获取全局趋势"""
        if not self.trend_data["overall"]:
            return {}
        
        recent = self.trend_data["overall"][-10:]
        
        # 热门主题
        topic_counts = Counter(d["topic"] for d in recent)
        hot_topics = topic_counts.most_common(5)
        
        # 质量最佳
        top_quality = sorted(recent, key=lambda x: x["quality_score"], reverse=True)[:5]
        
        return {
            "hot_topics": [{"topic": t, "count": c} for t, c in hot_topics],
            "top_quality": [{"topic": d["topic"], "score": d["quality_score"]} for d in top_quality],
            "total_researches": len(self.trend_data["overall"])
        }

# ════════════════════════════════════════════════════════════════
# 3. 真实 API 客户端
# ════════════════════════════════════════════════════════════════

class RealAPIClient:
    """真实 API 客户端"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def search_github(self, query: str, limit: int = 20):
        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [{
                        "title": item.get("full_name", ""),
                        "url": item.get("html_url", ""),
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                        "source": "github"
                    } for item in data.get('items', [])[:limit]]
        except Exception as e:
            print(f"  [!] GitHub: {e}")
        return []
    
    async def search_arxiv(self, query: str, limit: int = 20):
        try:
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    import re
                    results = []
                    entries = re.findall(r'<entry>(.*?)</entry>', text, re.DOTALL)
                    for entry in entries[:limit]:
                        title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                        summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                        link = re.search(r'<id>(.*?)</id>', entry)
                        if title:
                            results.append({
                                "title": title.group(1).strip().replace('\n', ' '),
                                "url": link.group(1) if link else "",
                                "abstract": (summary.group(1).strip()[:300] if summary else ""),
                                "source": "arxiv"
                            })
                    return results
        except Exception as e:
            print(f"  [!] ArXiv: {e}")
        return []

# ════════════════════════════════════════════════════════════════
# 4. 主研究函数
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
    """研究单个主题"""
    if sources is None:
        sources = ["github", "arxiv"]
    
    print(f"\n{'='*50}")
    print(f"Research: {topic}")
    print(f"{'='*50}")
    
    all_findings = []
    
    async with RealAPIClient() as client:
        tasks = []
        if "github" in sources:
            tasks.append(("github", client.search_github(topic, 20)))
        if "arxiv" in sources:
            tasks.append(("arxiv", client.search_arxiv(topic, 20)))
        
        for name, task in tasks:
            try:
                results = await task
                print(f"  {name}: {len(results)} items")
                all_findings.extend(results)
            except Exception as e:
                print(f"  {name}: Error - {e}")
    
    # 质量评分
    quality = QualityScorer.score(all_findings)
    
    # 保存
    result = ResearchResult(topic=topic, findings=all_findings, quality=quality)
    saved_file = result.save()
    
    # 记录趋势
    analyzer = TrendAnalyzer()
    analyzer.record_topic(topic, all_findings, quality)
    
    print(f"\nQuality Score: {quality['quality_score']:.3f}")
    print(f"Dimensions: {quality['dimensions']}")
    print(f"Saved: {saved_file.name}")
    
    return result

# ════════════════════════════════════════════════════════════════
# 5. 定时任务执行器
# ════════════════════════════════════════════════════════════════

DAILY_TOPICS = [
    "LLM optimization",
    "AI agents",
    "RAG retrieval",
    "model quantization",
    "fine-tuning LLMs",
]

async def run_daily_research():
    """每日定时研究"""
    print(f"\n{'#'*60}")
    print(f"# Daily AutoResearch: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#'*60}")
    
    results = []
    for topic in DAILY_TOPICS:
        try:
            result = await research_topic(topic)
            results.append(result)
            await asyncio.sleep(2)  # 避免 API 限流
        except Exception as e:
            print(f"  [!] Error: {e}")
    
    # 生成趋势报告
    analyzer = TrendAnalyzer()
    trends = analyzer.get_overall_trends()
    
    print(f"\n{'='*50}")
    print("Daily Research Complete!")
    print(f"{'='*50}")
    print(f"Topics researched: {len(results)}")
    print(f"Hot topics: {[t['topic'] for t in trends.get('hot_topics', [])]}")
    
    return results

# ════════════════════════════════════════════════════════════════
# 6. 报告生成
# ════════════════════════════════════════════════════════════════

def generate_report(results: list):
    """生成 Markdown 报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = [
        f"# AutoResearch Daily Report",
        f"",
        f"**Generated**: {timestamp}",
        f"**Topics**: {len(results)}",
        f"",
        f"## Quality Rankings",
        f"",
    ]
    
    # 按质量排序
    sorted_results = sorted(results, key=lambda x: x.quality["quality_score"], reverse=True)
    
    for i, r in enumerate(sorted_results, 1):
        lines.append(f"### {i}. {r.topic}")
        lines.append(f"- **Quality Score**: {r.quality['quality_score']:.3f}")
        lines.append(f"- **Findings**: {r.quality['total']}")
        lines.append(f"- **Dimensions**:")
        for dim, score in r.quality["dimensions"].items():
            lines.append(f"  - {dim}: {score}")
        lines.append("")
    
    # 趋势摘要
    analyzer = TrendAnalyzer()
    trends = analyzer.get_overall_trends()
    
    if trends:
        lines.extend([
            f"## Overall Trends",
            f"",
            f"**Total Researches**: {trends.get('total_researches', 0)}",
            f"",
            f"### Hot Topics",
        ])
        for t in trends.get("hot_topics", []):
            lines.append(f"- {t['topic']}: {t['count']} researches")
        
        lines.append("")
        lines.append("### Top Quality")
        for t in trends.get("top_quality", []):
            lines.append(f"- {t['topic']}: {t['score']:.3f}")
    
    report = "\n".join(lines)
    report_file = REPORTS_DIR / f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport saved: {report_file.name}")
    return report_file

# ════════════════════════════════════════════════════════════════
# 7. 主入口
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.1")
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
            print("No trend data yet. Run some research first!")
        return
    
    if args.daily:
        asyncio.run(run_daily_research())
        return
    
    if args.topic:
        result = asyncio.run(research_topic(args.topic))
        print(f"\nFinal Quality: {result.quality['quality_score']:.3f}")
        return
    
    print("Usage:")
    print("  python autorun_evolve_v4.1.py --topic 'LLM optimization'")
    print("  python autorun_evolve_v4.1.py --daily")
    print("  python autorun_evolve_v4.1.py --trends")

if __name__ == "__main__":
    main()
