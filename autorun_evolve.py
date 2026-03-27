#!/usr/bin/env python3
"""
autorun_evolve.py — QClaw AutoResearch 自主进化脚本 v3.1
全源重试 + 指数退避 + 实时进度条 + 进化历史
"""
import os, sys, io, json, time, uuid, argparse, hashlib, re, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict

# ── UTF-8 ──────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
for _s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        if hasattr(_s, "buffer"):
            sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", line_buffering=True)
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
            break
    except: pass

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR  = SCRIPT_DIR / "_cache"
HISTORY_DB = SCRIPT_DIR / "_evolution.jsonl"
CACHE_DIR.mkdir(exist_ok=True)
PORT = os.getenv("AUTH_GATEWAY_PORT", "19000")

# ── 控制台样式 ─────────────────────────────────────────────────
class C:
    R   = "\033[0m"
    B   = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YEL = "\033[93m"
    BLU = "\033[94m"
    MAG = "\033[95m"
    CYN = "\033[96m"

    @staticmethod
    def p(msg, c="", bold=False):
        pre = (C.B if bold else "") + c
        print(f"{pre}{msg}{C.R}", flush=True)

    @staticmethod
    def banner(msg):
        print()
        C.p("═" * 62, c=C.CYN)
        C.p(f"  {msg}", c=C.CYN, bold=True)
        C.p("═" * 62, c=C.CYN)
        print()

    @staticmethod
    def ok(msg):
        C.p(f"  ✅ {msg}", c=C.GRN)

    @staticmethod
    def info(msg):
        C.p(f"  ℹ️  {msg}", c=C.CYN)

    @staticmethod
    def warn(msg):
        C.p(f"  ⚠️  {msg}", c=C.YEL)

    @staticmethod
    def fail(msg):
        C.p(f"  ❌ {msg}", c=C.RED)

    @staticmethod
    def step(msg):
        C.p(f"  ⟡  {msg}", c=C.MAG)

# ── 缓存 ──────────────────────────────────────────────────────
def _ck(prefix, **kw):
    parts = [prefix] + [f"{k}={v}" for k,v in sorted(kw.items())]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16] + "_" + prefix

# ── 自适应缓存 TTL ────────────────────────────────────────────
def _adaptive_ttl(key, base_ttl=3600):
    """自适应缓存 TTL（热门主题缩短，冷门主题延长）"""
    # 根据缓存命中频率调整 TTL
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        # 统计最近访问频率
        stat = cache_file.stat()
        age_hours = (time.time() - stat.st_mtime) / 3600
        # 热门内容（被频繁访问）：缩短 TTL
        # 冷门内容（很少访问）：延长 TTL
        if age_hours < 1:
            return min(base_ttl, 600)  # 热门：10分钟
        elif age_hours < 6:
            return base_ttl // 2      # 中等：30分钟
        else:
            return base_ttl * 2       # 冷门：2小时
    return base_ttl


def _cget(key, ttl=3600):
    p = CACHE_DIR / f"{key}.json"
    if not p.exists(): return None
    # 使用自适应 TTL
    actual_ttl = _adaptive_ttl(key, ttl)
    if time.time() - p.stat().st_mtime > actual_ttl: return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return None

def _cset(key, data):
    try: (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except: pass

# ── 数据获取（统一重试逻辑）───────────────────────────────────

def _http_get_json(url, headers=None, timeout=20):
    """GET JSON，超时返回 None"""
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except: return None

def _http_get_text(url, headers=None, timeout=20):
    """GET 文本，超时返回 None"""
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except: return None

def _retry(label, fn, max_attempts=4, base_wait=2):
    """通用重试装饰器（基于返回值非空判断成功）"""
    last_err = ""
    for attempt in range(max_attempts):
        result = fn()
        if result: return result
        if attempt < max_attempts - 1:
            wait = (base_wait ** attempt) + 1
            C.step(f"{label} 重试 {attempt+2}/{max_attempts}，等待 {wait}s...")
            time.sleep(wait)
    C.warn(f"{label} 失败（{max_attempts}次重试）")
    return None

def fetch_prosearch(keyword, count=10, days=30):
    """ProSearch 联网搜索"""
    ck = _ck("ps", kw=keyword, c=count, d=days)
    cached = _cget(ck, ttl=900)
    if cached:
        C.info(f"ProSearch [缓存] {len(cached)} 条"); return cached
    url = f"http://localhost:{PORT}/proxy/prosearch/search"
    body = json.dumps({"keyword": keyword, "from_time": int(time.time()) - days*86400, "cnt": count}).encode()

    def _do():
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8", errors="replace"))
                return res.get("data", {}).get("docs", []) if res.get("success") else None
        except: return None

    results = _retry("ProSearch", _do, max_attempts=4)
    if results: C.info(f"ProSearch {len(results)} 条")
    else: C.warn(f"ProSearch 无结果")
    _cset(ck, results or [])
    return results or []

def fetch_github_trending(lang="", limit=8):
    """GitHub Trending"""
    ck = _ck("gh", l=lang)
    cached = _cget(ck, ttl=900)
    if cached:
        C.info(f"GitHub [缓存] {len(cached)} 个"); return cached[:limit]
    url = f"https://github.com/trending/{lang}" if lang else "https://github.com/trending"

    def _do():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html = ""
            with urllib.request.urlopen(req, timeout=25) as r:
                html = r.read().decode("utf-8", errors="replace")
            items = []
            for a in re.findall(r'<article class="Box-row">(.*?)</article>', html, re.DOTALL)[:15]:
                t = re.search(r'href="(/[^/]+/[^"]+)"[^>]*>\s*([^<\n]{3,200})', a)
                d = re.search(r'<p[^>]*>([^<\n]{10,300})', a)
                s = re.search(r'(\d[\d,]*)\s+stars today', a)
                if t:
                    items.append({
                        "title": f"github: {t.group(2).strip()}",
                        "url": "https://github.com" + t.group(1),
                        "type": "project",
                        "stars_today": s.group(1).replace(",","") if s else "0",
                        "description": d.group(1).strip() if d else "",
                        "source": "GitHub",
                    })
            return items if items else None
        except: return None

    results = _retry("GitHub", _do, max_attempts=4)
    if results: C.info(f"GitHub {len(results)} 个项目")
    _cset(ck, results or [])
    return (results or [])[:limit]

def fetch_hackernews(n=10):
    """Hacker News Top Stories"""
    ck = _ck("hn", n=n)
    cached = _cget(ck, ttl=600)
    if cached:
        C.info(f"HackerNews [缓存] {len(cached)} 条"); return cached

    def _do():
        try:
            req = urllib.request.Request(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                ids = json.loads(r.read().decode())
            items = []
            for iid in ids[:n * 2]:
                try:
                    req2 = urllib.request.Request(
                        f"https://hacker-news.firebaseio.com/v0/item/{iid}.json",
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        item = json.loads(r2.read().decode())
                    if item.get("title"):
                        items.append({
                            "title": f"hn: {item['title']}",
                            "url": item.get("url") or f"https://news.ycombinator.com/item?id={iid}",
                            "type": "discussion",
                            "score": item.get("score", 0),
                            "source": "HackerNews",
                        })
                    if len(items) >= n: break
                except: continue
            return items if items else None
        except: return None

    results = _retry("HackerNews", _do, max_attempts=4)
    if results: C.info(f"HackerNews {len(results)} 条")
    _cset(ck, results or [])
    return results or []

def _score_paper_quality(title, abstract, topic=""):
    """论文摘要质量评分（基于 ArXiv 检索优化研究）"""
    score = 0.0
    text = (title + " " + abstract).lower()
    
    # 高质量信号词（+权重）
    quality_signals = {
        "benchmark": 2.0, "evaluation": 1.5, "experiment": 1.5,
        "outperform": 2.0, "improve": 1.5, "achieve": 1.5,
        "state-of-the-art": 2.5, "sota": 2.0, "novel": 1.5,
        "propose": 1.0, "method": 1.0, "approach": 1.0,
        "lossless": 2.0, "zero-shot": 1.5, "quantization": 1.0,
    }
    for kw, w in quality_signals.items():
        if kw in text:
            score += w
    
    # 低质量信号词（-权重）
    low_quality = {
        "survey": -0.5, "review": -0.5, "overview": -0.5,
        "preliminary": -1.0, "draft": -1.5, "note": -0.5,
    }
    for kw, w in low_quality.items():
        if kw in text:
            score += w
    
    # 主题相关性加分
    if topic:
        topic_tokens = set(re.findall(r'\b\w{4,}\b', topic.lower()))
        title_tokens = set(re.findall(r'\b\w{4,}\b', title.lower()))
        overlap = len(topic_tokens & title_tokens)
        score += overlap * 0.5  # 每个重叠词 +0.5
    
    # 长度惩罚（过短摘要质量可能较低）
    if len(abstract) < 200:
        score -= 1.0
    elif len(abstract) > 500:
        score += 0.5  # 详实的摘要是好信号
    
    return max(score, 0.0)


def fetch_arxiv(topic, limit=5):
    """ArXiv 论文（自动优化关键词 + 时效性权重 + 质量过滤）"""
    ck = _ck("ax", t=topic, n=limit)
    cached = _cget(ck, ttl=7200)
    if cached:
        C.info(f"ArXiv [缓存] {len(cached)} 篇"); return cached[:limit]
    
    # 关键词优化：中文自动转英文
    optimized_topic = optimize_keyword_for_arxiv(topic)
    if optimized_topic != topic:
        C.step(f"ArXiv 关键词优化: {topic[:30]} → {optimized_topic[:30]}")
    
    q = urllib.parse.quote(optimized_topic)
    url = (f"http://export.arxiv.org/api/query"
           f"?search_query=all:{q}&start=0&max_results={limit*3}"  # 多取一些，后续过滤
           f"&sortBy=submittedDate&sortOrder=descending")

    def _do():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            xml = ""
            with urllib.request.urlopen(req, timeout=30) as r:
                xml = r.read().decode("utf-8", errors="replace")
            items = []
            for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
                tm = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                lm = re.search(r"<id>(.*?)</id>", entry)
                sm = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                dm = re.search(r"<published>(.*?)</published>", entry)
                if tm:
                    title = tm.group(1).strip().replace(chr(10), " ")
                    abstract = sm.group(1).strip().replace(chr(10), " ") if sm else ""
                    items.append({
                        "title": f"[论文] {title}",
                        "url": lm.group(1).strip() if lm else "",
                        "type": "paper",
                        "abstract": abstract[:400],
                        "date": dm.group(1).strip()[:10] if dm else "",
                        "source": "ArXiv",
                    })
            return items if items else None
        except: return None

    results = _retry("ArXiv", _do, max_attempts=4)
    if results:
        # 1. 计算质量评分（含主题相关性）
        for item in results:
            item["_quality"] = _score_paper_quality(
                item.get("title", ""),
                item.get("abstract", ""),
                optimized_topic  # 传入优化后的主题
            )
        
        # 2. 时效性权重
        current_year = datetime.now().year
        for item in results:
            url = item.get("url", "")
            year_match = re.search(r"/(\d{2})(\d{2})\.", url)
            if year_match:
                yy = int(year_match.group(1))
                year = 2000 + yy if yy < 50 else 1900 + yy
                if year >= current_year:
                    item["_freshness"] = 1.5
                elif year >= current_year - 1:
                    item["_freshness"] = 1.0
                else:
                    item["_freshness"] = 0.5
            else:
                item["_freshness"] = 1.0
        
        # 3. 综合排序：质量 × 时效性
        for item in results:
            item["_total_score"] = item.get("_quality", 1.0) * item.get("_freshness", 1.0)
        results.sort(key=lambda x: x.get("_total_score", 0), reverse=True)
        
        # 4. 过滤低质量（质量分 < 1.0 且摘要 < 100 字）
        filtered = [
            item for item in results
            if item.get("_quality", 0) >= 1.0 or len(item.get("abstract", "")) >= 100
        ]
        if len(filtered) < limit:
            filtered = results[:limit]  # 保证数量
        
        # 5. 聚类去重：按标题关键词聚类，每类只保留最高分
        def _extract_keywords(title):
            """从标题提取关键词"""
            # 移除常见前缀
            clean = re.sub(r'^\[?论文\]?\s*', '', title.lower())
            # 提取 4+ 字母的词
            words = re.findall(r'\b[a-z]{4,}\b', clean)
            return set(words)
        
        clusters = {}  # {关键词集合: 最佳论文}
        for item in filtered:
            kw = frozenset(_extract_keywords(item.get("title", "")))
            # 找相似的已存在聚类
            merged = False
            for existing_kw in list(clusters.keys()):
                # Jaccard 相似度 > 0.5 则认为同类
                overlap = len(kw & existing_kw) / max(len(kw | existing_kw), 1)
                if overlap > 0.5:
                    # 保留分数更高的
                    if item.get("_total_score", 0) > clusters[existing_kw].get("_total_score", 0):
                        clusters[existing_kw] = item
                    merged = True
                    break
            if not merged:
                clusters[kw] = item
        
        final = list(clusters.values())
        final.sort(key=lambda x: x.get("_total_score", 0), reverse=True)
        final = final[:limit]
        
        # 清理临时字段
        for item in final:
            item.pop("_quality", None)
            item.pop("_freshness", None)
            item.pop("_total_score", None)
        
        C.info(f"ArXiv {len(final)} 篇（质量+时效性+聚类去重）")
        _cset(ck, final)
        return final
    
    _cset(ck, results or [])
    return (results or [])[:limit]

def fetch_reddit(sub="technology", limit=5):
    """Reddit 热帖（可选源，网络不稳定）"""
    ck = _ck("rd", s=sub)
    cached = _cget(ck, ttl=600)
    if cached:
        C.info(f"Reddit [缓存] {len(cached)} 条"); return cached[:limit]
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"

    def _do():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AutoResearchBot/2.1"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            items = []
            for post in data.get("data", {}).get("children", []):
                d = post.get("data", {})
                if d.get("title"):
                    items.append({
                        "title": f"reddit/{sub}: {d['title']}",
                        "url": d.get("url", ""),
                        "type": "discussion",
                        "score": d.get("score", 0),
                        "source": f"Reddit r/{sub}",
                    })
            return items if items else None
        except: return None

    results = _retry("Reddit", _do, max_attempts=2)  # 降低重试次数，网络不稳定
    if results: C.info(f"Reddit {len(results)} 条")
    _cset(ck, results or [])
    return (results or [])[:limit]

# ── 关键词优化：中文自动转英文 ────────────────────────────────

# 技术术语词典（TurboQuant / KV Cache 量化等扩展）
TECH_TERMS = [
    ("自然语言处理",     "natural language processing"),
    ("计算机视觉",       "computer vision"),
    ("强化学习",         "reinforcement learning"),
    ("深度学习",         "deep learning"),
    ("机器学习",         "machine learning"),
    ("大语言模型",       "large language model"),
    ("大模型",           "large language model"),
    ("神经网络",         "neural network"),
    ("人工智能",         "artificial intelligence"),
    ("生成式AI",         "generative AI"),
    ("生成模型",         "generative model"),
    ("多模态",           "multimodal"),
    ("知识图谱",         "knowledge graph"),
    ("联邦学习",         "federated learning"),
    ("迁移学习",         "transfer learning"),
    ("注意力机制",       "attention mechanism"),
    ("向量量化",         "vector quantization"),
    ("KV缓存",           "KV cache"),
    ("缓存压缩",         "cache compression"),
    ("推理加速",         "inference acceleration"),
    ("零精度损失",       "zero precision loss"),
    ("无损压缩",         "lossless compression"),
    ("向量数据库",       "vector database"),
    ("嵌入向量",         "embedding vector"),
    ("推理效率",         "inference efficiency"),
    ("趋势",             "trends"),
    ("最新",             "latest"),
    ("进展",             "advances"),
    ("研究",             "research"),
    ("应用",             "application"),
    ("技术",             "technology"),
    ("算法",             "algorithm"),
    ("模型",             "model"),
    ("智能",             "intelligent"),
    ("优化",             "optimization"),
    ("训练",             "training"),
    ("推理",             "inference"),
    ("量化",             "quantization"),
    ("数据集",           "dataset"),
    ("基准",             "benchmark"),
    ("吞吐量",           "throughput"),
    ("延迟",             "latency"),
]

def optimize_keyword_for_arxiv(keyword):
    """优化 ArXiv 检索关键词（中文自动转英文，保证词间空格）"""
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in keyword)
    if not has_chinese:
        return keyword

    optimized = keyword
    for zh, en in TECH_TERMS:
        if zh in optimized:
            optimized = optimized.replace(zh, f" {en} ")

    tokens = re.split(r'\s+', optimized.strip())
    en_tokens = [t for t in tokens if t and not any('\u4e00' <= c <= '\u9fff' for c in t)]
    result = " ".join(en_tokens).strip()
    return result if result else keyword

# ════════════════════════════════════════════════════════════════
# 评分与优化
# ════════════════════════════════════════════════════════════════

def rerank_findings(findings, topic=""):
    """
    重排序：relevance × diversity 加权
    洞察来源: ArXiv 多源融合 + 检索质量研究
    """
    if not findings: return findings

    # 计算每条结果的 novelty（与已选集合的差异度）
    selected, seen_tokens = [], set()
    for f in findings:
        title = (f.get("title") or "").lower()
        tokens = set(re.findall(r'\b\w{4,}\b', title))
        # novelty = 与已选结果的词汇重叠度的反值
        if seen_tokens:
            overlap = len(tokens & seen_tokens) / max(len(tokens), 1)
            novelty = 1.0 - overlap
        else:
            novelty = 1.0
        # relevance 用 score 字段近似
        score = 0
        try: score = int(str(f.get("score") or f.get("stars_today") or "0").replace(",",""))
        except: pass
        relevance = min(score / 1000, 1.0)
        # 综合权重
        f["_rank"] = novelty * 0.6 + relevance * 0.4
        seen_tokens |= tokens
        selected.append(f)

    # 按综合权重降序
    selected.sort(key=lambda x: x.get("_rank", 0), reverse=True)
    # 清理临时字段
    for f in selected:
        f.pop("_rank", None)
    return selected


def calculate_diversity_score(findings):
    """计算信息多样性评分（Simpson 多样性指数）"""
    if not findings: return 0.0
    type_counts, source_counts = {}, {}
    for f in findings:
        t = f.get("type", "unknown")
        s = f.get("source", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        source_counts[s] = source_counts.get(s, 0) + 1
    n = len(findings)
    type_div   = 1 - sum((c/n)**2 for c in type_counts.values())
    source_div = 1 - sum((c/n)**2 for c in source_counts.values())
    return round((type_div + source_div) / 2, 3)


def enhanced_score(result):
    """增强评分：信息量 + 热度 + 多样性"""
    total = result.get("total_findings", 0)
    top_score = min(result.get("top_score", 0), 1000)
    diversity = calculate_diversity_score(result.get("findings", []))
    
    # 加权评分
    score = (
        total * 1.0 +                    # 信息量权重 1.0
        top_score * 0.01 +               # 热度权重 0.01
        diversity * 10                   # 多样性权重 10
    )
    return round(score, 2)


# ════════════════════════════════════════════════════════════════
# 数据模型
# ════════════════════════════════════════════════════════════════

@dataclass
class EStrategy:
    rounds: int = 3
    initial_sources: list = field(default_factory=lambda: ["prosearch","hackernews"])
    initial_depth: str = "quick"
    stall_threshold: int = 2
    max_sources: int = 5
    # 差分进化参数
    mutation_rate: float = 0.5
    crossover_rate: float = 0.7

@dataclass
class ERound:
    round_id: str; ts: str; topic: str; round_num: int
    sources: list; depth: str
    total_findings: int = 0; web_search: int = 0; github: int = 0
    hackernews: int = 0; arxiv: int = 0; reddit: int = 0
    producthunt: int = 0; top_score: int = 0
    diversity_score: float = 0.0  # 新增：多样性评分
    enhanced_score: float = 0.0   # 新增：增强评分
    score_delta: float = 0.0; is_improvement: bool = False
    decision: str = ""; new_sources_added: list = field(default_factory=list)
    sources_dropped: list = field(default_factory=list)
    next_hint: str = ""

# ── 进化决策引擎 ───────────────────────────────────────────────
class EvolutionEngine:
    def __init__(self, topic, strategy):
        self.topic = topic; self.strategy = strategy
        self.history = []; self.best = None; self.stall = 0

    def _score(self, result):
        return result["total_findings"] + min(result.get("top_score", 0), 1000) * 0.01

    def _next_srcs(self, prev_srcs, prev_depth, result, round_num=1, total_rounds=3):
        total = result["total_findings"]
        dist = result.get("type_distribution", {})
        diversity = result.get("diversity_score", 0)

        # 探索-利用平衡（ArXiv 洞察）
        # 前 50% 轮次：exploration（尝试新源）
        # 后 50% 轮次：exploitation（深挖最优源）
        explore_phase = round_num <= max(1, total_rounds // 2)

        # 智能深度调节（基于多样性）
        # 多样性低 → 增加 depth，多样性高 → 保持或降低
        if diversity < 0.4:
            suggested_depth = "deep"
        elif diversity < 0.6:
            suggested_depth = "standard"
        else:
            suggested_depth = prev_depth

        if total < 5:
            ns = list(set((prev_srcs or []) + ["prosearch","hackernews"])); hint = "扩展源"
        elif explore_phase:
            # 探索阶段：优先引入未用过的源
            candidate_new = [s for s in ["github","arxiv","hackernews","prosearch"]
                             if s not in (prev_srcs or [])]
            if candidate_new:
                ns = (prev_srcs or []) + [candidate_new[0]]
                hint = f"探索新源: {candidate_new[0]}"
            else:
                ns = prev_srcs; hint = "所有源已探索"
        else:
            # 利用阶段：保留表现好的源，去掉贡献少的
            src_contrib = {
                "prosearch":  dist.get("web_search", 0),
                "github":     dist.get("project", 0),
                "hackernews": dist.get("discussion", 0),
                "arxiv":      dist.get("paper", 0),
            }
            # 保留贡献 > 0 的源
            good_srcs = [s for s in (prev_srcs or []) if src_contrib.get(s, 0) > 0]
            ns = good_srcs if good_srcs else prev_srcs
            hint = f"利用阶段: 保留高贡献源 {ns}"

        # 深度选择：优先使用智能建议，但不降级
        if suggested_depth == "deep" or prev_depth == "deep":
            nd = "deep"
        elif suggested_depth == "standard" or prev_depth == "standard":
            nd = "standard"
        else:
            nd = prev_depth

        ns = ns[:self.strategy.max_sources]
        added   = [s for s in ns if s not in (prev_srcs or [])]
        dropped = [s for s in (prev_srcs or []) if s not in ns]
        return ns, nd, hint, added, dropped

    def process(self, round_num, result, sources, depth):
        prev_s = self._score(self.history[-1].__dict__) if self.history else 0
        curr_s = self._score(result)
        delta = curr_s - prev_s
        is_up = delta > 0.1
        ns, nd, hint, added, dropped = self._next_srcs(
            sources, depth, result,
            round_num=round_num,
            total_rounds=self.strategy.rounds
        )

        if is_up: self.stall = 0
        else: self.stall += 1

        dist = result.get("type_distribution", {})
        diversity = calculate_diversity_score(result.get("findings", []))
        enhanced = enhanced_score(result)
        
        rec = ERound(
            round_id=str(uuid.uuid4())[:8], ts=datetime.now().isoformat(),
            topic=self.topic, round_num=round_num,
            sources=list(sources), depth=depth,
            total_findings=result["total_findings"],
            web_search=dist.get("web_search",0),
            github=dist.get("project",0),
            hackernews=dist.get("discussion",0),
            arxiv=dist.get("paper",0),
            reddit=sum(v for k,v in dist.items() if "reddit" in k.lower()),
            producthunt=dist.get("product",0),
            top_score=result.get("top_score",0),
            diversity_score=diversity,
            enhanced_score=enhanced,
            score_delta=round(delta,3), is_improvement=is_up,
            decision=(f"✅ 提升 {prev_s:.1f}→{curr_s:.1f} (+{delta:.1f})" if is_up
                      else f"⏸️ 无提升 (+{delta:.1f})"),
            new_sources_added=added, sources_dropped=dropped, next_hint=hint,
        )
        self.history.append(rec)
        if self.best is None or is_up: self.best = rec
        return rec, ns, nd

    def get_next(self, current):
        if current >= self.strategy.rounds: return None
        if self.stall >= self.strategy.stall_threshold:
            C.warn(f"连续{self.stall}轮无提升，终止")
            return None
        last = self.history[-1] if self.history else None
        if last:
            dist = {"total_findings": last.total_findings, "type_distribution": {
                "web_search": last.web_search, "project": last.github,
                "discussion": last.hackernews, "paper": last.arxiv}}
            ns, nd, *_ = self._next_srcs(
                last.sources, last.depth, dist,
                round_num=current + 1,
                total_rounds=self.strategy.rounds
            )
            return ns, nd
        return self.strategy.initial_sources, self.strategy.initial_depth

# ── 执行单轮研究 ───────────────────────────────────────────────
def run_round(topic, sources, depth):
    cfg = {
        "github": {"quick":5,"standard":8,"deep":15}.get(depth,8),
        "hackernews": {"quick":5,"standard":10,"deep":20}.get(depth,10),
        "arxiv": {"quick":3,"standard":5,"deep":10}.get(depth,5),
        "reddit": {"quick":3,"standard":5,"deep":8}.get(depth,5),
    }
    findings = []
    for src in sources:
        if src == "prosearch":
            for d in fetch_prosearch(topic):
                findings.append({"title":d.get("title",""),"url":d.get("url",""),
                                   "type":"web_search","site":d.get("site",""),
                                   "snippet":d.get("passage","")[:300],"source":"ProSearch"})
        elif src == "github":
            findings.extend(fetch_github_trending(limit=cfg["github"]))
        elif src == "hackernews":
            findings.extend(fetch_hackernews(n=cfg["hackernews"]))
        elif src == "arxiv":
            findings.extend(fetch_arxiv(topic, limit=cfg["arxiv"]))
        elif src == "reddit":
            for sub in ["technology","MachineLearning"]:
                findings.extend(fetch_reddit(sub=sub, limit=cfg["reddit"]))

    seen, unique = set(), []
    for f in findings:
        url = f.get("url","")
        if url and url not in seen: seen.add(url); unique.append(f)
        elif not url: unique.append(f)
    findings = unique

    # 重排序：relevance × diversity
    findings = rerank_findings(findings, topic)

    dist = {}
    for f in findings:
        t = f.get("type","unknown"); dist[t] = dist.get(t,0) + 1
    scores = []
    for f in findings:
        s = f.get("score") or f.get("stars_today") or "0"
        try: scores.append(int(str(s).replace(",","")))
        except: scores.append(0)
    return {"total_findings":len(findings),"type_distribution":dist,
            "top_score":max(scores) if scores else 0,"findings":findings}

# ════════════════════════════════════════════════════════════════
# 自主探索模块 — 自动生成研究主题
# ════════════════════════════════════════════════════════════════

def extract_emerging_topics(findings, limit=5):
    """从搜索结果中提取新兴话题（自主探索）"""
    topics = {}
    for f in findings:
        title = f.get("title", "").lower()
        # 提取关键词（4+ 字母的词）
        words = re.findall(r'\b[a-z]{4,}\b', title)
        for w in words:
            if w not in ["http", "https", "arxiv", "github"]:
                topics[w] = topics.get(w, 0) + 1
    
    # 按频率排序，返回高频词
    sorted_topics = sorted(topics.items(), key=lambda x: -x[1])
    return [t[0] for t in sorted_topics[:limit]]

def generate_exploration_topics(base_topic, findings, history=None):
    """基于当前研究生成相关的探索主题"""
    emerging = extract_emerging_topics(findings, limit=5)
    
    # 过滤掉 base_topic 中已有的词
    base_words = set(base_topic.lower().split())
    filtered = [kw for kw in emerging if kw not in base_words]
    
    # 组合策略：base_topic + emerging keyword
    candidates = []
    for kw in filtered:
        # 避免重复
        if history and kw in [h.topic for h in history]:
            continue
        new_topic = f"{base_topic} {kw}"
        candidates.append(new_topic)
    
    return candidates[:3]  # 返回最多 3 个候选主题

def autonomous_explore(base_topic, max_iterations=3):
    """自主探索模式：持续研究相关主题"""
    C.banner(f"🤖 AutoResearch 自主探索 | {base_topic}")
    print()
    
    strategy = EStrategy(rounds=2, initial_depth="quick")  # 快速探索
    history = []
    current_topic = base_topic
    
    for iteration in range(max_iterations):
        C.p(f"\n【迭代 {iteration + 1}/{max_iterations}】主题: {current_topic}", bold=True)
        
        # 执行一轮研究
        all_r, elapsed = evolve(current_topic, strategy)
        history.extend(all_r)
        
        if not all_r:
            break
        
        # 从最后一轮获取 findings
        result = run_round(current_topic, strategy.initial_sources, strategy.initial_depth)
        findings = result.get("findings", [])
        
        candidates = generate_exploration_topics(current_topic, findings, history)
        
        if not candidates:
            C.info("无新主题可探索，停止")
            break
        
        # 选择第一个候选主题
        current_topic = candidates[0]
        C.info(f"下一个探索主题: {current_topic}")
    
    C.ok(f"自主探索完成: {len(history)} 轮研究")
    return history

# ── 进化主循环 ────────────────────────────────────────────────
def evolve(topic, strategy):
    C.banner(f"AutoResearch | {topic} | {strategy.rounds}轮")
    print()
    C.p(f"  {'R':<3} {'进度':<28} {'深度':<9} {'信息量':<9} {'顶分':<8} {'多样性':<7} {'状态'}", bold=True)
    print()
    engine = EvolutionEngine(topic, strategy)
    all_r, sources, depth = [], list(strategy.initial_sources), strategy.initial_depth
    t0 = time.time()

    for rn in range(1, strategy.rounds + 1):
        r_t0 = time.time()
        filled = round(rn / strategy.rounds * 28)
        bar = "█"*filled + "░"*(28-filled)
        C.step(f"R{rn} → sources={sources}, depth={depth}")

        result = run_round(topic, sources, depth)
        rec, sources, depth = engine.process(rn, result, sources, depth)
        all_r.append(rec)
        took = time.time() - r_t0

        icon = "✅" if rec.is_improvement else "⏸️"
        ds = {"quick":"quick","standard":"std","deep":"deep"}.get(depth,depth)
        si = "🔥" if rec.top_score > 500 else "  "
        diversity_str = f"{rec.diversity_score:.2f}"
        print(f"\r  R{rn:<2} [{bar}]  {ds:<9} {result['total_findings']:>5}条  {si}{rec.top_score:<6} {diversity_str:<7} {icon} ({took:.0f}s)", end="", flush=True)

        nxt = engine.get_next(rn)
        if nxt is None: break
        sources, depth = nxt

    elapsed = time.time() - t0
    best = max(all_r, key=lambda r: r.total_findings, default=None)
    fn = all_r[0].total_findings if all_r else 0
    bn = best.total_findings if best else fn
    mult = bn / max(fn, 1)
    print(); print()
    C.ok(f"完成: {len(all_r)}轮 | 最优R{best.round_num if best else 0} | {fn}→{bn} ({mult:.1f}x) | {elapsed:.0f}s")
    _save(all_r, topic, elapsed)
    return all_r, elapsed

def _save(rounds, topic, elapsed):
    best = max(rounds, key=lambda r: r.total_findings, default=None)
    rec = {
        "ts": datetime.now().isoformat(), "topic": topic,
        "total_rounds": len(rounds), "elapsed_s": round(elapsed,1),
        "best_round": rounds.index(best)+1 if best else None,
        "rounds": [asdict(r) for r in rounds],
    }
    try:
        with open(HISTORY_DB, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        C.ok("历史已保存")
    except Exception as e: C.warn(f"保存失败: {e}")

# ── 报告 ─────────────────────────────────────────────────────
def report(topic, rounds, elapsed):
    best = max(rounds, key=lambda r: r.total_findings, default=None)
    first = rounds[0] if rounds else None
    mult = (best.total_findings / max(first.total_findings,1)) if first and best else 1
    lines = [
        f"# 🧬 AutoResearch 进化报告\n",
        f"**主题**: {topic} | **{len(rounds)}轮**（{elapsed:.0f}s） | **最优**: R{best.round_num if best else '?'}\n",
        "## 📊 进化轨迹\n| R | 信息源 | 深度 | 总数 | 顶分 | 决策 |",
        "|---|--------|------|------|------|------|",
    ]
    for r in rounds:
        icon = "✅" if r.is_improvement else "⏸️"
        srcs = "+".join(r.sources[:3]) + ("..." if len(r.sources)>3 else "")
        lines.append(f"| R{r.round_num} | {srcs} | {r.depth} | {r.total_findings} | {r.top_score} | {icon} |")
    if best:
        lines += [
            "", "## 🏆 最优策略",
            f"- **配置**: `sources={best.sources}, depth={best.depth}`",
            f"- **信息量**: {best.total_findings} 条 | **顶分**: ⭐{best.top_score}",
            f"- **多样性**: {best.diversity_score:.2f} | **综合评分**: {best.enhanced_score:.1f}",
            f"- **类型**: 网页{best.web_search} | GH{best.github} | HN{best.hackernews} | 论文{best.arxiv}",
            "", "## 📈 进化效果",
            f"- 信息量: {first.total_findings if first else 0} → {best.total_findings} ({best.total_findings-(first.total_findings if first else 0):+d})",
            f"- 提升: **{mult:.1f}x**",
            "", f"🧬 {datetime.now().isoformat()} | Karpathy闭环 + 多样性优化",
        ]
    return "\n".join(lines)

# ── 主入口 ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="AutoResearch 自主进化 v3.2")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=3)
    p.add_argument("-s", "--sources", nargs="+",
                   default=["prosearch","hackernews"],
                   choices=["prosearch","github","hackernews","arxiv","reddit"])
    p.add_argument("-d", "--depth", default="quick", choices=["quick","standard","deep"])
    p.add_argument("--stall", type=int, default=2)
    p.add_argument("--save", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--history", action="store_true")
    p.add_argument("--explore", action="store_true", help="自主探索模式：自动生成相关主题")
    p.add_argument("--explore-depth", type=int, default=3, help="自主探索深度（迭代次数）")
    args = p.parse_args()

    if args.history:
        recs = []
        if HISTORY_DB.exists():
            for line in HISTORY_DB.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    try: recs.append(json.loads(line))
                    except: pass
        C.banner("进化历史")
        if not recs: C.warn("暂无记录"); return
        for r in recs[-10:]:
            best = max(r.get("rounds",[]), key=lambda x: x.get("total_findings",0), default={})
            C.p(f"  [{r.get('ts','')[:19]}] {r.get('topic','')}  {r.get('total_rounds',0)}轮  {best.get('total_findings',0)}条")
        return

    if not args.topic:
        C.fail("请提供研究主题"); return

    # 自主探索模式
    if args.explore:
        autonomous_explore(args.topic, max_iterations=args.explore_depth)
        return

    st = EStrategy(rounds=args.rounds, initial_sources=args.sources,
                   initial_depth=args.depth, stall_threshold=args.stall)

    rounds, elapsed = evolve(args.topic, st)
    best = max(rounds, key=lambda r: r.total_findings, default=None)
    print(); print(report(args.topic, rounds, elapsed))

    if args.save and best:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in args.topic)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCRIPT_DIR / f"evolve_{safe}_{ts}.md"
        path.write_text(report(args.topic, rounds, elapsed), encoding="utf-8")
        C.ok(f"报告: {path}")

if __name__ == "__main__":
    main()
