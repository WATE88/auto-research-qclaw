#!/usr/bin/env python3
"""
autorun_local.py — QClaw AutoResearch 本地优化运行脚本
=====================================================
集成了缓存、历史追踪、趋势分析、Karpagthy 闭环迭代思路的完整研究框架

用法:
    python autorun_local.py "研究主题" [options]

示例:
    python autorun_local.py "AI Agent 最新进展" --depth standard --watch
    python autorun_local.py "Python 技术趋势" --sources prosearch github hackernews
    python autorun_local.py "QClaw" --trend 7 --compare
"""

import os
import sys
import io
import json
import time
import argparse
import hashlib
from datetime import datetime
from pathlib import Path

# ── UTF-8 编码修复（Windows）────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if hasattr(sys.stdin, "buffer"):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# ── 路径配置 ─────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "_cache"
HISTORY_FILE = SCRIPT_DIR / "_research_history.jsonl"
CACHE_DIR.mkdir(exist_ok=True)

PORT = os.getenv("AUTH_GATEWAY_PORT", "19000")

# ─────────────────────────────────────────────────────────────
# 控制台样式
# ─────────────────────────────────────────────────────────────

class Console:
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def print(msg: str, color: str = "", bold: bool = False, dim: bool = False):
        prefix = ""
        if bold: prefix += Console.BOLD
        if dim: prefix += Console.DIM
        if color: prefix += color
        suffix = Console.RESET
        print(f"{prefix}{msg}{suffix}")

    @staticmethod
    def header(msg: str):
        print()
        Console.print("═" * 60, color=Console.CYAN)
        Console.print(f"  {msg}", color=Console.CYAN, bold=True)
        Console.print("═" * 60, color=Console.CYAN)
        print()

    @staticmethod
    def success(msg: str):
        Console.print(f"  ✅ {msg}", color=Console.GREEN)

    @staticmethod
    def info(msg: str):
        Console.print(f"  ℹ️  {msg}", color=Console.CYAN)

    @staticmethod
    def warn(msg: str):
        Console.print(f"  ⚠️  {msg}", color=Console.YELLOW)

    @staticmethod
    def error(msg: str):
        Console.print(f"  ❌ {msg}", color=Console.RED)

    @staticmethod
    def section(msg: str):
        print()
        Console.print(f"  ┌─ {msg}", color=Console.MAGENTA)
        print(f"  │")

    @staticmethod
    def section_end():
        print(f"  │")
        Console.print("  └" + "─" * 52, color=Console.MAGENTA)


# ─────────────────────────────────────────────────────────────
# 缓存工具
# ─────────────────────────────────────────────────────────────

def _cache_key(prefix: str, **kwargs) -> str:
    parts = [prefix]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:16] + "_" + prefix


def cache_get(key: str, ttl: int = 3600):
    path = CACHE_DIR / f"{key}.json"
    if not path.exists(): return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > ttl: return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(key: str, data):
    try:
        (CACHE_DIR / f"{key}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# 数据源采集
# ─────────────────────────────────────────────────────────────

def _spinner(step: str, done: bool = False):
    """进度显示"""
    mark = "✅" if done else "..."
    print(f"\r  🔄 {step:<30} {mark}", end="", flush=True)
    if done:
        print()


def fetch_prosearch(keyword: str, count: int = 10, days: int = 30) -> list[dict]:
    """通过 QClaw ProSearch 获取联网搜索结果"""
    ck = _cache_key("prosearch", keyword=keyword, count=count, days=days)
    cached = cache_get(ck, ttl=1800)
    if cached is not None:
        _spinner(f"ProSearch [{keyword}]", done=True)
        return cached

    import urllib.request
    url = f"http://localhost:{PORT}/proxy/prosearch/search"
    from_time = int(time.time()) - days * 86400
    body = json.dumps({"keyword": keyword, "from_time": from_time, "cnt": count}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    results = []
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            res = json.loads(r.read().decode("utf-8", errors="replace"))
            if res.get("success") and res.get("data", {}).get("docs"):
                results = res["data"]["docs"]
    except Exception as e:
        Console.warn(f"ProSearch 请求失败: {e}")
    cache_set(ck, results)
    _spinner(f"ProSearch [{keyword}]", done=True)
    return results


def fetch_github_trending(language: str = "", limit: int = 8) -> list[dict]:
    """抓取 GitHub Trending"""
    import re, urllib.request
    ck = _cache_key("gh", lang=language)
    cached = cache_get(ck, ttl=900)
    if cached is not None:
        _spinner(f"GitHub Trending [{language or '全部'}]", done=True)
        return cached[:limit]

    url = f"https://github.com/trending{'/' + language if language else ''}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        for a in re.findall(r"<article class=\"Box-row\">(.*?)</article>", html, re.DOTALL)[:15]:
            t = re.search(r'href="(/[^"/]+/[^"/]+)"[^>]*>\s*([^<]{3,200})', a)
            d = re.search(r"<p[^>]*>([^<\n]{10,300})", a)
            s = re.search(r"(\d[\d,]*)\s+stars today", a)
            lang = re.search(r'<span itemprop="programmingLanguage">([^<]+)</span>', a)
            if t:
                items.append({
                    "title": f"github: {t.group(2).strip()}",
                    "url": "https://github.com" + t.group(1),
                    "type": "project",
                    "language": lang.group(1) if lang else "",
                    "description": (d.group(1).strip() if d else ""),
                    "stars_today": s.group(1).replace(",", "") if s else "0",
                    "source": "GitHub",
                })
    except Exception as e:
        Console.warn(f"GitHub 请求失败: {e}")

    cache_set(ck, items)
    _spinner(f"GitHub Trending [{language or '全部'}]", done=True)
    return items[:limit]


def fetch_hackernews(top_n: int = 10) -> list[dict]:
    """抓取 Hacker News Top Stories"""
    import urllib.request
    ck = _cache_key("hn", n=top_n)
    cached = cache_get(ck, ttl=600)
    if cached is not None:
        _spinner(f"Hacker News [Top {top_n}]", done=True)
        return cached

    items = []
    try:
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            ids = json.loads(r.read().decode())
        for iid in ids[:top_n * 2]:
            try:
                req2 = urllib.request.Request(
                    f"https://hacker-news.firebaseio.com/v0/item/{iid}.json",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    item = json.loads(r2.read().decode())
                if item.get("title"):
                    items.append({
                        "title": f"hn: {item['title']}",
                        "url": item.get("url") or f"https://news.ycombinator.com/item?id={iid}",
                        "type": "discussion",
                        "score": item.get("score", 0),
                        "comments": item.get("descendants", 0),
                        "source": "HackerNews",
                    })
                if len(items) >= top_n:
                    break
            except Exception:
                continue
    except Exception as e:
        Console.warn(f"Hacker News 请求失败: {e}")

    cache_set(ck, items)
    _spinner(f"Hacker News [Top {top_n}]", done=True)
    return items


def fetch_arxiv(topic: str, max_results: int = 5) -> list[dict]:
    """搜索 ArXiv 论文"""
    import re, urllib.request, urllib.parse
    ck = _cache_key("arxiv", topic=topic, n=max_results)
    cached = cache_get(ck, ttl=7200)
    if cached is not None:
        _spinner(f"ArXiv [{topic}]", done=True)
        return cached[:max_results]

    query = urllib.parse.quote(topic)
    url = (f"http://export.arxiv.org/api/query"
           f"?search_query=all:{query}&start=0&max_results={max_results}"
           f"&sortBy=submittedDate&sortOrder=descending")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    items = []
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", errors="replace")
        for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
            tm = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            lm = re.search(r"<id>(.*?)</id>", entry)
            sm = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            if tm:
                items.append({
                    "title": f"[论文] {tm.group(1).strip().replace(chr(10), ' ')}",
                    "url": lm.group(1).strip() if lm else "",
                    "type": "paper",
                    "abstract": (sm.group(1).strip()[:200] if sm else "") + "...",
                    "source": "ArXiv",
                })
    except Exception as e:
        Console.warn(f"ArXiv 请求失败: {e}")

    cache_set(ck, items)
    _spinner(f"ArXiv [{topic}]", done=True)
    return items[:max_results]


def fetch_reddit(subreddit: str = "technology", limit: int = 5) -> list[dict]:
    """抓取 Reddit 热帖"""
    import urllib.request
    ck = _cache_key("reddit", sub=subreddit)
    cached = cache_get(ck, ttl=600)
    if cached is not None:
        _spinner(f"Reddit r/{subreddit}", done=True)
        return cached[:limit]

    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "AutoResearchBot/2.1"})
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            if d.get("title"):
                items.append({
                    "title": f"reddit/{subreddit}: {d['title']}",
                    "url": d.get("url", ""),
                    "type": "discussion",
                    "score": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "source": f"Reddit r/{subreddit}",
                })
    except Exception as e:
        Console.warn(f"Reddit 请求失败: {e}")

    cache_set(ck, items)
    _spinner(f"Reddit r/{subreddit}", done=True)
    return items[:limit]


def fetch_producthunt(limit: int = 5) -> list[dict]:
    """抓取 Product Hunt 热门"""
    import re, urllib.request
    ck = _cache_key("ph")
    cached = cache_get(ck, ttl=1800)
    if cached is not None:
        _spinner("Product Hunt", done=True)
        return cached[:limit]

    req = urllib.request.Request(
        "https://www.producthunt.com/",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        for m in re.finditer(
            r'<a[^>]+href="/posts/[^"]+"[^>]*>\s*<[^>]*data-test="post-card-title[^"]*"[^>]*>([^<]{5,200})</',
            html, re.DOTALL
        ):
            title = m.group(1).strip()
            if title and len(title) > 5:
                items.append({
                    "title": f"ph: {title}",
                    "url": "https://www.producthunt.com",
                    "type": "product",
                    "source": "ProductHunt",
                })
    except Exception as e:
        Console.warn(f"ProductHunt 请求失败: {e}")

    cache_set(ck, items)
    _spinner("Product Hunt", done=True)
    return items[:limit]


# ─────────────────────────────────────────────────────────────
# 核心研究引擎
# ─────────────────────────────────────────────────────────────

ALL_SOURCES = {
    "prosearch": ("ProSearch 联网搜索", True),
    "github": ("GitHub Trending", True),
    "hackernews": ("Hacker News", True),
    "arxiv": ("ArXiv 学术论文", True),
    "reddit": ("Reddit 技术社区", True),
    "producthunt": ("Product Hunt", True),
}

DEPTH_CONFIG = {
    "quick":    {"arxiv": 3, "github": 5, "hackernews": 5,  "reddit": 3, "producthunt": 3},
    "standard": {"arxiv": 5, "github": 8, "hackernews": 10, "reddit": 5, "producthunt": 5},
    "deep":     {"arxiv": 10, "github": 15, "hackernews": 20, "reddit": 8, "producthunt": 8},
}


def run_research(topic: str, sources: list, depth: str) -> dict:
    """执行完整研究任务"""
    cfg = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["standard"])
    findings = []
    active_sources = []

    # 并行采集（简单串行，真实并行用 asyncio）
    for src in sources:
        if src == "prosearch":
            _spinner(f"ProSearch [{topic}]", done=False)
            results = fetch_prosearch(topic)
            for d in results:
                findings.append({
                    "title": d.get("title", ""),
                    "url": d.get("url", ""),
                    "type": "web_search",
                    "site": d.get("site", ""),
                    "date": d.get("date", ""),
                    "snippet": d.get("passage", "")[:400],
                    "source": "ProSearch",
                })
            active_sources.append("ProSearch")

        elif src == "github":
            results = fetch_github_trending(limit=cfg["github"])
            findings.extend(results)
            active_sources.append("GitHub")

        elif src == "hackernews":
            results = fetch_hackernews(top_n=cfg["hackernews"])
            findings.extend(results)
            active_sources.append("Hacker News")

        elif src == "arxiv":
            results = fetch_arxiv(topic, max_results=cfg["arxiv"])
            findings.extend(results)
            active_sources.append("ArXiv")

        elif src == "reddit":
            results = fetch_reddit(limit=cfg["reddit"])
            findings.extend(results)
            active_sources.append("Reddit")

        elif src == "producthunt":
            results = fetch_producthunt(limit=cfg["producthunt"])
            findings.extend(results)
            active_sources.append("Product Hunt")

    # 去重
    seen = set()
    unique = []
    for f in findings:
        url = f.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(f)
        elif not url:
            unique.append(f)
    findings = unique

    # 统计
    type_dist = {}
    for f in findings:
        t = f.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1

    # 热度排序
    ranked = []
    for f in findings:
        s = f.get("score") or f.get("stars_today") or "0"
        try:
            s = int(str(s).replace(",", ""))
        except Exception:
            s = 0
        if s > 0:
            ranked.append((f.get("title", ""), s, f.get("url", ""), f.get("type", "")))

    ranked.sort(key=lambda x: x[1], reverse=True)
    top5 = ranked[:5]

    # 保存历史记录
    record = {
        "ts": datetime.now().isoformat(),
        "topic": topic,
        "sources": sources,
        "depth": depth,
        "total_findings": len(findings),
        "type_distribution": type_dist,
        "top_item": {"title": top5[0][0], "score": top5[0][1], "url": top5[0][2]} if top5 else None,
    }
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        record["saved"] = True
    except Exception as e:
        record["saved"] = False
        Console.warn(f"历史记录保存失败: {e}")

    return {
        "topic": topic,
        "depth": depth,
        "active_sources": active_sources,
        "total_findings": len(findings),
        "type_distribution": type_dist,
        "findings": findings,
        "top5": [{"title": t, "score": s, "url": u, "type": ty} for t, s, u, ty in top5],
        "history_saved": record.get("saved", False),
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# 报告生成
# ─────────────────────────────────────────────────────────────

def generate_report(result: dict) -> str:
    """生成 Markdown 格式研究报告"""
    lines = [
        f"# 🔬 AutoResearch 研究报告",
        "",
        f"**主题**: {result['topic']}",
        f"**深度**: {result['depth']}",
        f"**信息源**: {', '.join(result['active_sources'])}",
        f"**生成时间**: {result['timestamp']}",
        "",
        "---",
        "",
    ]

    # 概览
    lines += [
        "## 📊 概览",
        "",
        f"- **总信息量**: {result['total_findings']} 条（已去重）",
        f"- **活跃信息源**: {len(result['active_sources'])} 个",
        "",
    ]

    # 类型分布
    if result["type_distribution"]:
        lines.append("### 类型分布")
        for t, n in sorted(result["type_distribution"].items(), key=lambda x: -x[1]):
            bar = "█" * min(n, 20)
            lines.append(f"- **{t}**: {bar} ({n})")
        lines.append("")

    # TOP 5 热门
    if result["top5"]:
        lines += [
            "## 🔥 TOP 5 热门内容",
            "",
        ]
        for i, item in enumerate(result["top5"], 1):
            url_md = f"[链接]({item['url']})" if item["url"] else "无链接"
            lines.append(f"{i}. **{item['title']}**")
            lines.append(f"   - 热度: ⭐ {item['score']:,} | 类型: {item['type']} | {url_md}")
        lines.append("")

    # 关键洞察
    lines += [
        "## 💡 关键洞察",
        "",
        f"1. 「{result['topic']}」在 {len(result['active_sources'])} 个平台均有内容覆盖",
        f"2. 最高热度内容达 ⭐ {result['top5'][0]['score']:,}（如有评分数据）" if result["top5"] else "",
        f"3. 共发现 **{result['total_findings']} 条**相关信息",
        "",
    ]

    # 完整列表（简化）
    if result["findings"]:
        lines += [
            "---",
            "",
            "## 📋 完整信息列表",
            "",
        ]
        shown = 0
        for f in result["findings"][:30]:
            title = f.get("title", "N/A")
            url = f.get("url", "")
            site = f.get("site") or f.get("source", "")
            snippet = (f.get("snippet") or f.get("abstract") or f.get("description") or "")[:120]
            lines.append(f"- **{title}**  `[{site}]`")
            if snippet:
                lines.append(f"  > {snippet}...")
            shown += 1
            if shown >= 30:
                lines.append(f"\n_...还有 {len(result['findings']) - 30} 条未显示_")
                break

    lines += [
        "",
        "---",
        f"✅ AutoResearch | 研究历史已保存 | {result['timestamp']}",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 趋势分析
# ─────────────────────────────────────────────────────────────

def show_trend(keyword: str, days: int = 7):
    """显示关键词趋势"""
    records = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        r = json.loads(line)
                        if not keyword or keyword.lower() in r.get("topic", "").lower():
                            records.append(r)
                    except Exception:
                        continue
        except Exception:
            pass

    if not records:
        Console.warn(f"暂无历史记录，使用 `autorun_local.py \"{keyword}\"` 开始第一次研究")
        return

    # 按天统计
    cutoff = time.time() - days * 86400
    recent = [
        r for r in records
        if time.mktime(datetime.fromisoformat(r["ts"]).timetuple()) > cutoff
    ]

    by_day = {}
    for r in recent:
        day = r["ts"][:10]
        by_day.setdefault(day, []).append(r["total_findings"])

    day_stats = [
        {"date": d, "count": len(items), "avg": sum(items) / len(items)}
        for d, items in sorted(by_day.items())
    ]

    if len(day_stats) >= 2:
        diff = day_stats[-1]["avg"] - day_stats[0]["avg"]
        if diff > 0:
            trend_icon = "📈"
            trend_label = "上升"
        elif diff < 0:
            trend_icon = "📉"
            trend_label = "下降"
        else:
            trend_icon = "➡️"
            trend_label = "平稳"
    else:
        trend_icon = "📊"
        trend_label = "数据不足"

    Console.header(f"趋势分析: {keyword}（最近 {days} 天）")
    Console.print(f"  趋势: {trend_icon} {trend_label}", bold=True)
    Console.print(f"  近期研究次数: {len(recent)} 次")

    if day_stats:
        Console.section("每日统计")
        for ds in day_stats:
            bar = "█" * min(int(ds["avg"]), 30)
            Console.print(f"  {ds['date']}  {bar}  (平均 {ds['avg']:.0f} 条/次, {ds['count']} 次)")
        Console.section_end()

    Console.info(f"历史记录总数: {len(records)}")


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="QClaw AutoResearch 本地优化运行脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python autorun_local.py "AI Agent 最新进展"
  python autorun_local.py "Python" --depth deep
  python autorun_local.py "QClaw" --sources prosearch github hackernews
  python autorun_local.py "QClaw" --trend 7
  python autorun_local.py "QClaw" --history 10
  python autorun_local.py "QClaw" --watch
        """
    )
    parser.add_argument("topic", nargs="?", default="", help="研究主题（留空则显示趋势）")
    parser.add_argument("--depth", "-d", default="standard",
                        choices=["quick", "standard", "deep"], help="研究深度")
    parser.add_argument("--sources", "-s", nargs="+",
                        default=["prosearch", "github", "hackernews"],
                        help="信息源（默认: prosearch github hackernews）")
    parser.add_argument("--trend", "-t", type=int, metavar="DAYS",
                        help="显示最近 N 天的趋势统计")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="与上次研究结果对比")
    parser.add_argument("--history", nargs="?", const="5", type=int, metavar="N",
                        help="显示最近 N 条研究历史")
    parser.add_argument("--save", action="store_true",
                        help="保存报告到文件")
    parser.add_argument("--watch", action="store_true",
                        help="持续监控模式（每小时重复研究）")

    args = parser.parse_args()
    t0 = time.time()

    # 趋势模式
    if args.trend:
        show_trend(args.topic or "", days=args.trend)
        return

    # 历史模式
    if args.history is not None:
        show_history(args.history)
        return

    # 研究主题为空？
    if not args.topic:
        Console.warn("请提供研究主题，或使用 --trend 查看趋势")
        Console.info("示例: python autorun_local.py \"AI助手最新进展\"")
        return

    # ── 展示来源信息 ──────────────────────────────────────────
    src_labels = {
        "prosearch": "🔍 ProSearch",
        "github": "📦 GitHub",
        "hackernews": "💬 HN",
        "arxiv": "📚 ArXiv",
        "reddit": "🌐 Reddit",
        "producthunt": "🚀 PH",
    }
    active = [s for s in args.sources if s in src_labels]
    depth_labels = {"quick": "🔹 快速扫描", "standard": "🔸 标准研究", "deep": "🔶 深度研究"}

    Console.header(f"AutoResearch | {depth_labels[args.depth]}")
    Console.print(f"  主题: {args.topic}", bold=True)
    Console.print(f"  信息源: {' | '.join(src_labels.get(s, s) for s in active)}")
    Console.print(f"  深度: {args.depth}")

    # ── 执行研究 ──────────────────────────────────────────────
    print()
    result = run_research(args.topic, active, args.depth)
    elapsed = time.time() - t0

    print()
    Console.success(f"研究完成！收集 {result['total_findings']} 条信息（耗时 {elapsed:.1f}s）")
    if result.get("history_saved"):
        Console.success("历史记录已保存")

    # ── 报告输出 ──────────────────────────────────────────────
    report = generate_report(result)
    print()
    Console.header("研究报告")
    print(report)

    # 保存报告
    if args.save:
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in result["topic"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = SCRIPT_DIR / f"report_{safe_name}_{ts}.md"
        report_path.write_text(report, encoding="utf-8")
        Console.success(f"报告已保存: {report_path}")

    # 对比模式
    if args.compare:
        compare_with_previous(result["topic"])

    # 持续监控模式
    if args.watch:
        print()
        Console.info("持续监控模式已开启（Ctrl+C 退出）")
        print()
        while True:
            time.sleep(3600)  # 每小时重复
            Console.info(f"\n[{datetime.now().strftime('%H:%M:%S')}] 重新执行研究...")
            r2 = run_research(result["topic"], active, args.depth)
            Console.success(f"完成！收集 {r2['total_findings']} 条 | 历史已更新")


def show_history(limit: int = 5):
    """显示研究历史"""
    records = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines[-limit:]):
                line = line.strip()
                if not line: continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass

    Console.header(f"研究历史（最近 {limit} 条）")
    if not records:
        Console.warn("暂无历史记录")
        return

    for i, r in enumerate(records, 1):
        ts = r.get("ts", "")[11:19]
        total = r.get("total_findings", 0)
        top = r.get("top_item", {})
        top_score = top.get("score", "-") if top else "-"
        Console.print(f"  {i}. [{ts}] {r.get('topic', '')}", bold=True)
        Console.print(f"     总计: {total} 条 | 最高热度: ⭐ {top_score} | 深度: {r.get('depth', '')}")
        dist = r.get("type_distribution", {})
        if dist:
            items = ", ".join(f"{k}: {v}" for k, v in list(dist.items())[:4])
            Console.print(f"     {items}", dim=True)
    print()


def compare_with_previous(topic: str):
    """与上次研究对比"""
    records = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        r = json.loads(line)
                        if topic.lower() in r.get("topic", "").lower():
                            records.append(r)
                    except Exception:
                        continue
        except Exception:
            pass

    if len(records) < 2:
        Console.warn("历史记录不足（至少需要 2 条），无法对比")
        return

    prev = records[-2]
    curr = records[-1]

    Console.header("对比分析")
    Console.print(f"  上次研究: {prev['ts'][11:19]} → {curr['ts'][11:19]}", bold=True)
    diff = curr.get("total_findings", 0) - prev.get("total_findings", 0)
    icon = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
    Console.print(f"  信息量变化: {icon} {diff:+d} 条（{prev.get('total_findings', 0)} → {curr.get('total_findings', 0)}）")

    # 类型对比
    pd = prev.get("type_distribution", {})
    cd = curr.get("type_distribution", {})
    all_types = set(pd) | set(cd)
    if all_types:
        Console.section("类型分布变化")
        for t in sorted(all_types):
            pv = pd.get(t, 0)
            cv = cd.get(t, 0)
            d = cv - pv
            icon2 = "↑" if d > 0 else "↓" if d < 0 else "="
            Console.print(f"  {t}: {pv} → {cv}  {icon2}{abs(d)}")
        Console.section_end()
    print()


if __name__ == "__main__":
    main()
