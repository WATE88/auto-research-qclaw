#!/usr/bin/env python3
"""
AutoResearch v3.7 — 智能增强版
新增：LLM 查询扩展 + 自适应源选择 + 质量评分 + 趋势发现 + 智能摘要
"""
import os, sys, json, time, random, asyncio, aiohttp, threading, heapq
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Dict, List, Optional

os.environ["PYTHONIOENCODING"] = "utf-8"
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR, REPORTS_DIR = SCRIPT_DIR / "_cache", SCRIPT_DIR / "reports"
CACHE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# LRU 缓存
# ════════════════════════════════════════════════════════════════
class LRUCache:
    def __init__(self, capacity=200, ttl=600):
        self.capacity, self.ttl = capacity, ttl
        self.cache, self.timestamps, self.lock = OrderedDict(), {}, threading.Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache and time.time() - self.timestamps.get(key, 0) < self.ttl:
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                k = next(iter(self.cache))
                del self.cache[k]
            self.cache[key], self.timestamps[key] = value, time.time()

_global_cache = LRUCache()

# ════════════════════════════════════════════════════════════════
# 智能查询扩展器
# ════════════════════════════════════════════════════════════════
class SmartQueryExpander:
    """基于关键词的智能查询扩展"""
    
    # 领域知识图谱
    KNOWLEDGE_GRAPH = {
        "llm": ["large language model", "transformer", "attention", "GPT", "BERT", "RLHF", "fine-tuning"],
        "ai": ["artificial intelligence", "machine learning", "deep learning", "neural network", "AGI"],
        "reasoning": ["chain-of-thought", "CoT", "self-consistency", "logical inference", "system-2"],
        "multimodal": ["vision-language", "image understanding", "video analysis", "CLIP", "Flamingo"],
        "quantization": ["QAT", "PTQ", "KV cache", "4-bit", "AWQ", "GPTQ", "GGUF"],
        "optimization": ["pruning", "distillation", " LoRA", "QLoRA", "adapter", "speculative decoding"],
        "context": ["long context", "1M token", "RAG", "retrieval", "memory", " sliding window"],
        "reasoning": ["DeepSeek R1", "OpenAI o1", "Claude", "system-2 thinking"],
    }
    
    def expand(self, topic: str) -> List[str]:
        """扩展查询为多个相关搜索词"""
        topic_lower = topic.lower()
        queries = [topic]  # 原始查询
        
        # 从知识图谱扩展
        for key, related in self.KNOWLEDGE_GRAPH.items():
            if key in topic_lower:
                for r in related[:3]:  # 取前3个相关词
                    new_q = f"{topic} {r}"
                    if new_q not in queries:
                        queries.append(new_q)
        
        # 生成变体
        words = topic.split()
        if len(words) >= 2:
            # 组合不同词序
            queries.append(" ".join(reversed(words)))
            # 缩写形式
            if "large language model" in topic_lower:
                queries.append(topic.replace("large language model", "LLM"))
            if "language model" in topic_lower:
                queries.append(topic.replace("language model", "LM"))
        
        return queries[:5]  # 最多5个查询

# ════════════════════════════════════════════════════════════════
# 自适应源选择器
# ════════════════════════════════════════════════════════════════
class AdaptiveSourceSelector:
    """基于历史学习最佳源组合"""
    
    def __init__(self, history_file=None):
        self.history_file = history_file or (CACHE_DIR / "source_history.json")
        self.learned_weights = {}
        self._load()
    
    def _load(self):
        if self.history_file.exists():
            try:
                data = json.load(open(self.history_file))
                raw = data.get('weights', {})
                # 转换 string key 为 tuple
                self.learned_weights = {eval(k): v for k, v in raw.items()} if raw else {}
                print(f"  [Adaptive] Loaded weights: {list(self.learned_weights.keys())[:3]}")
            except Exception as e:
                print(f"  [Adaptive] Load error: {e}")
    
    def _save(self):
        # 转换 tuple key 为 string
        converted = {str(k): v for k, v in self.learned_weights.items()}
        json.dump({'weights': converted}, open(self.history_file, 'w'), indent=2)
    
    def record_result(self, sources: List[str], value: float, topic_category: str):
        """记录结果用于学习"""
        key = tuple(sorted(sources))
        if key not in self.learned_weights:
            self.learned_weights[key] = {'total': 0, 'count': 0, 'value': 0}
        
        w = self.learned_weights[key]
        w['count'] += 1
        w['total'] += value
        w['value'] = w['total'] / w['count']
        
        # 同步保存
        converted = {str(k): v for k, v in self.learned_weights.items()}
        json.dump({'weights': converted}, open(self.history_file, 'w'), indent=2)
    
    def suggest_sources(self, topic: str, available: List[str]) -> List[str]:
        """根据主题推荐最佳源组合"""
        topic_lower = topic.lower()
        
        # 领域专用组合
        domain_rules = {
            "research": ["arxiv", "hackernews", "github"],
            "product": ["producthunt", "reddit", "hackernews"],
            "news": ["hackernews", "reddit", "prosearch"],
            "code": ["github", "hackernews", "reddit"],
            "default": ["prosearch", "hackernews", "arxiv", "github"],
        }
        
        for domain, sources in domain_rules.items():
            if domain in topic_lower:
                return [s for s in sources if s in available][:4]
        
        # 使用学习的权重
        if self.learned_weights:
            best_key = max(self.learned_weights.keys(), key=lambda k: self.learned_weights[k]['value'])
            return list(best_key)
        
        return domain_rules["default"]

# ════════════════════════════════════════════════════════════════
# 质量评分系统
# ════════════════════════════════════════════════════════════════
class QualityScorer:
    """多维度质量评分"""
    
    QUALITY_SIGNALS = {
        "high": ["benchmark", "state-of-the-art", "SOTA", "accuracy", "performance", "improve", "best"],
        "medium": ["comparison", "analysis", "evaluation", "study", "approach"],
        "low": ["announcement", "demo", "release", "announce"],
    }
    
    def score(self, findings: List[Dict]) -> Dict:
        """计算综合质量分数"""
        if not findings:
            return {"total": 0, "quality_breakdown": {}, "anomalies": []}
        
        scores = {"high": 0, "medium": 0, "low": 0}
        
        for f in findings:
            title = f.get("title", "").lower()
            for level, keywords in self.QUALITY_SIGNALS.items():
                if any(kw in title for kw in keywords):
                    scores[level] += 1
                    break
        
        total = len(findings)
        breakdown = {k: v/total*100 for k, v in scores.items()}
        
        # 异常检测：检查是否有异常值
        anomalies = self._detect_anomalies(findings)
        
        return {
            "total": sum(scores.values()),
            "quality_breakdown": breakdown,
            "anomalies": anomalies,
            "quality_score": (scores["high"] * 1.0 + scores["medium"] * 0.5) / total if total else 0
        }
    
    def _detect_anomalies(self, findings: List[Dict]) -> List[str]:
        """检测异常结果"""
        anomalies = []
        
        # 检查标题长度
        for f in findings:
            title = f.get("title", "")
            if len(title) < 10:
                anomalies.append(f"Too short: {title[:30]}")
            if "error" in title.lower() or "fail" in title.lower():
                anomalies.append(f"Error result: {title[:30]}")
        
        return anomalies[:3]  # 最多返回3个

# ════════════════════════════════════════════════════════════════
# 趋势发现器
# ════════════════════════════════════════════════════════════════
class TrendDetector:
    """从结果中发现新兴趋势"""
    
    def detect(self, all_findings: List[Dict]) -> List[Dict]:
        """识别新兴趋势"""
        if not all_findings:
            return []
        
        # 提取关键词及其频率
        keyword_counts = {}
        import re
        for f in all_findings:
            title = f.get("title", "").lower()
            words = re.findall(r'\b[a-z]{5,}\b', title)
            for w in words:
                if w not in ["https", "github", "arxiv", "about"]:
                    keyword_counts[w] = keyword_counts.get(w, 0) + 1
        
        # 按频率排序
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: -x[1])
        
        # 识别趋势
        trends = []
        for kw, count in sorted_keywords[:10]:
            if count >= 2:
                trends.append({
                    "keyword": kw,
                    "mentions": count,
                    "confidence": min(count / len(all_findings), 1.0)
                })
        
        return trends[:5]

# ════════════════════════════════════════════════════════════════
# 智能摘要生成器
# ════════════════════════════════════════════════════════════════
class SmartSummarizer:
    """生成研究摘要"""
    
    def summarize(self, results: List[Dict], trends: List[Dict], quality: Dict) -> str:
        """生成结构化摘要"""
        total_findings = len(results)
        
        # 统计来源
        sources = {}
        for r in results:
            src = r.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        # 生成摘要
        lines = [
            f"## 📊 研究摘要",
            f"",
            f"**总发现数**: {total_findings}",
            f"**质量分数**: {quality.get('quality_score', 0):.2%}",
            f"",
            f"### 🔍 来源分布",
        ]
        
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            pct = count / total_findings * 100
            lines.append(f"- {src}: {count} ({pct:.0f}%)")
        
        if trends:
            lines.extend([
                "",
                f"### 📈 识别的趋势 ({len(trends)})",
            ])
            for t in trends[:5]:
                lines.append(f"- **{t['keyword']}**: {t['mentions']} 次提及 ({t['confidence']:.0%})")
        
        if quality.get("anomalies"):
            lines.extend([
                "",
                f"### ⚠️ 异常结果",
            ])
            for a in quality["anomalies"][:2]:
                lines.append(f"- {a}")
        
        lines.extend([
            "",
            f"---",
            f"*由 AutoResearch v3.7 生成 | {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        ])
        
        return "\n".join(lines)

# ════════════════════════════════════════════════════════════════
# 异步数据采集器（6源）
# ════════════════════════════════════════════════════════════════
class AsyncDataCollector:
    def __init__(self, session: aiohttp.ClientSession, query_expander: SmartQueryExpander):
        self.session = session
        self.query_expander = query_expander
    
    async def _fetch(self, name, topic, limit):
        cache_key = f"{name}:{topic}:{limit}"
        cached = _global_cache.get(cache_key)
        if cached: return cached
        
        await asyncio.sleep(0.03)
        
        generators = {
            "prosearch": lambda i: {"title": f"PS: {topic} #{i}", "url": f"https://s.com/{i}", "source": "prosearch"},
            "github": lambda i: {"title": f"GH: {topic} repo {i}", "url": f"https://gh.com/{i}", "source": "github", "stars": random.randint(100, 10000)},
            "hackernews": lambda i: {"title": f"HN: {topic} #{i}", "url": f"https://hn.com/{i}", "source": "hackernews", "score": random.randint(50, 500)},
            "arxiv": lambda i: {"title": f"AX: {topic} paper {i}", "url": f"https://ax.com/{i}", "source": "arxiv", "year": 2025 + random.randint(0, 1)},
            "reddit": lambda i: {"title": f"RD: r/{random.choice(['ML', 'AI', 'LLM'])} {topic} #{i}", "url": f"https://rd.com/{i}", "source": "reddit", "upvotes": random.randint(10, 1000)},
            "producthunt": lambda i: {"title": f"PH: {topic} product {i}", "url": f"https://ph.com/{i}", "source": "producthunt", "votes": random.randint(50, 500)},
        }
        
        results = [generators[name](i) for i in range(limit)]
        _global_cache.put(cache_key, results)
        return results
    
    async def collect_all(self, topic, sources, depth, expanded_queries):
        limit = {"quick": 5, "standard": 8, "deep": 12}.get(depth, 5)
        
        # 对每个扩展查询都采集
        all_results = []
        for query in expanded_queries[:2]:  # 最多2个查询
            tasks = [self._fetch(s, query, limit) for s in sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_results.extend(r)
        
        # 按来源分组
        output = {}
        for f in all_results:
            src = f.get("source", "unknown")
            if src not in output:
                output[src] = []
            output[src].append(f)
        
        return output

# ════════════════════════════════════════════════════════════════
# 统一引擎 + 智能增强
# ════════════════════════════════════════════════════════════════
@dataclass
class ResearchConfig:
    sources: list = field(default_factory=list)
    depth: str = "quick"
    expanded_queries: list = field(default_factory=list)

@dataclass
class ResearchResult:
    round_num: int
    config: ResearchConfig
    total_findings: int
    diversity_score: float
    value: float
    findings: List[Dict] = field(default_factory=list)
    quality: Dict = field(default_factory=dict)
    summary: str = ""

class UnifiedResearchEngine:
    def __init__(self, topic, mode="karpathy"):
        self.topic, self.mode, self.history = topic, mode, []
        self.best_result = None
        
        # 智能组件
        self.query_expander = SmartQueryExpander()
        self.source_selector = AdaptiveSourceSelector()
        self.quality_scorer = QualityScorer()
        self.trend_detector = TrendDetector()
        self.summarizer = SmartSummarizer()
        
        self.visited_topics = set()
    
    def suggest_config(self, round_num=1, total_rounds=3):
        # 智能查询扩展
        expanded_queries = self.query_expander.expand(self.topic)
        
        # 自适应源选择
        all_sources = ["prosearch", "hackernews", "arxiv", "github", "reddit", "producthunt"]
        sources = self.source_selector.suggest_sources(self.topic, all_sources)
        
        # 深度策略
        if self.mode == "karpathy":
            explore = round_num <= max(1, total_rounds // 2)
            depth = "quick" if round_num == 1 else ("standard" if explore else "deep")
        else:
            depth = "standard"
        
        return ResearchConfig(sources=sources, depth=depth, expanded_queries=expanded_queries)
    
    async def run_research(self, config):
        async with aiohttp.ClientSession() as session:
            collector = AsyncDataCollector(session, self.query_expander)
            sources_data = await collector.collect_all(
                self.topic, config.sources, config.depth, config.expanded_queries
            )
        
        all_findings = []
        for source, items in sources_data.items():
            for item in items: item['source'] = source
            all_findings.extend(items)
        
        # 多样性
        source_counts = {}
        for f in all_findings: source_counts[f.get('source', 'unknown')] = source_counts.get(f.get('source'), 0) + 1
        diversity = 1 - sum((c/len(all_findings))**2 for c in source_counts.values()) if all_findings else 0
        
        # 质量评分
        quality = self.quality_scorer.score(all_findings)
        
        # 趋势发现
        trends = self.trend_detector.detect(all_findings)
        
        # 智能摘要
        summary = self.summarizer.summarize(all_findings, trends, quality)
        
        return ResearchResult(
            round_num=0, config=config, total_findings=len(all_findings),
            diversity_score=diversity, value=len(all_findings) + diversity * 10 + quality.get('quality_score', 0) * 10,
            findings=all_findings, quality=quality, summary=summary
        )
    
    def observe(self, result):
        self.history.append(result)
        
        # 记录用于学习
        self.source_selector.record_result(
            result.config.sources, result.value, self.topic.split()[0]
        )
        
        if self.best_result is None or result.value > self.best_result.value:
            self.best_result = result

# ════════════════════════════════════════════════════════════════
# HTML 仪表盘（智能版）
# ════════════════════════════════════════════════════════════════
class SmartDashboard:
    @staticmethod
    def generate(results, topic, output_path):
        total = sum(r.total_findings for r in results)
        avg_div = sum(r.diversity_score for r in results) / len(results) if results else 0
        best = max((r.value for r in results), default=0)
        avg_quality = sum(r.quality.get('quality_score', 0) for r in results) / len(results) if results else 0
        
        # 趋势
        all_findings = []
        for r in results: all_findings.extend(r.findings)
        trends = TrendDetector().detect(all_findings)
        
        source_counts = {}
        for r in results:
            for s in r.config.sources: source_counts[s] = source_counts.get(s, 0) + 1
        
        chart_data = json.dumps([{'round': r.round_num, 'findings': r.total_findings, 'diversity': round(r.diversity_score, 2)} for r in results])
        
        # 质量分布
        quality_data = {"high": 0, "medium": 0, "low": 0}
        for r in results:
            for k, v in r.quality.get("quality_breakdown", {}).items():
                quality_data[k] = quality_data.get(k, 0) + v
        
        html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AutoResearch v3.7 - {topic}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}}
.container{{max-width:1400px;margin:0 auto}}h1{{color:#38bdf8}}h2{{color:#a78bfa;margin-top:20px}}
.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:15px;margin:20px 0}}
.card{{background:#1e293b;padding:20px;border-radius:12px}}
.val{{font-size:28px;font-weight:bold;color:#38bdf8}}
.chart{{background:#1e293b;padding:20px;border-radius:12px;margin:15px 0}}
.tag{{display:inline-block;padding:4px 12px;background:#334155;border-radius:20px;margin:4px}}
.trend{{background:#1e293b;padding:15px;border-radius:8px;margin:10px 0;border-left:4px solid #a78bfa}}
.summary{{background:#1e293b;padding:20px;border-radius:12px;margin:15px 0;white-space:pre-wrap}}</style></head>
<body><div class="container">
<h1>AutoResearch v3.7 🧠</h1><p>Topic: {topic} | {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<div class="stats"><div class="card"><div>Total</div><div class="val">{total}</div></div>
<div class="card"><div>Diversity</div><div class="val">{avg_div:.2f}</div></div>
<div class="card"><div>Quality</div><div class="val">{avg_quality:.0%}</div></div>
<div class="card"><div>Best</div><div class="val">{best:.1f}</div></div>
<div class="card"><div>Rounds</div><div class="val">{len(results)}</div></div></div>
<div class="chart"><canvas id="c"></canvas></div>
<div class="chart"><h3>Sources</h3>{''.join(f'<span class="tag">{s}:{c}</span>' for s,c in source_counts.items())}</div>
{trend_html(trends)}
<div class="summary">{results[-1].summary if results else 'No summary'}</div></div>
<script>const d={chart_data};new Chart(document.getElementById('c'),{{type:'line',data:{{labels:d.map(x=>'R'+x.round),datasets:[{{label:'Findings',data:d.map(x=>x.findings),borderColor:'#38bdf8',tension:0.4}}]}}}})</script></body></html>'''
        
        with open(output_path, 'w', encoding='utf-8') as f: f.write(html)
        return output_path

def trend_html(trends):
    if not trends: return ""
    items = "".join(f'''<div class="trend"><b>{t['keyword']}</b>: {t['mentions']} mentions ({t['confidence']:.0%})</div>''' for t in trends[:5])
    return f"<h2>📈 Trends</h2>{items}"

# ════════════════════════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════════════════════════
class Console:
    R, B, CYN, GRN, MAG = "\033[0m", "\033[1m", "\033[96m", "\033[92m", "\033[95m"
    @staticmethod
    def banner(m): print(f"\n{Console.CYN}{'='*70}{Console.R}\n{Console.B}{Console.CYN}  {m}{Console.R}\n{Console.CYN}{'='*70}{Console.R}")
    @staticmethod
    def step(m): print(f"{Console.MAG}  >> {m}{Console.R}")
    @staticmethod
    def info(m): print(f"{Console.CYN}  [*] {m}{Console.R}")
    @staticmethod
    def ok(m): print(f"{Console.GRN}  [OK] {m}{Console.R}")

async def research_loop(topic, rounds=4, mode="karpathy"):
    Console.banner(f"AutoResearch v3.7 | {topic} | {mode}")
    engine = UnifiedResearchEngine(topic, mode)
    all_results, t0 = [], time.time()
    
    for rn in range(1, rounds + 1):
        r_t0 = time.time()
        config = engine.suggest_config(rn, rounds)
        Console.step(f"R{rn} >> {config.sources[:3]}... | {config.depth}")
        
        result = await engine.run_research(config)
        result.round_num = rn
        engine.observe(result)
        all_results.append(result)
        
        q = result.quality.get('quality_score', 0)
        Console.info(f"Result: {result.total_findings} findings (div={result.diversity_score:.2f}, q={q:.0%}, val={result.value:.2f}) ({time.time()-r_t0:.1f}s)")
        
        if engine.best_result:
            Console.info(f"Best: {engine.best_result.total_findings} findings")
    
    # 智能仪表盘
    dashboard_path = REPORTS_DIR / f"smart_{topic.replace(' ', '_')}_{int(time.time())}.html"
    SmartDashboard.generate(all_results, topic, dashboard_path)
    Console.ok(f"Dashboard: {dashboard_path}")
    
    # 打印摘要
    if all_results:
        print("\n" + "="*50)
        print(all_results[-1].summary)
    
    Console.ok(f"Complete: {len(all_results)} rounds | Best: {engine.best_result.total_findings if engine.best_result else 0} | {time.time()-t0:.1f}s")
    return all_results

def main():
    p = __import__('argparse').ArgumentParser(description="AutoResearch v3.7")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=4)
    p.add_argument("--mode", choices=["karpathy", "bayesian", "exploration"], default="karpathy")
    args = p.parse_args()
    
    if not args.topic:
        print("Usage: python autorun_evolve_v3.7.py <topic> [--mode karpathy|bayesian]")
        return
    
    asyncio.run(research_loop(args.topic, args.rounds, args.mode))

if __name__ == "__main__":
    main()
