#!/usr/bin/env python3
"""
autorun_evolve_v3.3.py — QClaw AutoResearch 贝叶斯优化版本
贝叶斯优化 + 高斯过程 + 获取函数（EI/UCB）
"""
import os, sys, io, json, time, uuid, argparse, hashlib, re, urllib.request, urllib.parse, math, random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# ── UTF-8 ──────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR  = SCRIPT_DIR / "_cache"
CACHE_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 贝叶斯优化核心 — 高斯过程 + 获取函数
# ════════════════════════════════════════════════════════════════

class GaussianProcess:
    """简化的高斯过程（用于贝叶斯优化）"""
    def __init__(self, kernel_scale=1.0, noise=0.1):
        self.X = []
        self.y = []
        self.kernel_scale = kernel_scale
        self.noise = noise
    
    def _rbf_kernel(self, x1, x2):
        """RBF 核函数"""
        dist_sq = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return self.kernel_scale * math.exp(-dist_sq / 2)
    
    def fit(self, X, y):
        """拟合高斯过程"""
        self.X = [list(x) for x in X]
        self.y = list(y)
    
    def predict(self, x_new):
        """预测均值和方差"""
        if not self.X:
            return 0.0, 1.0
        
        # 简化预测：加权平均
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
        """将参数编码为向量"""
        vec = []
        for name in sorted(self.param_space.keys()):
            val = params.get(name, 0)
            min_v, max_v, _ = self.param_space[name]
            normalized = (val - min_v) / (max_v - min_v + 1e-10)
            vec.append(normalized)
        return vec
    
    def _decode_params(self, vec):
        """将向量解码为参数"""
        params = {}
        for i, name in enumerate(sorted(self.param_space.keys())):
            min_v, max_v, ptype = self.param_space[name]
            val = min_v + vec[i] * (max_v - min_v)
            if ptype == 'int':
                val = int(round(val))
            params[name] = val
        return params
    
    def suggest(self):
        """建议下一个参数组合"""
        if len(self.history) < self.n_warmup:
            # 预热阶段：随机采样
            params = {}
            for name, (min_v, max_v, ptype) in self.param_space.items():
                if ptype == 'int':
                    params[name] = random.randint(min_v, max_v)
                else:
                    params[name] = random.uniform(min_v, max_v)
            return params
        
        # 贝叶斯优化阶段
        X = [self._encode_params(h['params']) for h in self.history]
        y = [h['value'] for h in self.history]
        self.gp.fit(X, y)
        
        # 网格搜索找最优获取函数值
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
        """记录观测"""
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
        C.p("═" * 62, c=C.CYN)
        C.p(f"  {msg}", c=C.CYN, bold=True)
        C.p("═" * 62, c=C.CYN)

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
# 贝叶斯优化进化引擎
# ════════════════════════════════════════════════════════════════

class BayesianEvolutionEngine:
    """基于贝叶斯优化的进化引擎"""
    def __init__(self, topic):
        self.topic = topic
        
        # 定义参数空间
        self.param_space = {
            'num_sources': (2, 4, 'int'),
            'depth_level': (0, 2, 'int'),
        }
        
        self.optimizer = BayesianOptimizer(self.param_space, acquisition="ei", n_warmup=2)
    
    def params_to_config(self, params):
        """将参数转换为配置"""
        depth_map = {0: "quick", 1: "standard", 2: "deep"}
        sources = ["prosearch", "hackernews"]
        if params['num_sources'] >= 3:
            sources.append("arxiv")
        if params['num_sources'] >= 4:
            sources.append("github")
        
        return {
            'sources': sources,
            'depth': depth_map[params['depth_level']],
        }
    
    def suggest_next(self):
        """建议下一个配置"""
        params = self.optimizer.suggest()
        return self.params_to_config(params)
    
    def observe(self, result):
        """记录观测结果"""
        value = result.get('total_findings', 0) + result.get('diversity_score', 0) * 10
        params = {
            'num_sources': len(result.get('sources', [])),
            'depth_level': {'quick': 0, 'standard': 1, 'deep': 2}.get(result.get('depth', 'quick'), 1),
        }
        self.optimizer.observe(params, value)
        C.info(f"贝叶斯优化: 目标函数值 = {value:.2f}")

# ════════════════════════════════════════════════════════════════
# 模拟研究函数
# ════════════════════════════════════════════════════════════════

def run_round(topic, sources, depth):
    """执行单轮研究（模拟）"""
    # 模拟：源数越多、深度越深，信息量越多
    base = 10
    base += len(sources) * 5
    base += {'quick': 0, 'standard': 5, 'deep': 10}.get(depth, 0)
    
    # 加入随机性
    findings = base + random.randint(-2, 2)
    
    return {
        'total_findings': findings,
        'sources': sources,
        'depth': depth,
        'diversity_score': 0.5 + random.random() * 0.3,
    }

# ════════════════════════════════════════════════════════════════
# 贝叶斯优化进化主循环
# ════════════════════════════════════════════════════════════════

def evolve_bayesian(topic, rounds=4):
    """贝叶斯优化进化"""
    C.banner(f"AutoResearch Bayesian Optimization | {topic}")
    print()
    
    engine = BayesianEvolutionEngine(topic)
    all_results = []
    t0 = time.time()
    
    for rn in range(1, rounds + 1):
        r_t0 = time.time()
        
        # 建议下一个配置
        config = engine.suggest_next()
        sources = config['sources']
        depth = config['depth']
        
        C.step(f"R{rn} → sources={sources}, depth={depth}")
        
        # 执行研究
        result = run_round(topic, sources, depth)
        result['round'] = rn
        
        # 记录观测
        engine.observe(result)
        all_results.append(result)
        
        took = time.time() - r_t0
        C.info(f"完成: {result['total_findings']} 条信息 ({took:.0f}s)")
        
        # 显示最优参数
        if engine.optimizer.best_params:
            C.info(f"当前最优: {engine.optimizer.best_params} (值={engine.optimizer.best_value:.2f})")
    
    elapsed = time.time() - t0
    best = max(all_results, key=lambda r: r['total_findings'], default=None)
    
    print()
    C.ok(f"贝叶斯优化完成: {len(all_results)} 轮 | 最优信息量: {best['total_findings'] if best else 0} 条 | {elapsed:.0f}s")
    
    return all_results, elapsed

# ── 主入口 ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="AutoResearch 贝叶斯优化 v3.3")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=4)
    args = p.parse_args()
    
    if not args.topic:
        print("用法: python autorun_evolve_v3.3.py <主题> [-r 轮数]")
        return
    
    results, elapsed = evolve_bayesian(args.topic, rounds=args.rounds)

if __name__ == "__main__":
    main()
