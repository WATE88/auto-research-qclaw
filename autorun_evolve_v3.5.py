#!/usr/bin/env python3
"""
AutoResearch v3.5 — 统一功能主体
融合 Karpathy 闭环 + 贝叶斯优化 + 自主探索
单一核心引擎，支持三种模式无缝切换
"""
import os, sys, io, json, time, uuid, argparse, hashlib, re, urllib.request, urllib.parse, math, random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum

# ── UTF-8 ──────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR  = SCRIPT_DIR / "_cache"
CACHE_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════════
# 枚举与配置
# ════════════════════════════════════════════════════════════════

class OptimizationMode(Enum):
    """优化模式"""
    KARPATHY = "karpathy"      # 启发式闭环
    BAYESIAN = "bayesian"      # 贝叶斯优化
    EXPLORATION = "exploration" # 自主探索

class Depth(Enum):
    """研究深度"""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"

# ════════════════════════════════════════════════════════════════
# 贝叶斯优化核心
# ════════════════════════════════════════════════════════════════

class GaussianProcess:
    """高斯过程"""
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
    def __init__(self, param_space, n_warmup=2):
        self.param_space = param_space
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
            acq = (mu - self.best_value) * sigma
            
            if acq > best_acq:
                best_acq = acq
                best_vec = vec
        
        return self._decode_params(best_vec) if best_vec else self.suggest()
    
    def observe(self, params, value):
        self.history.append({'params': params, 'value': value})
        if value > self.best_value:
            self.best_value = value
            self.best_params = params

# ════════════════════════════════════════════════════════════════
# 自主探索核心
# ════════════════════════════════════════════════════════════════

class ExplorationEngine:
    """自主探索引擎"""
    def __init__(self):
        self.visited_topics = set()
    
    def extract_topics(self, findings, limit=5):
        """从结果提取新兴话题"""
        topics = {}
        for f in findings:
            title = f.get("title", "").lower()
            words = re.findall(r'\b[a-z]{4,}\b', title)
            for w in words:
                if w not in ["http", "https", "arxiv", "github"]:
                    topics[w] = topics.get(w, 0) + 1
        
        sorted_topics = sorted(topics.items(), key=lambda x: -x[1])
        return [t[0] for t in sorted_topics[:limit]]
    
    def generate_next_topics(self, base_topic, findings, limit=3):
        """生成下一个探索主题"""
        emerging = self.extract_topics(findings, limit=5)
        base_words = set(base_topic.lower().split())
        filtered = [kw for kw in emerging if kw not in base_words]
        
        candidates = []
        for kw in filtered:
            if kw not in self.visited_topics:
                new_topic = f"{base_topic} {kw}"
                candidates.append(new_topic)
        
        return candidates[:limit]
    
    def mark_visited(self, topic):
        """标记已访问主题"""
        self.visited_topics.add(topic)

# ════════════════════════────────────────────────────────────────
# 统一进化引擎 (v3.5 核心)
# ════════════════════════════════════════════════════════════════

@dataclass
class ResearchConfig:
    """研究配置"""
    sources: list = field(default_factory=lambda: ["prosearch", "hackernews"])
    depth: Depth = Depth.QUICK
    
    def to_dict(self):
        return {
            'sources': self.sources,
            'depth': self.depth.value,
        }

@dataclass
class ResearchResult:
    """研究结果"""
    round_num: int
    config: ResearchConfig
    total_findings: int
    diversity_score: float
    value: float  # 目标函数值
    findings: list = field(default_factory=list)

class UnifiedResearchEngine:
    """统一研究引擎 (v3.5 核心)"""
    
    def __init__(self, topic, mode=OptimizationMode.KARPATHY):
        self.topic = topic
        self.mode = mode
        self.history = []
        self.best_result = None
        self.stall_count = 0
        
        # 贝叶斯优化器
        self.param_space = {
            'num_sources': (2, 4, 'int'),
            'depth_level': (0, 2, 'int'),
        }
        self.optimizer = BayesianOptimizer(self.param_space, n_warmup=2)
        
        # 自主探索引擎
        self.explorer = ExplorationEngine()
    
    def suggest_config(self, round_num=1, total_rounds=3):
        """建议研究配置"""
        if self.mode == OptimizationMode.BAYESIAN:
            return self._suggest_bayesian()
        elif self.mode == OptimizationMode.KARPATHY:
            return self._suggest_karpathy(round_num, total_rounds)
        else:
            return self._suggest_karpathy(round_num, total_rounds)
    
    def _suggest_karpathy(self, round_num, total_rounds):
        """Karpathy 启发式建议"""
        explore_phase = round_num <= max(1, total_rounds // 2)
        
        if explore_phase:
            sources = ["prosearch", "hackernews", "arxiv"]
            depth = Depth.QUICK if round_num == 1 else Depth.STANDARD
        else:
            sources = ["prosearch", "hackernews", "arxiv", "github"]
            depth = Depth.DEEP
        
        return ResearchConfig(sources=sources, depth=depth)
    
    def _suggest_bayesian(self):
        """贝叶斯优化建议"""
        params = self.optimizer.suggest()
        depth_map = {0: Depth.QUICK, 1: Depth.STANDARD, 2: Depth.DEEP}
        
        sources = ["prosearch", "hackernews"]
        if params['num_sources'] >= 3:
            sources.append("arxiv")
        if params['num_sources'] >= 4:
            sources.append("github")
        
        return ResearchConfig(sources=sources, depth=depth_map[params['depth_level']])
    
    def observe(self, result):
        """记录观测"""
        self.history.append(result)
        
        # 更新最优结果
        if self.best_result is None or result.value > self.best_result.value:
            self.best_result = result
            self.stall_count = 0
        else:
            self.stall_count += 1
        
        # 贝叶斯优化器更新
        if self.mode == OptimizationMode.BAYESIAN:
            params = {
                'num_sources': len(result.config.sources),
                'depth_level': {'quick': 0, 'standard': 1, 'deep': 2}[result.config.depth.value],
            }
            self.optimizer.observe(params, result.value)
    
    def should_stop(self, stall_threshold=2):
        """是否应该停止"""
        return self.stall_count >= stall_threshold
    
    def get_next_exploration_topic(self):
        """获取下一个探索主题"""
        if not self.best_result:
            return None
        
        findings = self.best_result.findings
        candidates = self.explorer.generate_next_topics(self.topic, findings)
        
        if candidates:
            next_topic = candidates[0]
            self.explorer.mark_visited(next_topic)
            return next_topic
        
        return None

# ── 控制台样式 ─────────────────────────────────────────────────
class Console:
    R   = "\033[0m"
    B   = "\033[1m"
    CYN = "\033[96m"
    GRN = "\033[92m"
    MAG = "\033[95m"

    @staticmethod
    def banner(msg):
        print()
        print(f"{Console.CYN}{'='*62}{Console.R}")
        print(f"{Console.B}{Console.CYN}  {msg}{Console.R}")
        print(f"{Console.CYN}{'='*62}{Console.R}")

    @staticmethod
    def step(msg):
        print(f"{Console.MAG}  >> {msg}{Console.R}")

    @staticmethod
    def info(msg):
        print(f"{Console.CYN}  [*] {msg}{Console.R}")

    @staticmethod
    def ok(msg):
        print(f"{Console.GRN}  [OK] {msg}{Console.R}")

# ════════════════════════════════════════════════════════════════
# 模拟研究函数
# ════════════════════════════════════════════════════════════════

def run_research(topic, config):
    """执行研究"""
    base = 10
    base += len(config.sources) * 5
    base += {'quick': 0, 'standard': 5, 'deep': 10}[config.depth.value]
    findings = base + random.randint(-2, 2)
    diversity = 0.5 + random.random() * 0.3
    value = findings + diversity * 10
    
    return ResearchResult(
        round_num=0,
        config=config,
        total_findings=findings,
        diversity_score=diversity,
        value=value,
        findings=[{'title': f'Result {i}'} for i in range(findings)],
    )

# ════════════════════════════════════════════════════════════════
# 主研究循环
# ════════════════════════════════════════════════════════════════

def research_loop(topic, rounds=4, mode=OptimizationMode.KARPATHY):
    """主研究循环"""
    Console.banner(f"AutoResearch v3.5 | {topic} | {mode.value}")
    print()
    
    engine = UnifiedResearchEngine(topic, mode)
    all_results = []
    t0 = time.time()
    
    for rn in range(1, rounds + 1):
        r_t0 = time.time()
        
        # 建议配置
        config = engine.suggest_config(rn, rounds)
        Console.step(f"R{rn} >> sources={config.sources}, depth={config.depth.value}")
        
        # 执行研究
        result = run_research(topic, config)
        result.round_num = rn
        
        # 记录观测
        engine.observe(result)
        all_results.append(result)
        
        took = time.time() - r_t0
        Console.info(f"Result: {result.total_findings} findings (value={result.value:.2f}) ({took:.0f}s)")
        
        # 显示最优
        if engine.best_result:
            Console.info(f"Best: {engine.best_result.total_findings} findings (value={engine.best_result.value:.2f})")
        
        # 检查停止条件
        if engine.should_stop(stall_threshold=2):
            Console.info("Stall detected, stopping")
            break
    
    elapsed = time.time() - t0
    print()
    Console.ok(f"Complete: {len(all_results)} rounds | Best: {engine.best_result.total_findings if engine.best_result else 0} findings | {elapsed:.0f}s")
    
    return all_results, engine

def exploration_loop(topic, max_iterations=3):
    """自主探索循环"""
    Console.banner(f"AutoResearch v3.5 | Autonomous Exploration | {topic}")
    print()
    
    all_results = []
    current_topic = topic
    
    for iteration in range(max_iterations):
        print(f"\n{Console.B}[Iteration {iteration + 1}/{max_iterations}] Topic: {current_topic}{Console.R}")
        
        # 执行研究
        results, engine = research_loop(current_topic, rounds=2, mode=OptimizationMode.KARPATHY)
        all_results.extend(results)
        
        if not results:
            break
        
        # 获取下一个主题
        next_topic = engine.get_next_exploration_topic()
        if not next_topic:
            Console.info("No new topics, stopping")
            break
        
        current_topic = next_topic
        Console.info(f"Next topic: {current_topic}")
    
    print()
    Console.ok(f"Exploration complete: {len(all_results)} rounds")
    return all_results

# ── 主入口 ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="AutoResearch v3.5 Unified Core")
    p.add_argument("topic", nargs="?", default="")
    p.add_argument("-r", "--rounds", type=int, default=4)
    p.add_argument("--mode", choices=["karpathy", "bayesian", "exploration"], default="karpathy")
    p.add_argument("--explore-depth", type=int, default=3)
    args = p.parse_args()
    
    if not args.topic:
        print("Usage: python autorun_evolve_v3.5.py <topic> [--mode karpathy|bayesian|exploration]")
        return
    
    mode_map = {
        "karpathy": OptimizationMode.KARPATHY,
        "bayesian": OptimizationMode.BAYESIAN,
        "exploration": OptimizationMode.EXPLORATION,
    }
    
    mode = mode_map[args.mode]
    
    if mode == OptimizationMode.EXPLORATION:
        exploration_loop(args.topic, max_iterations=args.explore_depth)
    else:
        research_loop(args.topic, rounds=args.rounds, mode=mode)

if __name__ == "__main__":
    main()
