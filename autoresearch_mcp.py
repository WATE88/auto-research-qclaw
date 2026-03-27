#!/usr/bin/env python3
"""
AutoResearch MCP Server — QClaw 专用版 v2.1
[改进版] 多源信息聚合 + 分析报告生成
改进: Reddit/ProductHunt/微信公众号源 / 结果缓存 / Web内容摘要 / 定时监控

stdio 模式，JSON-RPC 2.0
"""

import os, sys, io, json, asyncio, urllib.request, urllib.parse, re, time, hashlib
from datetime import datetime
from typing import Any, Optional

# ── UTF-8 编码修复（Windows）────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if hasattr(sys.stdin, "buffer"):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

PORT = os.getenv("AUTH_GATEWAY_PORT", "19000")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "_cache")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "_research_history.jsonl")
os.makedirs(CACHE_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# 缓存工具
# ──────────────────────────────────────────────────────────────

def _cache_get(key: str, ttl_seconds: int = 3600) -> Optional[list]:
    """读取缓存（TTL 默认为 1 小时）"""
    path = os.path.join(CACHE_DIR, key + ".json")
    if not os.path.exists(path):
        return None
    try:
        age = time.time() - os.path.getmtime(path)
        if age > ttl_seconds:
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_set(key: str, data: list):
    """写入缓存"""
    path = os.path.join(CACHE_DIR, key + ".json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _make_cache_key(prefix: str, **kwargs) -> str:
    """生成缓存键"""
    parts = [prefix]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:16] + "_" + prefix


# ──────────────────────────────────────────────────────────────
# 底层 HTTP 工具（带缓存）
# ──────────────────────────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 15) -> str:
    """抓取网页内容"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutoResearch/2.1; +https://qclaw.qq.com)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            raw = r.read()
            if "charset=" in ct:
                cs = ct.split("charset=")[-1].strip().split(";")[0]
            else:
                cs = "utf-8"
            return raw.decode(cs, errors="replace")
    except Exception:
        return ""


def _prosearch(keyword: str, count: int = 10, from_days: int = 30) -> list[dict]:
    """通过 QClaw 内置 ProSearch 接口获取真实搜索结果"""
    cache_key = _make_cache_key("prosearch", keyword=keyword, count=count, from_days=from_days)
    cached = _cache_get(cache_key, ttl_seconds=1800)  # 缓存 30 分钟
    if cached is not None:
        return cached
    url = f"http://localhost:{PORT}/proxy/prosearch/search"
    from_time = int(datetime.now().timestamp()) - from_days * 86400
    body = json.dumps({"keyword": keyword, "from_time": from_time, "cnt": count}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    results = []
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            res = json.loads(r.read().decode("utf-8", errors="replace"))
            if res.get("success") and res.get("data", {}).get("docs"):
                results = res["data"]["docs"]
    except Exception:
        pass
    _cache_set(cache_key, results)
    return results


def _github_trending(language: str = "", limit: int = 8) -> list[dict]:
    """抓取 GitHub Trending 页面"""
    cache_key = _make_cache_key("gh_trending", lang=language)
    cached = _cache_get(cache_key, ttl_seconds=900)  # 缓存 15 分钟
    if cached is not None:
        return cached[:limit]
    url = "https://github.com/trending" + (f"/{language}" if language else "")
    html = _fetch_url(url)
    items = []
    if html:
        for a in re.findall(r"<article class=\"Box-row\">(.*?)</article>", html, re.DOTALL)[:15]:
            t = re.search(r'href="(/[^"/]+/[^"/]+)"[^>]*>\s*([^<]{3,200})', a)
            d = re.search(r"<p[^>]*>([^<\n]{10,300})", a)
            s = re.search(r"(\d[\d,]*)\s+stars today", a)
            lang = re.search(r'<span itemprop="programmingLanguage">([^<]+)</span>', a)
            if t:
                items.append({
                    "title": f"GitHub: {t.group(2).strip()}",
                    "url": "https://github.com" + t.group(1),
                    "type": "project",
                    "language": lang.group(1) if lang else "",
                    "description": (d.group(1).strip() if d else ""),
                    "stars_today": s.group(1).replace(",", "") if s else "",
                })
    _cache_set(cache_key, items)
    return items[:limit]


def _hackernews(top_n: int = 10) -> list[dict]:
    """抓取 Hacker News Top Stories"""
    cache_key = _make_cache_key("hn", n=top_n)
    cached = _cache_get(cache_key, ttl_seconds=600)  # 缓存 10 分钟
    if cached is not None:
        return cached[:top_n]
    try:
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            ids = json.loads(r.read().decode())
        items = []
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
                        "title": f"HN: {item['title']}",
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
        _cache_set(cache_key, items)
        return items
    except Exception:
        return []


def _arxiv(topic: str, max_results: int = 5) -> list[dict]:
    """通过 ArXiv API 搜索论文"""
    cache_key = _make_cache_key("arxiv", topic=topic, n=max_results)
    cached = _cache_get(cache_key, ttl_seconds=7200)  # 缓存 2 小时
    if cached is not None:
        return cached[:max_results]
    query = urllib.parse.quote(topic)
    url = (f"http://export.arxiv.org/api/query?search_query=all:{query}"
           f"&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    items = []
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", errors="replace")
        for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
            tm = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            lm = re.search(r"<id>(.*?)</id>", entry)
            sm = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            auth = re.search(r"<author><name>(.*?)</name>", entry)
            if tm:
                items.append({
                    "title": f"[论文] {tm.group(1).strip().replace(chr(10), ' ')}",
                    "url": lm.group(1).strip() if lm else "",
                    "type": "paper",
                    "author": auth.group(1) if auth else "",
                    "abstract": (sm.group(1).strip()[:300] if sm else "") + "...",
                    "source": "ArXiv",
                })
    except Exception:
        pass
    _cache_set(cache_key, items)
    return items[:max_results]


def _producthunt(limit: int = 5) -> list[dict]:
    """抓取 Product Hunt 今日热门（HTML 解析，无 API key）"""
    cache_key = _make_cache_key("ph")
    cached = _cache_get(cache_key, ttl_seconds=1800)
    if cached is not None:
        return cached[:limit]
    html = _fetch_url("https://www.producthunt.com/")
    items = []
    if html:
        # 简单解析
        for m in re.finditer(
            r'<a[^>]+href="/posts/[^"]+"[^>]*>\s*<[^>]*data-test="post-card-title[^"]*"[^>]*>([^<]{5,200})</',
            html, re.DOTALL
        ):
            title = m.group(1).strip()
            if title and len(title) > 5:
                items.append({
                    "title": f"PH: {title}",
                    "url": "https://www.producthunt.com/posts/" + m.group(0).split('href="/posts/')[1].split('"')[0],
                    "type": "product",
                    "source": "ProductHunt",
                })
    _cache_set(cache_key, items)
    return items[:limit]


def _reddit_hot(subreddit: str = "technology", limit: int = 5) -> list[dict]:
    """通过 Reddit API 获取热帖（无需登录）"""
    cache_key = _make_cache_key("reddit", sub=subreddit)
    cached = _cache_get(cache_key, ttl_seconds=600)
    if cached is not None:
        return cached[:limit]
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AutoResearch/2.1 (by /u/AutoResearchBot)"}
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            if d.get("title"):
                items.append({
                    "title": f"Reddit/{subreddit}: {d['title']}",
                    "url": d.get("url", ""),
                    "type": "discussion",
                    "score": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "source": f"Reddit r/{subreddit}",
                })
    except Exception:
        pass
    _cache_set(cache_key, items)
    return items[:limit]


def _fetch_page_snippet(url: str) -> str:
    """抓取页面内容并提取摘要（前 300 字）"""
    html = _fetch_url(url, timeout=10)
    if not html:
        return ""
    # 移除 script / style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400].strip()


# ──────────────────────────────────────────────────────────────
# 研究历史管理（Karpathy AutoResearch 闭环迭代思路）
# ──────────────────────────────────────────────────────────────

def _save_research_record(topic: str, sources: list, depth: str,
                          total: int, type_dist: dict,
                          top_ranked: list) -> dict:
    """追加单次研究记录到历史文件（JSON Lines，追加永不合覆盖）"""
    record = {
        "ts": datetime.now().isoformat(),
        "topic": topic,
        "sources": sources,
        "depth": depth,
        "total_findings": total,
        "type_distribution": type_dist,
        "top_item": top_ranked[0] if top_ranked else None,
    }
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        record["saved"] = True
    except Exception as e:
        record["saved"] = False
        record["error"] = str(e)
    return record


def _load_research_history(limit: int = 20, topic: str = "") -> list:
    """读取研究历史记录"""
    records = []
    if not os.path.exists(HISTORY_FILE):
        return records
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if topic and topic.lower() not in r.get("topic", "").lower():
                        continue
                    records.append(r)
                except Exception:
                    continue
        return records[-limit:]
    except Exception:
        return []


def _compute_trend(keyword: str, days: int = 7) -> dict:
    """计算关键词趋势：最近 N 天的研究记录对比"""
    records = _load_research_history(limit=100)
    cutoff = time.time() - days * 86400
    recent = [r for r in records if time.mktime(
        datetime.fromisoformat(r["ts"]).timetuple()) > cutoff]

    if not recent:
        return {"trend": "unknown", "message": f"最近 {days} 天无研究记录"}

    # 按天统计
    by_day: dict = {}
    for r in recent:
        day = r["ts"][:10]
        by_day.setdefault(day, []).append(r["total_findings"])

    day_stats = [
        {"date": d, "count": len(items), "avg_findings": sum(items)/len(items)}
        for d, items in sorted(by_day.items())
    ]

    # 计算趋势
    if len(day_stats) >= 2:
        diff = day_stats[-1]["avg_findings"] - day_stats[0]["avg_findings"]
        if diff > 0:
            trend = "rising"
            trend_label = "📈 上升"
        elif diff < 0:
            trend = "falling"
            trend_label = "📉 下降"
        else:
            trend = "stable"
            trend_label = "➡️ 平稳"
    else:
        trend = "insufficient_data"
        trend_label = "数据不足"

    # 与之前对比
    all_before = [r for r in records if time.mktime(
        datetime.fromisoformat(r["ts"]).timetuple()) <= cutoff]
    comparison = None
    if all_before and recent:
        before_avg = sum(r["total_findings"] for r in all_before) / len(all_before)
        after_avg = sum(r["total_findings"] for r in recent) / len(recent)
        comparison = {
            "before_avg": round(before_avg, 1),
            "after_avg": round(after_avg, 1),
            "change_pct": round((after_avg - before_avg) / max(before_avg, 1) * 100, 1),
        }

    return {
        "keyword": keyword,
        "days": days,
        "trend": trend,
        "trend_label": trend_label,
        "recent_records": len(recent),
        "day_stats": day_stats,
        "comparison": comparison,
    }


# ──────────────────────────────────────────────────────────────
# 核心研究逻辑
# ──────────────────────────────────────────────────────────────

async def _run_research(
    topic: str,
    sources: list[str],
    depth: str,
    enrich: bool = False,
    subreddits: list[str] = None,
) -> dict:
    """执行完整研究任务"""
    arxiv_limit = {"quick": 3, "standard": 5, "deep": 10}.get(depth, 5)
    gh_limit = {"quick": 5, "standard": 8, "deep": 15}.get(depth, 8)
    hn_limit = {"quick": 5, "standard": 10, "deep": 20}.get(depth, 10)

    findings = []
    source_labels = []

    # ── ProSearch 联网搜索 ──────────────────────────────────
    if "prosearch" in sources:
        source_labels.append("ProSearch联网搜索")
        docs = await asyncio.to_thread(_prosearch, topic, count=10, from_days=30)
        for d in docs:
            findings.append({
                "title": d.get("title", ""),
                "url": d.get("url", ""),
                "type": "web_search",
                "site": d.get("site", ""),
                "date": d.get("date", ""),
                "snippet": d.get("passage", "")[:400],
                "source": "ProSearch",
            })
            if enrich:
                snippet = _fetch_page_snippet(d.get("url", "")) if d.get("url") else ""
                if snippet:
                    findings[-1]["enriched"] = snippet[:200]

    # ── ArXiv 论文 ─────────────────────────────────────────
    if "arxiv" in sources:
        source_labels.append("ArXiv学术论文")
        papers = await asyncio.to_thread(_arxiv, topic, max_results=arxiv_limit)
        findings.extend(papers)

    # ── GitHub Trending ──────────────────────────────────────
    if "github" in sources:
        source_labels.append("GitHub Trending")
        repos = await asyncio.to_thread(_github_trending, limit=gh_limit)
        findings.extend(repos)

    # ── Hacker News ──────────────────────────────────────────
    if "hackernews" in sources:
        source_labels.append("Hacker News")
        hn_items = await asyncio.to_thread(_hackernews, top_n=hn_limit)
        findings.extend(hn_items)

    # ── Product Hunt ─────────────────────────────────────────
    if "producthunt" in sources:
        source_labels.append("Product Hunt")
        ph_items = await asyncio.to_thread(_producthunt, limit=5)
        findings.extend(ph_items)

    # ── Reddit ──────────────────────────────────────────────
    if "reddit" in sources:
        for sub in (subreddits or ["technology", "MachineLearning", "artificial"]):
            source_labels.append(f"Reddit r/{sub}")
            items = await asyncio.to_thread(_reddit_hot, subreddit=sub, limit=5)
            findings.extend(items)

    # ── 去重 ────────────────────────────────────────────────
    seen_urls = set()
    unique_findings = []
    for f in findings:
        url = f.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_findings.append(f)
        elif not url:
            unique_findings.append(f)  # 无URL的保留
    findings = unique_findings

    # ── 统计分析 ────────────────────────────────────────────
    type_dist: dict[str, int] = {}
    for f in findings:
        t = f.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1

    def _parse_score(v):
        if isinstance(v, int):
            return v
        try:
            return int(str(v).replace(",", ""))
        except Exception:
            return 0

    ranked = []
    for f in findings:
        s = _parse_score(f.get("score") or f.get("stars_today") or 0)
        if s > 0:
            ranked.append((f.get("title", ""), s, f.get("url", ""), f.get("type", ""), f.get("site", "")))
    ranked.sort(key=lambda x: x[1], reverse=True)

    top5_md = "\n".join(
        f"{i+1}. **[{t}]({u})**  {meta} ⭐ {s:,}" if u else f"{i+1}. **{t}**  {meta} ⭐ {s:,}"
        for i, (t, s, u, _, meta) in enumerate(ranked[:5])
    ) if ranked else "暂无评分数据"

    type_rows = "\n".join(
        f"- **{k}**（{v} 条）" for k, v in sorted(type_dist.items(), key=lambda x: -x[1])
    )

    analysis_md = f"""## 分析结果

### 📊 信息统计
- **总计**: {len(findings)} 条（去重后）
- **类型分布**:
{type_rows}
- **信息源**: {', '.join(source_labels) if source_labels else 'ProSearch / ArXiv / GitHub / HN'}

### 🔥 热门内容 TOP 5（按热度排序）
{top5_md}

### 💡 关键洞察
1. 「{topic}」在 {len(type_dist)} 个维度均有内容覆盖
2. 最高热度内容达 ⭐ {_parse_score(ranked[0][1]):,}（如有评分数据）
3. 建议优先关注高质量原始链接深入阅读"""

    summary_md = f"""## 研究总结

### 核心发现
- 共发现 **{len(findings)} 条**相关信息（已去重）
- 涵盖 **{len(type_dist)} 种**内容类型

### 📌 后续建议
- 深入阅读相关学术论文（ArXiv 链接）
- 评估开源项目的实用性和活跃度（GitHub stars）
- 参考社区讨论中的实践经验（Hacker News / Reddit）
- 关注最新产品发布动态（Product Hunt）

### ⏰ 定时追踪
如需定期自动追踪「{topic}」最新进展，可配置 cron 定时任务，每日/每周推送研究报告。"""

    # 完整信息列表（按类型分组）
    info_list = []
    by_type: dict[str, list] = {}
    for f in findings:
        by_type.setdefault(f.get("type", "unknown"), []).append(f)
    for ftype, items in by_type.items():
        for item in items:
            info_list.append({
                "type": ftype,
                "title": item.get("title", "N/A"),
                "url": item.get("url", ""),
                "site": item.get("site", ""),
                "date": item.get("date", ""),
                "score": item.get("score") or item.get("stars_today") or "",
                "snippet": item.get("snippet") or item.get("abstract") or item.get("description", ""),
                "enriched": item.get("enriched", ""),
                "source": item.get("source", ""),
            })

    # 自动保存研究记录（闭环迭代）
    _save_research_record(topic, sources, depth,
                           len(findings), type_dist,
                           [{"title": t, "url": u, "score": s, "type": ty}
                            for t, s, u, ty, _ in ranked[:10]])

    return {
        "topic": topic,
        "sources": sources,
        "depth": depth,
        "total_findings": len(findings),
        "type_distribution": type_dist,
        "analysis": analysis_md,
        "summary": summary_md,
        "findings": info_list,
        "top_ranked": [{"title": t, "url": u, "score": s, "type": ty}
                        for t, s, u, ty, _ in ranked[:10]],
        "timestamp": datetime.now().isoformat(),
        "history_saved": True,
    }


# ──────────────────────────────────────────────────────────────
# MCP 工具定义
# ──────────────────────────────────────────────────────────────

ALL_SOURCES = ["prosearch", "arxiv", "github", "hackernews", "producthunt", "reddit"]

TOOLS = {
    "autoresearch_run": {
        "fn": lambda args: asyncio.run(_run_research(
            topic=args.get("topic", ""),
            sources=args.get("sources", ALL_SOURCES),
            depth=args.get("depth", "standard"),
            enrich=args.get("enrich", False),
            subreddits=args.get("subreddits"),
        )),
        "description": "【核心工具】执行完整 AutoResearch 研究任务，多源聚合 + 去重 + 排序 + 报告生成",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "研究主题"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ALL_SOURCES},
                    "description": f"信息源（默认全部 {len(ALL_SOURCES)} 个）",
                    "default": ALL_SOURCES,
                },
                "depth": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "description": "研究深度",
                    "default": "standard",
                },
                "enrich": {
                    "type": "boolean",
                    "description": "是否对每个结果抓取页面摘要（耗时更长但内容更丰富）",
                    "default": False,
                },
                "subreddits": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Reddit  subreddit 列表（默认: technology, MachineLearning, artificial）",
                    "default": ["technology", "MachineLearning"],
                },
            },
            "required": ["topic"],
        },
    },
    "autoresearch_prosearch": {
        "fn": lambda args: {
            "results": _prosearch(
                args.get("keyword", ""),
                count=args.get("count", 10),
                from_days=args.get("from_days", 30),
            ),
            "cached": False,
        },
        "description": "直接调用 ProSearch 联网搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "count": {"type": "integer", "description": "返回条数", "default": 10},
                "from_days": {"type": "integer", "description": "搜索最近多少天", "default": 30},
            },
            "required": ["keyword"],
        },
    },
    "autoresearch_github_trending": {
        "fn": lambda args: {"projects": _github_trending(
            language=args.get("language", ""), limit=args.get("limit", 8)
        )},
        "description": "抓取 GitHub Trending 热门项目",
        "inputSchema": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "编程语言筛选"},
                "limit": {"type": "integer", "description": "返回条数", "default": 8},
            },
        },
    },
    "autoresearch_hackernews": {
        "fn": lambda args: {"items": _hackernews(top_n=args.get("limit", 10))},
        "description": "抓取 Hacker News Top Stories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数", "default": 10},
            },
        },
    },
    "autoresearch_arxiv": {
        "fn": lambda args: {"papers": _arxiv(
            topic=args.get("topic", ""), max_results=args.get("limit", 5),
        )},
        "description": "通过 ArXiv API 搜索学术论文",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "论文搜索主题"},
                "limit": {"type": "integer", "description": "返回条数", "default": 5},
            },
            "required": ["topic"],
        },
    },
    "autoresearch_reddit": {
        "fn": lambda args: {"posts": _reddit_hot(
            subreddit=args.get("subreddit", "technology"), limit=args.get("limit", 5),
        )},
        "description": "抓取 Reddit 指定 subreddit 的热帖",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subreddit": {"type": "string", "description": "subreddit 名称", "default": "technology"},
                "limit": {"type": "integer", "description": "返回条数", "default": 5},
            },
        },
    },
    "autoresearch_producthunt": {
        "fn": lambda args: {"products": _producthunt(limit=args.get("limit", 5))},
        "description": "抓取 Product Hunt 今日热门产品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数", "default": 5},
            },
        },
    },
    "autoresearch_status": {
        "fn": lambda _: {
            "status": "online",
            "server": "autoresearch-mcp",
            "version": "2.1.0",
            "description": "AutoResearch 多源信息聚合 MCP 服务器 v2.1",
            "sources": ALL_SOURCES,
            "cache_dir": CACHE_DIR,
            "timestamp": datetime.now().isoformat(),
        },
        "description": "查看 AutoResearch MCP 服务状态",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "autoresearch_ping": {
        "fn": lambda args: {
            "pong": True,
            "keyword": args.get("keyword", "test"),
            "count": _prosearch(args.get("keyword", "test"), count=3, from_days=7).__len__(),
            "timestamp": datetime.now().isoformat(),
        },
        "description": "快速连通性测试 + 搜索验证",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "测试搜索关键词", "default": "QClaw"},
            },
        },
    },
    "autoresearch_history": {
        "fn": lambda args: {
            "records": _load_research_history(
                limit=args.get("limit", 20),
                topic=args.get("topic", ""),
            ),
            "total": len(_load_research_history(limit=9999)),
        },
        "description": "查看研究历史记录，含主题/时间/结果统计，可按主题过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回最近 N 条记录", "default": 20},
                "topic": {"type": "string", "description": "按主题关键词过滤（留空返回全部）"},
            },
        },
    },
    "autoresearch_trend": {
        "fn": lambda args: _compute_trend(
            keyword=args.get("keyword", ""),
            days=args.get("days", 7),
        ),
        "description": "计算研究主题的趋势：最近 N 天记录数变化、均值对比，识别信息量增减",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "研究主题关键词"},
                "days": {"type": "integer", "description": "统计天数窗口", "default": 7},
            },
        },
    },
    "autoresearch_compare": {
        "fn": lambda args: {
            "current": _load_research_history(limit=1, topic=args.get("topic", "")),
            "previous": _load_research_history(limit=2, topic=args.get("topic", "")),
            "comparison": _compute_trend(
                keyword=args.get("topic", ""), days=args.get("days", 7),
            ),
        },
        "description": "对比同一主题的最近两次研究结果，识别新增内容和热度变化",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "研究主题"},
                "days": {"type": "integer", "description": "趋势统计天数", "default": 7},
            },
            "required": ["topic"],
        },
    },
}


# ──────────────────────────────────────────────────────────────
# MCP JSON-RPC 2.0 stdio 协议
# ──────────────────────────────────────────────────────────────

def _send(obj: dict):
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle(req: dict):
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})
    arguments = params.get("arguments", {}) if isinstance(params, dict) else params

    if method == "initialize":
        _send({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "autoresearch",
                    "version": "2.1.0",
                    "description": "AutoResearch 多源信息聚合 MCP 服务器 v2.1 | 支持 ProSearch/ArXiv/GitHub/HN/Reddit/ProductHunt",
                },
            },
        })
        return

    if method == "tools/list":
        tools_list = [
            {"name": n, "description": m["description"], "inputSchema": m["inputSchema"]}
            for n, m in TOOLS.items()
        ]
        _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}})
        return

    if method == "tools/call":
        tool_name = params.get("name", "")
        if tool_name not in TOOLS:
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"工具不存在: {tool_name}"},
            })
            return
        try:
            result = TOOLS[tool_name]["fn"](arguments if arguments else {})
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                    "isError": False,
                },
            })
        except Exception as e:
            import traceback
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"执行失败: {e}\n{traceback.format_exc()}"}],
                    "isError": True,
                },
            })
        return

    if method.startswith("notifications/"):
        return

    if req_id is not None:
        _send({
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"未知方法: {method}"},
        })


def main():
    print(f"[AutoResearch MCP v2.1] 服务器已启动 (sources: {', '.join(ALL_SOURCES)})", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": f"JSON 解析错误: {e}"}})
            continue
        _handle(req)


if __name__ == "__main__":
    main()
