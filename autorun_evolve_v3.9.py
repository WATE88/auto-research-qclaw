#!/usr/bin/env python3
"""
AutoResearch v3.9 — Token 效率优化版
核心：用最少的 Token 做更多智能化的事情
"""
import os, sys, json, time, random, asyncio, aiohttp, threading
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter
import hashlib

os.environ["PYTHONIOENCODING"] = "utf-8"
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR, REPORTS_DIR = SCRIPT_DIR / "_cache", SCRIPT_DIR / "reports"
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# Token 效率优化核心
# ════════════════════════════════════════════════════════════════

class TokenOptimizer:
    """Token 效率优化器"""
    
    # 压缩映射表（高频词 → 短编码）
    COMPRESS_MAP = {
        "artificial_intelligence": "AI",
        "machine_learning": "ML",
        "large_language_model": "LLM",
        "natural_language_processing": "NLP",
        "deep_learning": "DL",
        "reinforcement_learning": "RL",
        "convolutional_neural_network": "CNN",
        "transformer_attention": "TA",
        "retrieval_augmented_generation": "RAG",
        "quantization_aware_training": "QAT",
        "large_language_model": "LLM",
        "state_of_the_art": "SOTA",
        "chain_of_thought": "CoT",
    }
    
    @staticmethod
    def compress(text: str) -> str:
        """文本压缩：长词 → 短词"""
        for long, short in TokenOptimizer.COMPRESS_MAP.items():
            text = text.replace(long, short)
        return text
    
    @staticmethod
    def hash_id(text: str, length=8) -> str:
        """生成短 ID"""
        return hashlib.md5(text.encode()).hexdigest()[:length]
    
    @staticmethod
    def truncate(text: str, max_len=50) -> str:
        """智能截断"""
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."
    
    @staticmethod
    def compact_findings(findings: list) -> list:
        """压缩 findings：只保留关键字段"""
        compacted = []
        for f in findings:
            compacted.append({
                "i": TokenOptimizer.hash_id(f.get("title", "")),
                "t": TokenOptimizer.compress(TokenOptimizer.truncate(f.get("title", ""), 40)),
                "s": f.get("source", "unk")[:3],  # 来源缩写
            })
        return compacted
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算 Token 数（约等于 4 字符/token）"""
        return len(text) // 4

# ════════════════════════════════════════════════════════════════
# 智能增量更新
# ════════════════════════════════════════════════════════════════

class IncrementalUpdate:
    """增量更新：只记录变化"""
    
    def __init__(self):
        self.last_state = {}
        self.changes = []
    
    def diff(self, new_data: dict) -> dict:
        """计算差异"""
        diff = {}
        for k, v in new_data.items():
            if k not in self.last_state:
                diff[k] = ("add", v)
            elif self.last_state[k] != v:
                diff[k] = ("update", v)
        self.last_state = new_data.copy()
        return diff
    
    def summary(self, changes: dict) -> str:
        """生成变化摘要"""
        if not changes:
            return "No changes"
        return f"+{sum(1 for v in changes.values() if v[0]=='add')}|~{sum(1 for v in changes.values() if v[0]=='update')}"

# ════════════════════════════════════════════════════════════════
# 智能缓存（Token 感知）
# ════════════════════════════════════════════════════════════════

class TokenAwareCache:
    """Token 感知缓存：根据 Token 预算动态调整"""
    
    def __init__(self, max_tokens=10000):
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.cache = {}
        self.lock = threading.Lock()
    
    def can_cache(self, data: str) -> bool:
        """检查是否可以缓存"""
        tokens = TokenOptimizer.estimate_tokens(data)
        return (self.current_tokens + tokens) <= self.max_tokens
    
    def add(self, key: str, data: dict):
        """添加缓存"""
        with self.lock:
            tokens = TokenOptimizer.estimate_tokens(json.dumps(data))
            if key not in self.cache:
                self.current_tokens += tokens
                self.cache[key] = data
    
    def get(self, key: str) -> dict:
        return self.cache.get(key)
    
    def evict_lru(self):
        """LRU 淘汰"""
        if self.cache:
            oldest = next(iter(self.cache))
            del self.cache[oldest]

# ════════════════════════════════════════════════════════════════
# 智能查询优化
# ════════════════════════════════════════════════════════════════

class SmartQueryOptimizer:
    """智能查询：用更少的查询获取更多有价值信息"""
    
    # 查询模板（精炼）
    QUERY_TEMPLATES = {
        "research": ["{topic} survey", "{topic} benchmark", "{topic} SOTA"],
        "code": ["{topic} github", "{topic} implementation", "{topic} framework"],
        "product": ["{topic} product", "{topic} launch", "{topic} release"],
        "news": ["{topic} news", "{topic} update", "{topic} 2026"],
    }
    
    @staticmethod
    def optimize(topic: str, mode="research") -> list:
        """生成优化查询"""
        templates = SmartQueryOptimizer.QUERY_TEMPLATES.get(mode, SmartQueryOptimizer.QUERY_TEMPLATES["research"])
        queries = []
        for t in templates[:2]:  # 最多2个查询
            q = t.format(topic=TokenOptimizer.compress(topic))
            queries.append(q)
        return queries

# ════════════════════════════════════════════════════════════════
# 轻量级评分
# ════════════════════════════════════════════════════════════════

class LightScorer:
    """轻量级评分：简化计算"""
    
    SOURCE_WEIGHT = {"ax": 1.0, "gh": 0.9, "hn": 0.8, "ph": 0.7, "rd": 0.6, "ps": 0.5}
    
    @staticmethod
    def score(findings: list) -> dict:
        if not findings:
            return {"n": 0, "w": 0}
        
        n = len(findings)
        
        # 简化：只用来源计算
        w = sum(LightScorer.SOURCE_WEIGHT.get(f.get("s",""), 0.5) for f in findings) / n
        
        return {"n": n, "w": w}

# ════════════════════════════════════════════════════════════════
# 数据采集
# ════════════════════════════════════════════════════════════════

class Collector:
    def __init__(self, session):
        self.s = session
    
    async def fetch(self, name, topic, limit):
        key = f"{name}:{topic}:{limit}"
        
        await asyncio.sleep(0.015)  # 更短延迟
        
        gs = {
            "prosearch": lambda i: {"t": f"PS {topic[:20]} #{i}", "s": "ps"},
            "github": lambda i: {"t": f"GH {topic[:15]} {i}", "s": "gh", "star": random.randint(100,5000)},
            "hackernews": lambda i: {"t": f"HN {topic[:15]} {i}", "s": "hn", "score": random.randint(50,300)},
            "arxiv": lambda i: {"t": f"AX {topic[:15]} {i}", "s": "ax"},
            "reddit": lambda i: {"t": f"RD {topic[:15]} {i}", "s": "rd", "up": random.randint(10,500)},
            "producthunt": lambda i: {"t": f"PH {topic[:15]} {i}", "s": "ph", "vote": random.randint(50,300)},
        }
        
        return [gs[name](i) for i in range(limit)]
    
    async def run(self, topic, sources, depth):
        l = {"quick": 4, "standard": 6, "deep": 10}.get(depth, 4)
        
        # 智能查询优化
        queries = SmartQueryOptimizer.optimize(topic)
        
        # 并行采集
        all_fs = []
        for q in queries[:1]:  # 减少查询次数
            ts = [self.fetch(s, q, l) for s in sources]
            rs = await asyncio.gather(*ts, return_exceptions=True)
            for r in rs:
                if isinstance(r, list):
                    all_fs.extend(r)
        
        return all_fs

# ════════════════════════════════════════════════════════════════
# 引擎
# ════════════════════════════════════════════════════════════════

@dataclass
class Cfg:
    sources: list
    depth: str = "quick"

@dataclass
class Res:
    rn: int
    cfg: Cfg
    n: int
    w: float
    findings_compact: list = field(default_factory=list)

class Engine:
    def __init__(self, topic):
        self.topic = topic
        self.history = []
        self.best = None
        self.scorer = LightScorer()
    
    def suggest(self, rn, total):
        all_s = ["prosearch", "github", "hackernews", "arxiv", "reddit", "producthunt"]
        exp = rn <= max(1, total // 2)
        srcs = all_s[:3] if exp else all_s[:4]
        depth = "quick" if rn == 1 else ("standard" if exp else "deep")
        return Cfg(sources=srcs, depth=depth)
    
    async def run(self, cfg):
        async with aiohttp.ClientSession() as s:
            fs = await Collector(s).run(self.topic, cfg.sources, cfg.depth)
        
        sc = self.scorer.score(fs)
        
        # Token 压缩
        compact = TokenOptimizer.compact_findings(fs)
        
        return Res(rn=0, cfg=cfg, n=sc["n"], w=sc["w"], findings_compact=compact)
    
    def observe(self, r):
        self.history.append(r)
        if not self.best or r.w > self.best.w:
            self.best = r

# ════════════════════════════════════════════════════════════════
# 极简仪表盘
# ════════════════════════════════════════════════════════════════

class MiniDash:
    @staticmethod
    def gen(rs, topic, out):
        total = sum(r.n for r in rs)
        avg_w = sum(r.w for r in rs) / len(rs) if rs else 0
        
        # Token 统计
        raw_tokens = sum(len(json.dumps(r.findings_compact)) for r in rs)
        compact_tokens = raw_tokens  # 已经是压缩格式
        
        trend = json.dumps([{"r": ri.rn, "n": ri.n, "w": round(ri.w, 2)} for ri in rs])
        
        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{topic}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{{font-family:system-ui;background:#111;color:#eee;padding:20px}}.c{{max-width:900px;margin:0 auto}}
h1{{color:#00d4ff}}h2{{color:#888;margin:15px 0 5px}}.g{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:20px 0}}
.b{{background:#222;padding:15px;border-radius:8px}}.v{{font-size:24px;color:#00d4ff}}
.p{{color:#666;font-size:12px}}.cv{{background:#222;padding:15px;border-radius:8px;margin:15px 0}}
</style></head><body><div class="c">
<h1>AutoResearch v3.9 Token-Optimized</h1><p>{topic} | {datetime.now().strftime("%H:%M:%S")}</p>
<div class="g">
<div class="b"><div class="p">Findings</div><div class="v">{total}</div></div>
<div class="b"><div class="p">Avg Score</div><div class="v">{avg_w:.2f}</div></div>
<div class="b"><div class="p">Tasks</div><div class="v">{len(rs)}</div></div>
<div class="b"><div class="p">Tokens</div><div class="v">~{compact_tokens}</div></div>
</div>
<div class="cv"><canvas id="c"></canvas></div></div>
<script>new Chart(document.getElementById('c'),{{type:'line',data:{{labels:{trend}.map(x=>'R'+x.r)},datasets:[{{label:'Findings',data:{trend}.map(x=>x.n),borderColor:'#00d4ff'}},{{label:'Score',data:{trend}.map(x=>x.w*100),borderColor:'#888',yAxisID:'y1'}}]}},options:{{scales:{{y1:{{type:'linear',display:true,position:'right'}}}}}}}});
</script></body></html>'''
        
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        return out

# ════════════════════════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════════════════════════

async def run(topic, rounds=3):
    print(f"\n{'='*60}\n  AutoResearch v3.9 | {topic}\n{'='*60}")
    
    e = Engine(topic)
    rs, t0 = [], time.time()
    
    for rn in range(1, rounds + 1):
        cfg = e.suggest(rn, rounds)
        print(f"  >> R{rn} | {cfg.sources[:3]}... | {cfg.depth}")
        
        r = await e.run(cfg)
        r.rn = rn
        e.observe(r)
        rs.append(r)
        
        print(f"  [*] {r.n} findings (w={r.w:.2f}) | tokens: ~{len(json.dumps(r.findings_compact))}")
    
    out = REPORTS_DIR / f"v39_{topic.replace(' ','_')[:20]}_{int(t0)}.html"
    MiniDash.gen(rs, topic, out)
    print(f"[OK] {len(rs)} rounds | {time.time()-t0:.1f}s | {out.name}")
    return rs

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=3)
    a = p.parse_args()
    if not a.topic:
        print("Usage: python autorun_evolve_v3.9.py <topic> [-r rounds]")
        return
    asyncio.run(run(a.topic, a.rounds))

if __name__ == "__main__":
    main()
