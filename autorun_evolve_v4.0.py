#!/usr/bin/env python3
"""
AutoResearch v4.0 — 真实 API 版
接入真实搜索 API：ProSearch + GitHub + HackerNews + ArXiv
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
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
FINDINGS_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 真实 API 客户端
# ════════════════════════════════════════════════════════════════

class RealAPIClient:
    """真实 API 客户端"""
    
    def __init__(self):
        self.session = None
        self.cache_file = CACHE_DIR / "api_cache.json"
        self.api_cache = self._load_cache()
    
    def _load_cache(self):
        if self.cache_file.exists():
            try:
                return json.load(open(self.cache_file))
            except:
                return {}
        return {}
    
    def _save_cache(self):
        json.dump(self.api_cache, open(self.cache_file, 'w'), indent=2)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    # ════════════════════════════════════════════════════════════════
    # 1. ProSearch (中文搜索)
    # ════════════════════════════════════════════════════════════════
    async def search_prosearch(self, query: str, limit: int = 10):
        """ProSearch 搜索"""
        cache_key = f"prosearch:{query}:{limit}"
        if cache_key in self.api_cache:
            return self.api_cache[cache_key]
        
        try:
            # 使用 web_search 工具的真实端点
            url = f"https://duckduckgo.com/?q={query}&format=json"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for i, item in enumerate(data.get('Results', [])[:limit]):
                        results.append({
                            "title": item.get("Text", ""),
                            "url": item.get("FirstURL", ""),
                            "source": "prosearch"
                        })
                    self.api_cache[cache_key] = results
                    self._save_cache()
                    return results
        except Exception as e:
            print(f"  [!] ProSearch error: {e}")
        
        return []
    
    # ════════════════════════════════════════════════════════════════
    # 2. GitHub API
    # ════════════════════════════════════════════════════════════════
    async def search_github(self, query: str, limit: int = 10):
        """GitHub 仓库搜索"""
        cache_key = f"github:{query}:{limit}"
        if cache_key in self.api_cache:
            return self.api_cache[cache_key]
        
        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get('items', [])[:limit]:
                        results.append({
                            "title": item.get("full_name", ""),
                            "url": item.get("html_url", ""),
                            "description": item.get("description", ""),
                            "stars": item.get("stargazers_count", 0),
                            "source": "github"
                        })
                    self.api_cache[cache_key] = results
                    self._save_cache()
                    return results
                elif resp.status == 403:
                    print(f"  [!] GitHub API rate limited")
        except Exception as e:
            print(f"  [!] GitHub error: {e}")
        
        return []
    
    # ════════════════════════════════════════════════════════════════
    # 3. HackerNews API
    # ════════════════════════════════════════════════════════════════
    async def search_hackernews(self, query: str, limit: int = 10):
        """HackerNews 搜索"""
        cache_key = f"hackernews:{query}:{limit}"
        if cache_key in self.api_cache:
            return self.api_cache[cache_key]
        
        try:
            # 获取 Top Stories
            async with self.session.get("https://hacker-news.firebaseio.com/v0/topstories.json", 
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    story_ids = await resp.json()
                    
                    results = []
                    for story_id in story_ids[:30]:  # 获取前30个
                        async with self.session.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as story_resp:
                            if story_resp.status == 200:
                                story = await story_resp.json()
                                if story and query.lower() in story.get("title", "").lower():
                                    results.append({
                                        "title": story.get("title", ""),
                                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                                        "score": story.get("score", 0),
                                        "source": "hackernews"
                                    })
                                    if len(results) >= limit:
                                        break
                    
                    self.api_cache[cache_key] = results
                    self._save_cache()
                    return results
        except Exception as e:
            print(f"  [!] HackerNews error: {e}")
        
        return []
    
    # ════════════════════════════════════════════════════════════════
    # 4. ArXiv API
    # ════════════════════════════════════════════════════════════════
    async def search_arxiv(self, query: str, limit: int = 10):
        """ArXiv 论文搜索"""
        cache_key = f"arxiv:{query}:{limit}"
        if cache_key in self.api_cache:
            return self.api_cache[cache_key]
        
        try:
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # 简单解析 XML
                    results = []
                    import re
                    entries = re.findall(r'<entry>(.*?)</entry>', text, re.DOTALL)
                    for entry in entries[:limit]:
                        title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                        summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                        link = re.search(r'<link.*?href="(.*?)".*?/>', entry)
                        
                        if title:
                            results.append({
                                "title": title.group(1).strip().replace('\n', ' '),
                                "url": link.group(1) if link else "",
                                "abstract": summary.group(1).strip()[:200] if summary else "",
                                "source": "arxiv"
                            })
                    
                    self.api_cache[cache_key] = results
                    self._save_cache()
                    return results
        except Exception as e:
            print(f"  [!] ArXiv error: {e}")
        
        return []

# ════════════════════════════════════════════════════════════════
# 研究引擎
# ════════════════════════════════════════════════════════════════

@dataclass
class ResearchResult:
    topic: str
    round_num: int
    findings: list
    sources_used: list
    
    def save(self):
        """保存发现到文件"""
        fname = FINDINGS_DIR / f"{self.topic.replace(' ', '_')}_{self.round_num}.json"
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump({
                "topic": self.topic,
                "round": self.round_num,
                "timestamp": datetime.now().isoformat(),
                "findings": self.findings,
                "sources": self.sources_used
            }, f, indent=2, ensure_ascii=False)
        return fname

async def run_research(topic: str, sources: list, depth: str):
    """执行真实研究"""
    print(f"\n{'='*60}")
    print(f"  AutoResearch v4.0 | {topic}")
    print(f"  Sources: {sources} | Depth: {depth}")
    print(f"{'='*60}")
    
    limit = {"quick": 5, "standard": 10, "deep": 20}.get(depth, 5)
    
    all_findings = []
    
    async with RealAPIClient() as client:
        # 并行执行所有源
        tasks = []
        if "prosearch" in sources:
            tasks.append(("prosearch", client.search_prosearch(topic, limit)))
        if "github" in sources:
            tasks.append(("github", client.search_github(topic, limit)))
        if "hackernews" in sources:
            tasks.append(("hackernews", client.search_hackernews(topic, limit)))
        if "arxiv" in sources:
            tasks.append(("arxiv", client.search_arxiv(topic, limit)))
        
        # 执行
        for name, task in tasks:
            print(f"\n  >> {name.upper()}...")
            try:
                results = await task
                print(f"     Found: {len(results)} items")
                all_findings.extend(results)
            except Exception as e:
                print(f"     Error: {e}")
    
    # 保存
    result = ResearchResult(
        topic=topic,
        round_num=1,
        findings=all_findings,
        sources_used=sources
    )
    saved_file = result.save()
    
    print(f"\n  [OK] Total findings: {len(all_findings)}")
    print(f"  [OK] Saved to: {saved_file.name}")
    
    # 统计
    if all_findings:
        sources_count = Counter(f.get("source", "unknown") for f in all_findings)
        print(f"\n  Sources breakdown:")
        for src, count in sources_count.most_common():
            print(f"    - {src}: {count}")
    
    return result

# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="AutoResearch v4.0 - Real API")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-s", "--sources", default="prosearch,github,hackernews,arxiv",
                   help="Sources: prosearch,github,hackernews,arxiv")
    p.add_argument("-d", "--depth", default="standard", choices=["quick", "standard", "deep"])
    args = p.parse_args()
    
    if not args.topic:
        print("Usage: python autorun_evolve_v4.0.py <topic> [-s sources] [-d depth]")
        print("\nExamples:")
        print("  python autorun_evolve_v4.0.py 'LLM optimization'")
        print("  python autorun_evolve_v4.0.py 'AI agents' -s github,hackernews -d deep")
        return
    
    sources = args.sources.split(",")
    asyncio.run(run_research(args.topic, sources, args.depth))

if __name__ == "__main__":
    main()
