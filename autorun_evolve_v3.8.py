#!/usr/bin/env python3
"""
AutoResearch v3.8 — 多维度优化增强版
"""
import os, sys, json, time, random, asyncio, aiohttp, threading
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import OrderedDict, Counter
from typing import Dict, List

os.environ["PYTHONIOENCODING"] = "utf-8"
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR, REPORTS_DIR = SCRIPT_DIR / "_cache", SCRIPT_DIR / "reports"
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# 缓存
class Cache:
    def __init__(self, c=300, t=600):
        self.c, self.t = c, t
        self.cache, self.ts, self.ac, self.lock = OrderedDict(), {}, {}, threading.Lock()
    
    def get(self, k):
        with self.lock:
            if k in self.cache and time.time() - self.ts.get(k, 0) < self.t:
                self.cache.move_to_end(k)
                return self.cache[k]
            return None
    
    def put(self, k, v):
        with self.lock:
            if k in self.cache: self.cache.move_to_end(k)
            elif len(self.cache) >= self.c:
                kk = min(self.ac.items(), key=lambda x: x[1])[0] if self.ac else next(iter(self.cache))
                del self.cache[kk]
            self.cache[k], self.ts[k], self.ac[k] = v, time.time(), self.ac.get(k, 0) + 1

G = Cache()

# 来源权威性
AUTH = {"arxiv": 1.0, "github": 0.9, "hackernews": 0.8, "producthunt": 0.7, "reddit": 0.6, "prosearch": 0.5}

# 多维度评分
class Scorer:
    QUAL = {"high": ["benchmark", "SOTA", "accuracy", "novel"], "medium": ["analysis", "study", "method"], "low": ["demo", "release"]}
    
    def score(self, fs):
        if not fs: return {"total": 0, "dims": {}, "w": 0}
        
        q = sum(1 for f in fs if any(k in f.get("title","").lower() for k in self.QUAL["high"])) / len(fs)
        a = sum(AUTH.get(f.get("s",""), 0.5) for f in fs) / len(fs)
        d = 1 - sum((c/len(fs))**2 for c in Counter(f.get("s","") for f in fs).values())
        r = 0.7  # 简化
        w = q*0.3 + a*0.3 + d*0.25 + r*0.15
        
        return {"total": len(fs), "dims": {"quality": q, "authority": a, "diversity": d, "recency": r}, "w": w}

# 采集器
class Collector:
    def __init__(self, s): self.s = s
    
    async def _f(self, n, t, l):
        k = f"{n}:{t}:{l}"
        c = G.get(k)
        if c: return c
        await asyncio.sleep(0.02)
        gs = {
            "prosearch": lambda i: {"t": f"PS: {t} #{i}", "s": "prosearch"},
            "github": lambda i: {"t": f"GH: {t} repo {i}", "s": "github", "stars": random.randint(100,10000)},
            "hackernews": lambda i: {"t": f"HN: {t} #{i}", "s": "hackernews", "score": random.randint(50,500)},
            "arxiv": lambda i: {"t": f"AX: {t} paper {i}", "s": "arxiv"},
            "reddit": lambda i: {"t": f"RD: r/ML {t} #{i}", "s": "reddit", "up": random.randint(10,1000)},
            "producthunt": lambda i: {"t": f"PH: {t} product {i}", "s": "producthunt", "votes": random.randint(50,500)},
        }
        r = [gs[n](i) for i in range(l)]
        G.put(k, r)
        return r
    
    async def run(self, topic, srcs, depth):
        l = {"quick": 5, "standard": 8, "deep": 15}.get(depth, 5)
        ts = [self._f(s, topic, l) for s in srcs]
        rs = await asyncio.gather(*ts, return_exceptions=True)
        out = {}
        for s, r in zip(srcs, rs):
            out[s] = r if isinstance(r, list) else []
        return out

@dataclass
class Cfg: srcs: list = field(default_factory=list); depth: str = "quick"
@dataclass
class Res: rn: int; cfg: Cfg; n: int; sc: dict

class Engine:
    def __init__(self, topic, mode="karpathy"):
        self.topic, self.mode, self.history = topic, mode, []
        self.scorer = Scorer()
    
    def suggest(self, rn, tr):
        all_srcs = ["prosearch", "hackernews", "arxiv", "github", "reddit", "producthunt"]
        exp = rn <= max(1, tr // 2)
        srcs = all_srcs[:3] if exp else all_srcs[:4]
        depth = "quick" if rn == 1 else ("standard" if exp else "deep")
        return Cfg(srcs=srcs, depth=depth)
    
    async def run(self, cfg):
        async with aiohttp.ClientSession() as s:
            d = await Collector(s).run(self.topic, cfg.srcs, cfg.depth)
        fs = []
        for src, items in d.items():
            for it in items: it["s"] = src
            fs.extend(items)
        sc = self.scorer.score(fs)
        return Res(rn=0, cfg=cfg, n=len(fs), sc=sc)
    
    def observe(self, r):
        self.history.append(r)
        if not hasattr(self, 'best') or r.sc.get("w", 0) > self.best.sc.get("w", 0):
            self.best = r

# 仪表盘
class Dash:
    @staticmethod
    def gen(rs, topic, out):
        total = sum(r.n for r in rs)
        avgd = {}
        for dim in ["quality", "authority", "diversity", "recency"]:
            avgd[dim] = sum(r.sc.get("dims",{}).get(dim,0) for r in rs) / len(rs)
        
        trend = json.dumps([{"r": ri.rn, "n": ri.n, "w": ri.sc.get("w",0)} for ri in rs])
        dims = json.dumps([{"d": k, "s": v} for k,v in avgd.items()])
        
        html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>AutoResearch v3.8</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
.c{max-width:1400px;margin:0 auto}h1{color:#38bdf8}h2{color:#a78bfa;margin:20px 0 10px}
.g{display:grid;grid-template-columns:repeat(5,1fr);gap:15px;margin:20px 0}
.b{background:#1e293b;padding:20px;border-radius:12px}v{font-size:28px;font-weight:bold;color:#38bdf8}
.cv{background:#1e293b;padding:20px;border-radius:12px;margin:15px 0}</style></head>
<body><div class="c">
<h1>AutoResearch v3.8 Multi-Dimension</h1><p>Topic: ''' + topic + ''' | ''' + datetime.now().strftime("%Y-%m-%d %H:%M") + '''</p>
<div class="g">
<div class="b"><div>Findings</div><v>''' + str(total) + '''</v></div>
<div class="b"><div>Quality</div><v>''' + f"{avgd.get('quality',0):.0%}" + '''</v></div>
<div class="b"><div>Authority</div><v>''' + f"{avgd.get('authority',0):.0%}" + '''</v></div>
<div class="b"><div>Diversity</div><v>''' + f"{avgd.get('diversity',0):.0%}" + '''</v></div>
<div class="b"><div>Recency</div><v>''' + f"{avgd.get('recency',0):.0%}" + '''</v></div>
</div>
<div class="cv"><canvas id="t"></canvas></div>
<div class="cv"><canvas id="d"></canvas></div></div>
<script>
const td=''' + trend + ''';
const dd=''' + dims + ''';
new Chart(document.getElementById('t'),{type:'line',data:{labels:td.map(x=>'R'+x.r),datasets:[{label:'Findings',data:td.map(x=>x.n),borderColor:'#38bdf8'}]}});
new Chart(document.getElementById('d'),{type:'bar',data:{labels:dd.map(x=>x.d),datasets:[{label:'Score',data:dd.map(x=>x.s*100),backgroundColor:['#38bdf8','#a78bfa','#34d399','#fbbf24']}]}});
</script></body></html>'''
        
        with open(out, 'w', encoding='utf-8') as f: f.write(html)
        return out

# 主循环
async def run(topic, rounds=4, mode="karpathy"):
    print(f"\n{'='*70}\n  AutoResearch v3.8 | {topic} | {mode}\n{'='*70}")
    e = Engine(topic, mode)
    rs, t0 = [], time.time()
    
    for rn in range(1, rounds + 1):
        cfg = e.suggest(rn, rounds)
        print(f"  >> R{rn} >> {cfg.srcs[:3]}... | {cfg.depth}")
        
        r = await e.run(cfg)
        r.rn = rn
        e.observe(r)
        rs.append(r)
        
        print(f"  [*] {r.n} findings (w={r.sc.get('w',0):.2f})")
    
    out = REPORTS_DIR / f"v38_{topic.replace(' ','_')}_{int(t0)}.html"
    Dash.gen(rs, topic, out)
    print(f"[OK] Dashboard: {out}")
    print(f"[OK] Complete: {len(rs)} rounds | {time.time()-t0:.1f}s")
    return rs

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=4)
    p.add_argument("--mode", default="karpathy")
    a = p.parse_args()
    if not a.topic: print("Usage: python autorun_evolve_v3.8.py <topic> [-r rounds]"); return
    asyncio.run(run(a.topic, a.rounds, a.mode))

if __name__ == "__main__":
    main()
