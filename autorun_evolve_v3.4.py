#!/usr/bin/env python3
"""
autorun_evolve_v3.4.py — QClaw AutoResearch 统一版本
融合：自主进化 (v3.2) + 自主探索 (v3.2) + 贝叶斯优化 (v3.3)
"""
import os, sys, io, json, time, uuid, argparse, hashlib, re, urllib.request, urllib.parse, math, random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict

# ── UTF-8 ──────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR  = SCRIPT_DIR / "_cache"
CACHE_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 贝叶斯优化核心
# ════════════════════════════════════════════════════════════════

class GaussianProcess:
    """简化的高斯过程"""
    def __init__(self, kernel_scale=1.0, noise=0.1):
        self.X = []
        self.y = []
        self.kernel_scale = kernel_scale
        self.noise = noise
    
    def _rbf_kernel(self, x1, x2):
        dist_sq = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return self.kernel_scale * math.exp(-dist_sq / 2)
    
    def fit(self, X, y):
        self.X = [list(x) for x in X]
        self.y = list(y)
    
    def predict(self, x_new):
        if not self.X:
            return 0.0, 1.0
        weights = [self._rbf_kernel(x_new, x) for x in self.X]
        total_w = sum(weights)
        if total_w < 1e-10:
            return 0.0, 1.0
        mu = sum(w * y for w, y in zip(weights, self.y)) / total_w
        sigma = 1.0 / (1.0 + total_w)
        return mu, sigma

class BayesianOptimizer:
    """贝叶斯优化器"""
    def __init__(self, param_space, acquisition="ei", n_warmup=2):
        self.param_space = param_space
        self.acquisition = acquisition
        self.n_warmup = n_warmup
        self.gp = GaussianProcess()
        self.history = []
        self.best_value = -float('inf')
        self.best_params = None
    
    def _encode_params(self, params):
        vec = []
        for name in sorted(self.param_space.keys()):
            val = params.get(name, 0)
            min_v, max_v, _ = self.param_space[name]
            normalized = (val - min_v) / (max_v - min_v + 1e-10)
            vec.append(normalized)
        return vec
    
    def _decode_params(self, vec):
        params = {}
        for i, name in enumerate(sorted(self.param_space.keys())):
            min_v, max_v, ptype = self.param_space[name]
            val = min_v + vec[i] * (max_v - min_v)
            if ptype == 'int':
                val = int(round(val))
            params[name] = val
        return params
    
    def suggest(self):
        if len(self.history) < self.n_warmup:
            params = {}
            for name, (min_v, max_v, ptype) in self.param_space.items():
                if ptype == 'int':
                    params[name] = random.randint(min_v, max_v)
                else:
                    params[name] = random.uniform(min_v, max_v)
            return params
        
        X = [self._encode_params(h['params']) for h in self.history]
        y = [h['value'] for h in self.history]
        self.gp.fit(X, y)
        
        best_acq = -float('inf')
        best_vec = None
        
        for _ in range(10):
            vec = [random.uniform(0, 1) for _ in range(len(self.param_space))]
            mu, sigma = self.gp.predict(vec)
            
            if self.acquisition == "ei":
                acq = (mu - self.best_value) * sigma
            else:
                acq = mu + 2.0 * sigma
            
            if acq > best_acq:
                best_acq = acq
                best_vec = vec
        
        return self._decode_params(best_vec) if best_vec else self.suggest()
    
    def observe(self, params, value):
        self.history.append({'params': params, 'value': value})
        if value > self.best_value:
            self.best_value = value
            self.best_params = params

# ── 控制台样式 ─────────────────────────────────────────────────
class C:
    R   = "\033[0m"
    B   = "\033[1m"
    CYN = "\033[96m"
    GRN = "\033[92m"
    MAG = "\033[95m"

    @staticmethod
    def p(msg, c="", bold=False):
        pre = (C.B if bold else "") + c
        print(f"{pre}{msg}{C.R}", flush=True)

    @staticmethod
    def banner(msg):
        print()
        C.p("=" * 62, c=C.CYN)
        C.p(f"  {msg}", c=C.CYN, bold=True)
        C.p("=" * 62, c=C.CYN)

    @staticmethod
    def step(msg):
        C.p(f"  >> {msg}", c=C.MAG)

    @staticmethod
    def info(msg):
        C.p(f"  [*] {msg}", c=C.CYN)

    @staticmethod
    def ok(msg):
        C.p(f"  [OK] {msg}", c=C.GRN)

# ════════════════════════════════════════════════════════════════
# 自主探索模块
# ════════════════════════════════════════════════════════════════

def extract_emerging_topics(findings, limit=5):
    """从搜索结果中提取新兴话题"""
    topics = {}
    for f in findings:
        title = f.get("title", "").lower()
        words = re.findall(r'\b[a-z]{4,}\b', title)
        for w in words:
            if w not in ["http", "https", "arxiv", "github"]:
                topics[w] = topics.get(w, 0) + 1
    
    sorted_topics = sorted(topics.items(), key=lambda x: -x[1])
    return [t[0] for t in sorted_topics[:limit]]

def generate_exploration_topics(base_topic, findings, history=None):
    """基于当前研究生成相关的探索主题"""
    emerging = extract_emerging_topics(findings, limit=5)
    base_words = set(base_topic.lower().split())
    filtered = [kw for kw in emerging if kw not in base_words]
    
    candidates = []
    for kw in filtered:
        if history and kw in [h.get('topic', '') for h in history]:
            continue
        new_topic = f"{base_topic} {kw}"
        candidates.append(new_topic)
    
    return candidates[:3]

# ════════════════════════════════════════════════════════════════
# 统一进化引擎 (v3.4)
# ════════════════════════════════════════════════════════════════

class UnifiedEvolutionEngine:
    """统一进化引擎：融合 Karpathy 闭环 + 自主探索 + 贝叶斯优化"""
    
    def __init__(self, topic, use_bayesian=False, use_exploration=False):
        self.topic = topic
        self.use_bayesian = use_bayesian
        self.use_exploration = use_exploration
        self.history = []
        self.best_value = -float('inf')
        self.best_config = None
        self.stall = 0
        
        if use_bayesian:
            self.param_space = {
                'num_sources': (2, 4, 'int'),
                'depth_level': (0, 2, 'int'),
            }
            self.optimizer = BayesianOptimizer(self.param_space, acquisition="ei", n_warmup=2)
    
    def suggest_config(self, round_num=1, total_rounds=3):
        """建议下一个配置"""
        if self.use_bayesian:
            # 贝叶斯优化模式
            params = self.optimizer.suggest()
            depth_map = {0: "quick", 1: "standard", 2: "deep"}
            sources = ["prosearch", "hackernews"]
            if params['num_sources'] >= 3:
                sources.append("arxiv")
            if params['num_sources'] >= 4:
                sources.append("github")
            return {'sources': sources, 'depth': depth_map[params['depth_level']]}
        else:
            # Karpathy 闭环模式
            explore_phase = round_num <= max(1, total_rounds // 2)
            if explore_phase:
                sources = ["prosearch", "hackernews", "arxiv"]
                depth = "quick" if round_num == 1 else "standard"
            else:
                sources = ["prosearch", "hackernews", "arxiv", "github"]
                depth = "deep"
            return {'sources': sources, 'depth': depth}
    
    def observe(self, result):
        """记录观测"""
        value = result.get('total_findings', 0) + result.get('diversity_score', 0) * 10
        
        if self.use_bayesian:
            params = {
                'num_sources': len(result.get('sources', [])),
                'depth_level': {'quick': 0, 'standard': 1, 'deep': 2}.get(result.get('depth', 'quick'), 1),
            }
            self.optimizer.observe(params, value)
        
        self.history.append({'result': result, 'value': value})
        
        if value > self.best_value:
            self.best_value = value
            self.best_config = result
            self.stall = 0
        else:
            self.stall += 1

# ════════════════════════════════════════════════════════════════
# 模拟研究函数
# ════════════════════════════════════════════════════════════════

def run_round(topic, sources, depth):
    """执行单轮研究（模拟）"""
    base = 10
    base += len(sources) * 5
    base += {'quick': 0, 'standard': 5, 'deep': 10}.get(depth, 0)
    findings = base + random.randint(-2, 2)
    
    return {
        'total_findings': findings,
        'sources': sources,
        'depth': depth,
        'diversity_score': 0.5 + random.random() * 0.3,
        'findings': [{'title': f'Result {i}'} for i in range(findings)],
    }

# ════════════════════════════════════════════════════════════════
# 统一进化主循环
# ════════════════════════════════════════════════════════════════

def evolve_unified(topic, rounds=4, use_bayesian=False, use_exploration=False):
    """统一进化"""
    mode = []
    if use_bayesian:
        mode.append("Bayesian")
    if use_exploration:
        mode.append("Exploration")
    if not mode:
        mode.append("Karpathy")
    
    C.banner(f"AutoResearch v3.4 | {topic} | {' + '.join(mode)}")
    print()
    
    engine = UnifiedEvolutionEngine(topic, use_bayesian, use_exploration)
    all_results = []
    t0 = time.time()
    
    for rn in range(1, rounds + 1):
        r_t0 = time.time()
        
        # 建议配置
        config = engine.suggest_config(rn, rounds)
        sources = config['sources']
        depth = config['depth']
        
        C.step(f"R{rn} >> sources={sources}, depth={depth}")
        
        # 执行研究
        result = run_round(topic, sources, depth)
        result['round'] = rn
        
        # 记录观测
        engine.observe(result)
        all_results.append(result)
        
        took = time.time() - r_t0
        C.info(f"Result: {result['total_findings']} findings ({took:.0f}s)")
        
        # 显示最优
        if engine.best_config:
            C.info(f"Best so far: {engine.best_config['total_findings']} findings (value={engine.best_value:.2f})")
        
        # 检查停止条件
        if engine.stall >= 2:
            C.info("Stall detected, stopping")
            break
    
    elapsed = time.time() - t0
    best = max(all_results, key=lambda r: r['total_findings'], default=None)
    
    print()
    C.ok(f"Complete: {len(all_results)} rounds | Best: {best['total_findings'] if best else 0} findings | {elapsed:.0f}s")
    
    return all_results, elapsed

def evolve_with_exploration(topic, max_iterations=3):
    """自主探索模式"""
    C.banner(f"AutoResearch v3.4 | Autonomous Exploration | {topic}")
    print()
    
    all_history = []
    current_topic = topic
    
    for iteration in range(max_iterations):
        C.p(f"\n[Iteration {iteration + 1}/{max_iterations}] Topic: {current_topic}", bold=True)
        
        # 执行一轮研究
        results, elapsed = evolve_unified(current_topic, rounds=2, use_bayesian=False, use_exploration=False)
        all_history.extend(results)
        
        if not results:
            break
        
        # 提取新主题
        findings = results[-1].get('findings', [])
        candidates = generate_exploration_topics(current_topic, findings, all_history)
        
        if not candidates:
            C.info("No new topics, stopping")
            break
        
        current_topic = candidates[0]
        C.info(f"Next topic: {current_topic}")
    
    C.ok(f"Exploration complete: {len(all_history)} rounds")
    return all_history

# ── 主入口 ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="AutoResearch v3.4 Unified")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=4)
    p.add_argument("--bayesian", action="store_true", help="Enable Bayesian optimization")
    p.add_argument("--explore", action="store_true", help="Enable autonomous exploration")
    p.add_argument("--explore-depth", type=int, default=3, help="Exploration depth")
    args = p.parse_args()
    
    if not args.topic:
        print("Usage: python autorun_evolve_v3.4.py <topic> [--bayesian] [--explore]")
        return
    
    if args.explore:
        evolve_with_exploration(args.topic, max_iterations=args.explore_depth)
    else:
        evolve_unified(args.topic, rounds=args.rounds, use_bayesian=args.bayesian, use_exploration=False)

if __name__ == "__main__":
    main()
