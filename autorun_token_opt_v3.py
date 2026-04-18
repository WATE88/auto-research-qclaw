#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoResearch Token Optimization v3.0 - Multi-source + Self-evolution"""
from __future__ import annotations
import os, sys, json, time, asyncio, aiohttp, signal
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import Counter
from typing import Optional, Dict, List, Any
import platform

def get_workspace():
    if os.environ.get("AUTORESEARCH_HOME"):
        return Path(os.environ["AUTORESEARCH_HOME"])
    return Path(os.environ.get("USERPROFILE","~")) / ".qclaw" / "workspace" / "autoresearch"

WORKSPACE = get_workspace()
CACHE_DIR = WORKSPACE / "_cache"
REPORTS_DIR = WORKSPACE / "reports"
FINDINGS_DIR = WORKSPACE / "findings"
STATS_DIR = WORKSPACE / "_stats"
PROGRESS_FILE = WORKSPACE / "progress_v3.json"
for d in [CACHE_DIR, REPORTS_DIR, FINDINGS_DIR, STATS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

@dataclass
class Config:
    version: str = "3.0"
    batch_size: int = 15
    cache_ttl_hours: int = 48
    min_report_grade: str = "B+"
    max_items_per_source: int = 30
    github_token: str = ""
    hf_token: str = ""
    sources: List[str] = field(default_factory=lambda: ["github"])
    weights: Dict[str, float] = field(default_factory=lambda: {
        "authority": 0.30, "academic": 0.20, "stars": 0.15,
        "forks": 0.10, "issues": 0.10, "recency": 0.10, "diversity": 0.05,
    })
    topics: List[str] = field(default_factory=lambda: [
        "AI agent framework", "LLM benchmark evaluation", "RAG evaluation",
        "model quantization", "speculative decoding", "KV cache optimization",
        "LLM inference optimization", "AI coding assistant", "multimodal LLM",
        "transformer architecture", "AI research tool", "knowledge graph RAG",
        "LLM training optimization", "AI agent memory system", "model compression",
        "chain of thought prompting", "embedding models", "neural architecture search",
        "LLM reasoning", "diffusion models", "text to speech",
    ])

    @classmethod
    def load(cls) -> "Config":
        f = WORKSPACE / "config.json"
        if f.exists():
            try:
                data = json.load(open(f, "r", encoding="utf-8"))
                known = set(cls.__dataclass_fields__.keys())
                return cls(**{k: v for k, v in data.items() if k in known})
            except: pass
        return cls()

    def save(self):
        with open(WORKSPACE / "config.json", "w", encoding="utf-8") as fp:
            json.dump(asdict(self), fp, ensure_ascii=False, indent=2)

@dataclass
class TopicStats:
    runs: int = 0; total_score: float = 0.0
    grades: List[str] = field(default_factory=list)
    avg_items: float = 0.0; last_run: str = ""
    best_score: float = 0.0; best_grade: str = "F"

    @property
    def avg_score(self) -> float:
        return self.total_score / self.runs if self.runs else 0.0

    def update(self, score: float, grade: str, n: int):
        self.runs += 1; self.total_score += score; self.grades.append(grade)
        self.last_run = datetime.now().isoformat()
        self.avg_items = (self.avg_items*(self.runs-1)+n)/self.runs
        if score > self.best_score:
            self.best_score = score; self.best_grade = grade

    def grade_score(self) -> float:
        gm = {"A":1.0,"B":0.75,"C":0.5,"D":0.25,"F":0.0,"B+":0.82}
        gs = sum(gm.get(g,0) for g in self.grades)/max(len(self.grades),1)
        return self.avg_score*0.5 + gs*0.5

class TopicTracker:
    def __init__(self):
        self.stats: Dict[str,TopicStats] = {}; self._load()

    def _load(self):
        f = STATS_DIR / "topic_stats.json"
        if f.exists():
            try:
                for k,v in json.load(open(f,"r",encoding="utf-8")).items():
                    self.stats[k] = TopicStats(**v)
            except: pass

    def save(self):
        f = STATS_DIR / "topic_stats.json"
        with open(f,"w",encoding="utf-8") as fp:
            json.dump({k: asdict(v) for k,v in self.stats.items()}, fp, ensure_ascii=False, indent=2)

    def update(self, topic, score, grade, n):
        if topic not in self.stats: self.stats[topic] = TopicStats()
        self.stats[topic].update(score, grade, n); self.save()

    def get_hints(self) -> Dict[str, List[str]]:
        h = {"hot":[],"warm":[],"cold":[]}
        for t,s in self.stats.items():
            gs = s.grade_score()
            if gs >= 0.75: h["hot"].append(t)
            elif gs >= 0.4: h["warm"].append(t)
            else: h["cold"].append(t)
        return h

class TokenBudget:
    def __init__(self):
        self.gh_calls=0; self.hf_calls=0; self.rate_limited=0; self.start=time.time()
    def gh(self, ok, cached=False):
        if not cached: self.gh_calls += 1
        if not ok: self.rate_limited += 1
    def hf(self): self.hf_calls += 1
    def report(self):
        e = time.time()-self.start; t = self.gh_calls+self.hf_calls
        return {"gh":self.gh_calls,"lim":self.rate_limited,"hf":self.hf_calls,
                "total":t,"sec":round(e,1),"pm":round(t/max(e/60,.1),1)}

class SmartCache:
    def __init__(self, ttl=48): self.ttl=ttl*3600
    def _key(self, t, s): return f"{s}:{t.lower().strip().replace(' ','-')}"
    def get(self, t, s="github") -> Optional[Dict]:
        f = CACHE_DIR/f"{self._key(t,s)}.json"
        if not f.exists(): return None
        try:
            d = json.load(open(f,"r",encoding="utf-8"))
            qs = d.get("quality_score", .5); ttl = self.ttl*(1.5-qs)
            if time.time()-d.get("_at",0) > ttl: return None
            return d
        except: return None
    def set(self, t, s, d):
        f = CACHE_DIR/f"{self._key(t,s)}.json"; d["_at"] = time.time()
        try: json.dump(d, open(f,"w",encoding="utf-8"), ensure_ascii=False)
        except: pass

HIGH_KW = ["benchmark","tutorial","guide","SOTA","NeurIPS","ICML","evaluation",
           "framework","survey","review","ACL","EMNLP","COLING","AAAI","IJCAI","arxiv","paper"]

class EnhancedScorer:
    def __init__(self, w=None):
        self.w = w or Config.load().weights
    def score(self, items: List[Dict], topic: str) -> Dict[str, Any]:
        if not items: return {"total":0,"quality_score":0.0,"grade":"F","dims":{}}
        n=len(items); d={}; d["authority"]=0.88
        ac = sum(1 for i in items if any(kw in ((i.get("title","") or "")+(i.get("description","") or "")).lower() for kw in HIGH_KW))/n
        d["academic"]=round(ac,3)
        ss=[i.get("stars",0) for i in items if i.get("stars",0)>0]
        ms=max(ss) if ss else 1
        d["stars"]=round(sum(min(s/ms,1) for s in ss)/len(ss) if ss else 0,3)
        fs=[i.get("forks",0) for i in items if i.get("forks",0)>0]
        mf=max(fs) if fs else 1
        d["forks"]=round(sum(min(f/mf,1) for f in fs)/len(fs) if fs else 0,3)
        iss=[i.get("open_issues",0) for i in items if i.get("open_issues",0)>0]
        mi=max(iss) if iss else 1
        d["issues"]=round(sum(min(i/mi,1) for i in iss)/len(iss) if iss else 0,3)
        now=datetime.now(); rs=[]
        for i in items:
            u=i.get("updated","") or i.get("last_modified","")
            if u:
                try:
                    up=datetime.fromisoformat(u.replace("Z","+00:00"))
                    age=(now-up.replace(tzinfo=None)).days
                    rs.append(max(.0,1-age/365))
                except: rs.append(.3)
            else: rs.append(.3)
        d["recency"]=round(sum(rs)/len(rs),3)
        ls=[len(i.get("description","") or "") for i in items]; ml=max(ls) if ls else 1
        d["diversity"]=round(sum(min(l/ml,1) for l in ls)/n,3)
        score=sum(self.w.get(k,0)*v for k,v in d.items())
        g="F" if score<.25 else "D" if score<.4 else "C" if score<.55 else "B" if score<.68 else "B+" if score<.78 else "A"
        return {"total":n,"quality_score":round(score,4),"grade":g,"dims":d,"w":self.w}

class MultiFetcher:
    def __init__(self, cache, budget, cfg):
        self.cache=cache; self.budget=budget; self.cfg=cfg
        self.hdr={"Accept":"application/vnd.github.v3+json"}
        if cfg.github_token: self.hdr["Authorization"]=f"token {cfg.github_token}"
    async def gh(self, topic) -> List[Dict]:
        c=self.cache.get(topic,"github")
        if c:
            self.budget.gh(True,cached=True); print(f"  [CACHE:G] {topic}"); return c.get("items",[])
        params={"q":topic,"sort":"stars","order":"desc","per_page":self.cfg.max_items_per_source}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.github.com/search/repositories",params=params,headers=self.hdr,timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status==403:
                        self.budget.gh(False); print(f"  [LIMIT:G] {topic} - rate limited"); return []
                    if r.status!=200:
                        self.budget.gh(False); print(f"  [ERR:G] {topic} HTTP {r.status}"); return []
                    data=await r.json()
                    items=[{"title":x.get("full_name",""),"url":x.get("html_url",""),
                            "description":x.get("description",""),"stars":x.get("stargazers_count",0),
                            "forks":x.get("forks_count",0),"open_issues":x.get("open_issues_count",0),
                            "updated":x.get("updated_at",""),"language":x.get("language",""),
                            "source":"github"} for x in data.get("items",[])]
                    self.cache.set(topic,"github",{"items":items}); self.budget.gh(True)
                    print(f"  [GITHUB] {topic} -> {len(items)} items"); return items
        except Exception as e:
            self.budget.gh(False); print(f"  [ERR:G] {topic} {e}"); return []
    async def hf(self, topic) -> List[Dict]:
        c=self.cache.get(topic,"hf_models")
        if c: print(f"  [CACHE:HF] {topic}"); return c.get("items",[])
        h={} if not self.cfg.hf_token else {"Authorization":f"Bearer {self.cfg.hf_token}"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://huggingface.co/api/models",params={"search":topic,"sort":"downloads","direction":-1,"limit":15},headers=h,timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status!=200: print(f"  [ERR:HF] {topic} HTTP {r.status}"); return []
                    data=await r.json()
                    items=[{"title":x.get("id",""),"url":f"https://huggingface.co/{x.get('id','')}",
                            "description":str(x.get("cardData",{}).get("base_model",x.get("pipeline_tag",""))),
                            "stars":x.get("likes",0),"forks":0,"open_issues":0,
                            "updated":x.get("last_modified",""),"downloads":x.get("downloads",0),
                            "source":"huggingface"} for x in data if isinstance(x,dict)]
                    self.cache.set(topic,"hf_models",{"items":items}); self.budget.hf()
                    print(f"  [HF:MODELS] {topic} -> {len(items)} items"); return items
        except Exception as e:
            print(f"  [ERR:HF] {topic} {e}"); return []
    async def all(self, topic) -> List[Dict]:
        tasks=[]
        if "github" in self.cfg.sources: tasks.append(self.gh(topic))
        if "huggingface" in self.cfg.sources: tasks.append(self.hf(topic))
        rs=await asyncio.gather(*tasks,return_exceptions=True)
        items=[]
        for r in rs: items.extend(r if isinstance(r,list) else [])
        return items

GRADE_ORDER=["F","D","C","B","B+","A"]
DIM_ZH={"authority":"Authority","academic":"Academic","stars":"Stars","forks":"Forks","issues":"Activity","recency":"Freshness","diversity":"Diversity"}

class Reporter:
    def __init__(self, min_grade="B+"): self.min_grade=min_grade
    def should_report(self, grade):
        try: return GRADE_ORDER.index(grade) >= GRADE_ORDER.index(self.min_grade)
        except: return grade == self.min_grade
    def generate(self, result) -> Optional[Path]:
        g=result["quality"]["grade"]
        if not self.should_report(g): return None
        t=result["topic"]; score=result["quality"]["quality_score"]; finds=result["findings"]
        dims=result["quality"]["dims"]; ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        st=t[:30].replace(" ","_").replace("/","_")
        md=f"# {t}\n\n**Score**: {score:.4f} ({g}) | {len(finds)} findings\n\n## Dimensions\n\n| Dimension | Score | Weight |\n|---|---|---|\n"
        for k,v in dims.items():
            w=result["quality"].get("w",{}).get(k,0); md+=f"| {DIM_ZH.get(k,k)} | {v:.3f} | {w:.2f} |\n"
        md+="\n## Top Projects\n\n"
        by_s=sorted(finds,key=lambda x:x.get("stars",0),reverse=True)
        for i,f in enumerate(by_s[:8],1):
            md+=f"{i}. [**{f['title']}**]({f['url']}) stars:{f.get('stars',0)}"
            if f.get("forks"): md+=f" forks:{f.get('forks',0)}"
            if f.get("downloads"): md+=f" downloads:{f.get('downloads',0)}"
            md+=f"\n   {f.get('description','')[:120]}\n\n"
        md+=f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
        mp=REPORTS_DIR/f"token_opt_{st}_{ts}.md"
        with open(mp,"w",encoding="utf-8") as fp: fp.write(md)
        with open(REPORTS_DIR/f"token_opt_{st}_{ts}.json","w",encoding="utf-8") as fp: json.dump(result,fp,ensure_ascii=False,indent=2)
        return mp

def save_progress(results, rn=0):
    with open(PROGRESS_FILE,"w",encoding="utf-8") as fp:
        json.dump({"round":rn,"timestamp":datetime.now().isoformat(),
                   "results":[{"topic":r["topic"],"quality_score":r["quality"]["quality_score"],
                               "grade":r["quality"]["grade"],"n_findings":len(r["findings"]),
                               "sources":list(set(x["source"] for x in r["findings"]))} for r in results]},
                  fp,ensure_ascii=False,indent=2)

class Researcher:
    def __init__(self, cfg):
        self.cfg=cfg; self.cache=SmartCache(cfg.cache_ttl_hours); self.budget=TokenBudget()
        self.fetcher=MultiFetcher(self.cache,self.budget,cfg); self.scorer=EnhancedScorer(cfg.weights)
        self.tracker=TopicTracker(); self._stop=False
        if platform.system()=="Windows": signal.signal(signal.SIGINT,self._sig)
        else: signal.signal(signal.SIGTERM,self._sig)
    def _sig(self,s,f): print("\n[STOP] Saved progress..."); self._stop=True
    async def run(self, topic) -> Dict:
        items=await self.fetcher.all(topic)
        q=self.scorer.score(items,topic)
        self.tracker.update(topic,q["quality_score"],q["grade"],len(items))
        return {"topic":topic,"timestamp":datetime.now().isoformat(),"findings":items,"quality":q}
    async def batch(self, topics) -> List[Dict]:
        results=[]; total=len(topics)
        for i,t in enumerate(topics):
            if self._stop: print(f"\n[ABORT] {i}/{total}"); break
            print(f"\n[{i+1}/{total}] ",end="",flush=True)
            results.append(await self.run(t)); await asyncio.sleep(1)
        return results

async def main():
    print("="*65)
    print("AutoResearch Token Optimization v3.0 (Multi-source + Self-evolution)")
    print("="*65)
    cfg=Config.load(); cfg.save()
    r=Researcher(cfg); rp=Reporter(cfg.min_report_grade)
    topics=sys.argv[1:] if len(sys.argv)>1 else cfg.topics
    if r.tracker.stats:
        h=r.tracker.get_hints()
        if h["hot"]: print(f"[EVOLVE] Hot: {', '.join(h['hot'][:5])}")
        if h["cold"]: print(f"[EVOLVE] Cold: {', '.join(h['cold'][:3])}")
    print(f"\n[CONFIG] Topics:{len(topics)} Sources:{','.join(cfg.sources)} TTL:{cfg.cache_ttl_hours}h")
    print("-"*65)
    if PROGRESS_FILE.exists():
        try: pg=json.load(open(PROGRESS_FILE,"r",encoding="utf-8")); print(f"[RESUME] Round {pg.get('round',0)} - {len(pg.get('results',[]))} done")
        except: pass
    results=await r.batch(topics)
    grades=Counter(x["quality"]["grade"] for x in results)
    avg=sum(x["quality"]["quality_score"] for x in results)/max(len(results),1)
    br=r.budget.report()
    print("\n"+"="*65+"\n[RESULTS]\n"+"="*65)
    print(f"Grades: {dict(sorted(grades.items()))}")
    print(f"Avg: {avg:.4f} | API: GitHub {br['gh']}(lim {br['lim']}) HF {br['hf']}")
    print(f"Elapsed: {br['sec']}s ({br['pm']}/min)")
    n=0
    for result in results:
        p=rp.generate(result)
        if p: print(f"[REPORT] {p.name}"); n+=1
    print(f"\n[DONE] {n}/{len(results)} reports (grade>={cfg.min_report_grade})")
    save_progress(results)
    if r.tracker.get_hints()["hot"]: print(f"\n[EVOLVE] Best: {', '.join(r.tracker.get_hints()['hot'][:5])}")

if __name__=="__main__":
    if platform.system()=="Windows":
        import codecs; sys.stdout=codecs.getwriter("utf-8")(sys.stdout.buffer,"strict")
        sys.stderr=codecs.getwriter("utf-8")(sys.stderr.buffer,"strict")
    asyncio.run(main())
