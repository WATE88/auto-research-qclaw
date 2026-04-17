"""
AutoResearch BOHB — 多保真度贝叶斯优化 (Multi-Fidelity BO)
=============================================================
参考：Nature Comput. Sci. 2025 / Falkner et al. ICML 2018

核心思想：
  • 用"便宜的低保真度评估"（如少量训练步数/小数据集/粗采样）
    快速筛掉劣质候选，只把算力花在最有希望的候选上。
  • 保真度调度器（FidelityScheduler）：Hyperband 式 η=3 梯度淘汰
  • GP 代理模型跨保真度联合建模（增量 length_scale 偏移修正）
  • 与现有 EvolvableBayesianOptimizer 零侵入集成：
    只需把 evaluate_fn(params) → evaluate_fn(params, fidelity)

速度提升推算（η=3，4 级保真度）：
  传统 BO:  100 次全保真评估 → 100 × T_full
  BOHB:     ~33 次低保 + ~11 次中保 + ~4 次高保 + ~1 次全保
            ≈ 33×0.1T + 11×0.3T + 4×0.6T + 1×T = 10.2T
  → 约节省 90%, 相当于 10× 加速（即 +900% 速度）

用法示例：
    from autoresearch_bohb import BOHBOptimizer

    def my_eval(params: dict, fidelity: float) -> float:
        # fidelity ∈ [0,1], 1.0 = 完整评估
        n_iter = max(3, int(fidelity * 30))
        return run_bo(params, n_iter)

    opt = BOHBOptimizer(bounds, evaluate_fn=my_eval, eta=3, min_fidelity=0.1)
    best = opt.run(budget=81)   # budget = 总算力单位（折算成全保真次数）
"""

from __future__ import annotations
import math, time, json, copy, random
from typing import Callable, Dict, List, Tuple, Optional
import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
#  1. 保真度调度器（Hyperband / SH 核心）
# ──────────────────────────────────────────────────────────────────────────────

class FidelityScheduler:
    """
    Successive Halving 式保真度调度器。
    
    参数：
        min_fidelity   最低保真度（如 0.1 = 10% 算力）
        max_fidelity   最高保真度（1.0 = 全量）
        eta            每轮淘汰比例的倒数（默认 3 → 每轮保留 1/3）
    """
    def __init__(self, min_fidelity: float = 0.1,
                 max_fidelity: float = 1.0, eta: int = 3):
        self.min_f = min_fidelity
        self.max_f = max_fidelity
        self.eta   = eta
        self.n_levels = max(1, int(round(
            math.log(max_fidelity / min_fidelity) / math.log(eta)
        )))

    def fidelity_at_level(self, level: int) -> float:
        """level=0 → min_fidelity; level=n_levels → max_fidelity"""
        f = self.min_f * (self.eta ** level)
        return float(min(f, self.max_f))

    def n_configs_at_level(self, level: int, n0: int) -> int:
        """SH: 第 level 级存活的配置数"""
        return max(1, int(n0 / (self.eta ** level)))

    def build_bracket(self, n0: int) -> List[Tuple[int, float, int]]:
        """
        返回 [(level, fidelity, n_configs), ...] 的完整调度表。
        """
        bracket = []
        for lvl in range(self.n_levels + 1):
            f = self.fidelity_at_level(lvl)
            n = self.n_configs_at_level(lvl, n0)
            bracket.append((lvl, f, n))
        return bracket


# ──────────────────────────────────────────────────────────────────────────────
#  2. 多保真度 GP 代理（简单版：用 fidelity 作附加输入维度）
# ──────────────────────────────────────────────────────────────────────────────

class MultiFidelityGP:
    """
    把 (x, fidelity) 拼接作为 GP 输入，用不同 length_scale 区分各维度。
    低保真观测点自动下调权重（noise_scale 随 1-fidelity 增大）。
    """

    def __init__(self, length_scale: float = 1.0,
                 noise_level: float = 1e-4,
                 fidelity_ls: float = 0.5):
        self.ls   = length_scale
        self.f_ls = fidelity_ls   # 保真度维度的 length_scale（通常更短）
        self.noise = noise_level
        self.X_aug: List[np.ndarray] = []   # [x ‖ fidelity]
        self.Y:     List[float]      = []
        self.fids:  List[float]      = []   # 对应保真度（用于噪声加权）

    def _rbf(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """各维度独立 length_scale：前 d 维 ls，最后 1 维 f_ls"""
        d = A.shape[1] - 1
        diff_x = (A[:, None, :d] - B[None, :, :d]) / max(self.ls, 1e-3)
        diff_f = (A[:, None, d:] - B[None, :, d:]) / max(self.f_ls, 1e-3)
        return np.exp(-0.5 * (np.sum(diff_x**2, -1) + np.sum(diff_f**2, -1)))

    def add_observation(self, x: np.ndarray, fidelity: float, y: float):
        aug = np.append(x, fidelity)
        self.X_aug.append(aug)
        self.Y.append(y)
        self.fids.append(fidelity)

    def predict(self, x: np.ndarray, fidelity: float
                ) -> Tuple[float, float]:
        """返回 (mean, std)"""
        n = len(self.X_aug)
        if n < 2:
            return 0.5, 1.0
        MAX_W = 80
        if n > MAX_W:
            # 保留最近 + top 各一半
            arr_y = np.array(self.Y)
            top_idx  = set(np.argsort(arr_y)[::-1][:MAX_W//2].tolist())
            rec_idx  = set(range(max(0, n - MAX_W//2), n))
            keep = sorted(top_idx | rec_idx)
            X_buf = np.array([self.X_aug[i] for i in keep])
            Y_buf = np.array([self.Y[i]     for i in keep])
            fids_buf = [self.fids[i] for i in keep]
        else:
            X_buf = np.array(self.X_aug)
            Y_buf = np.array(self.Y)
            fids_buf = self.fids

        # 低保真观测加额外噪声（1-fidelity 越高噪声越大）
        noise_diag = np.array([
            self.noise + (1.0 - fi) * 0.1 for fi in fids_buf
        ])
        K = self._rbf(X_buf, X_buf) + np.diag(noise_diag)
        try:
            L = np.linalg.cholesky(K + 1e-6 * np.eye(len(K)))
        except np.linalg.LinAlgError:
            return float(np.mean(Y_buf)), 1.0

        x_aug = np.append(x, fidelity).reshape(1, -1)
        Ks = self._rbf(x_aug, X_buf).flatten()
        Kss = 1.0 + self.noise

        alpha = np.linalg.solve(L.T, np.linalg.solve(L, Y_buf))
        v     = np.linalg.solve(L, Ks)
        mean  = float(Ks @ alpha)
        var   = float(max(0.0, Kss - v @ v))
        return mean, math.sqrt(var) + 1e-8


# ──────────────────────────────────────────────────────────────────────────────
#  3. BOHB 主优化器
# ──────────────────────────────────────────────────────────────────────────────

class BOHBOptimizer:
    """
    BOHB：Bayesian Optimization + HyperBand

    参数
    ----
    bounds        : {param_name: (low, high)} 或 {param_name: [choices]}
    evaluate_fn   : Callable[[dict, float], float]
                    接受 (params, fidelity)，fidelity∈[0,1]
    eta           : Hyperband 淘汰倍率（默认 3）
    min_fidelity  : 最低保真度（默认 0.1）
    n_candidates  : 采集函数候选点数量
    rng_seed      : 随机种子
    verbose       : 是否打印进度
    """

    def __init__(self,
                 bounds: Dict,
                 evaluate_fn: Callable[[Dict, float], float],
                 eta: int = 3,
                 min_fidelity: float = 0.1,
                 n_candidates: int = 128,
                 rng_seed: int = 42,
                 verbose: bool = True):
        self.bounds    = bounds
        self.eval_fn   = evaluate_fn
        self.eta       = eta
        self.n_cands   = n_candidates
        self.rng       = np.random.RandomState(rng_seed)
        self.verbose   = verbose

        # 保真度调度
        self.scheduler = FidelityScheduler(
            min_fidelity=min_fidelity,
            max_fidelity=1.0,
            eta=eta
        )
        # 多保真 GP
        self.gp = MultiFidelityGP()

        # 结果记录
        self.all_results: List[Dict] = []   # {params, fidelity, score, time}
        self.best_params: Dict  = {}
        self.best_score: float  = -np.inf
        self.total_calls: int   = 0
        self.total_time:  float = 0.0

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    def _param_names(self) -> List[str]:
        return list(self.bounds.keys())

    def _is_discrete(self, key: str) -> bool:
        return isinstance(self.bounds[key], (list, tuple)) and \
               isinstance(self.bounds[key][0], str)

    def _sample_random(self) -> Dict:
        p = {}
        for k, v in self.bounds.items():
            if isinstance(v, (list, tuple)) and isinstance(v[0], str):
                p[k] = self.rng.choice(v)
            else:
                lo, hi = v
                p[k] = float(self.rng.uniform(lo, hi))
        return p

    def _params_to_vec(self, params: Dict) -> np.ndarray:
        vec = []
        for k, v in self.bounds.items():
            if isinstance(v, (list, tuple)) and isinstance(v[0], str):
                choices = list(v)
                vec.append(choices.index(params[k]) / max(1, len(choices) - 1))
            else:
                lo, hi = float(v[0]), float(v[1])
                vec.append((params[k] - lo) / max(hi - lo, 1e-8))
        return np.array(vec, dtype=float)

    def _vec_to_params(self, vec: np.ndarray) -> Dict:
        p = {}
        for i, (k, v) in enumerate(self.bounds.items()):
            if isinstance(v, (list, tuple)) and isinstance(v[0], str):
                choices = list(v)
                idx = int(round(vec[i] * (len(choices) - 1)))
                p[k] = choices[max(0, min(idx, len(choices)-1))]
            else:
                lo, hi = float(v[0]), float(v[1])
                p[k] = float(np.clip(vec[i] * (hi - lo) + lo, lo, hi))
        return p

    def _acquire_ei(self, fidelity: float, xi: float = 0.01) -> Dict:
        """Expected Improvement 采集（在给定 fidelity 下）"""
        if len(self.gp.Y) < 3:
            return self._sample_random()

        best_y = self.best_score if self.best_score > -np.inf else 0.0
        best_cand, best_ei = None, -np.inf

        for _ in range(self.n_cands):
            cand_vec = self.rng.uniform(0, 1, len(self.bounds))
            mu, sigma = self.gp.predict(cand_vec, fidelity)
            z = (mu - best_y - xi) / (sigma + 1e-9)
            ei = (mu - best_y - xi) * 0.5 * (1 + math.erf(z / math.sqrt(2))) \
                 + sigma * math.exp(-0.5 * z**2) / math.sqrt(2 * math.pi)
            if ei > best_ei:
                best_ei  = ei
                best_cand = cand_vec

        return self._vec_to_params(best_cand) if best_cand is not None \
               else self._sample_random()

    def _evaluate(self, params: Dict, fidelity: float) -> float:
        t0 = time.time()
        try:
            score = float(self.eval_fn(params, fidelity))
        except Exception:
            score = -np.inf
        elapsed = time.time() - t0
        self.total_calls += 1
        self.total_time  += elapsed

        # 更新 GP
        vec = self._params_to_vec(params)
        self.gp.add_observation(vec, fidelity, score)

        # 记录结果
        entry = {"params": copy.deepcopy(params), "fidelity": fidelity,
                 "score": score, "time": elapsed}
        self.all_results.append(entry)

        # 只有全保真（或接近全保真）才更新 best
        if fidelity >= 0.9 and score > self.best_score:
            self.best_score  = score
            self.best_params = copy.deepcopy(params)

        if self.verbose:
            fid_bar = "▓" * int(fidelity * 10) + "░" * (10 - int(fidelity * 10))
            print(f"  [BOHB] fidelity={fidelity:.2f} [{fid_bar}] "
                  f"score={score:.4f}  best={self.best_score:.4f}", flush=True)
        return score

    # ── 主入口：单 SH Bracket ─────────────────────────────────────────────────

    def run_bracket(self, n0: int = 9) -> Dict:
        """
        运行一个 Successive Halving bracket。
        n0: 初始配置数量（推荐 eta^n_levels，如 eta=3,levels=2 → n0=9）
        返回本次 bracket 的最优 {params, score}
        """
        bracket = self.scheduler.build_bracket(n0)
        # 初始配置：用 BO 采集（冷启动时随机）
        configs = [self._acquire_ei(bracket[0][1]) if len(self.gp.Y) >= 5
                   else self._sample_random()
                   for _ in range(bracket[0][2])]

        survivors = configs
        for level, fidelity, n_keep in bracket:
            if self.verbose:
                print(f"\n  [BOHB] Bracket Level {level}  "
                      f"fidelity={fidelity:.2f}  "
                      f"configs={len(survivors)} → keep={n_keep}", flush=True)
            scored = []
            for cfg in survivors:
                sc = self._evaluate(cfg, fidelity)
                scored.append((sc, cfg))
            # 保留 top-n_keep
            scored.sort(key=lambda x: x[0], reverse=True)
            survivors = [cfg for _, cfg in scored[:n_keep]]

        # 用全保真验证最终幸存者
        final_best_score = -np.inf
        final_best_params = {}
        for cfg in survivors:
            sc = self._evaluate(cfg, 1.0)
            if sc > final_best_score:
                final_best_score  = sc
                final_best_params = cfg

        return {"params": final_best_params, "score": final_best_score}

    def run(self, budget: int = 81, n_brackets: int = None) -> Dict:
        """
        运行完整 BOHB（多个 SH bracket，直到用完 budget）。

        budget : 折算成"全保真等价评估次数"的总算力
        返回最优 {params, score, speedup_est, total_calls, total_time}
        """
        # 估算每个 bracket 的 n0
        # budget ≈ n_levels * n0 * 平均保真度 → n0 ≈ budget / n_levels
        n_lvls = self.scheduler.n_levels + 1
        n0 = max(self.eta, int(self.eta ** max(1, n_lvls - 1)))
        n_brackets = n_brackets or max(1, budget // n0)

        t_wall_start = time.time()
        for b_idx in range(n_brackets):
            if self.verbose:
                print(f"\n{'='*55}", flush=True)
                print(f"  [BOHB] Bracket {b_idx+1}/{n_brackets}  "
                      f"n0={n0}  budget_used≈{self.total_calls}", flush=True)
            self.run_bracket(n0)

        wall = time.time() - t_wall_start
        # 理论加速比：相比 naive BO（全保真 n_brackets*n0 次）
        naive_calls = n_brackets * n0
        speedup_est = naive_calls / max(self.total_calls, 1)

        return {
            "best_params": self.best_params,
            "best_score":  self.best_score,
            "total_calls": self.total_calls,
            "total_time":  round(wall, 2),
            "speedup_est": round(speedup_est, 2),
            "all_results": self.all_results,
        }


# ──────────────────────────────────────────────────────────────────────────────
#  4. 与现有 SelfEvolveController 的适配层
# ──────────────────────────────────────────────────────────────────────────────

class BOHBEvolveAdapter:
    """
    把 BOHBOptimizer 包装成 SelfEvolveController 兼容的接口。
    
    进化引擎调用 evaluate_genome(genome) 时，自动决定：
      - 低保真: 少量 BO 迭代（快速估分）
      - 高保真: 完整 BO 优化（精确得分）
    """

    def __init__(self, base_evaluator, fidelity_scale: int = 10):
        """
        base_evaluator : CandidateEvaluator 实例
        fidelity_scale : 高保真迭代次数 = fidelity_scale * fidelity
                         （如 scale=20，fidelity=0.5 → 10 次迭代）
        """
        self.base_eval    = base_evaluator
        self.fid_scale    = fidelity_scale
        self._call_count  = 0
        self._saved_budget = {}   # genome_hash → full_score（缓存全保真结果）

    def evaluate(self, genome: dict, fidelity: float = 1.0) -> float:
        """
        可接受 fidelity 参数的评估函数。
        低保真 → 减少迭代次数近似评估；高保真 → 完整评估。
        """
        import hashlib, json
        g_hash = hashlib.md5(json.dumps(genome, sort_keys=True).encode()).hexdigest()[:8]
        
        # 命中全保真缓存直接返回
        if fidelity >= 0.9 and g_hash in self._saved_budget:
            return self._saved_budget[g_hash]

        # 动态调整评估强度
        n_trials = max(3, int(self.fid_scale * fidelity))
        try:
            score = self.base_eval.evaluate(genome, n_trials=n_trials)
        except TypeError:
            # 不支持 n_trials 参数的老接口
            score = self.base_eval.evaluate(genome)

        self._call_count += 1
        if fidelity >= 0.9:
            self._saved_budget[g_hash] = score
        return score

    def build_bohb_for_genome_space(
            self,
            genome_bounds: dict,
            budget: int = 27,
            eta: int = 3,
            min_fidelity: float = 0.1,
            verbose: bool = False,
    ) -> BOHBOptimizer:
        """
        构造一个针对 genome 搜索空间的 BOHBOptimizer。
        """
        def _eval_fn(params: dict, fidelity: float) -> float:
            return self.evaluate(params, fidelity)

        return BOHBOptimizer(
            bounds=genome_bounds,
            evaluate_fn=_eval_fn,
            eta=eta,
            min_fidelity=min_fidelity,
            n_candidates=64,
            verbose=verbose,
        )


# ──────────────────────────────────────────────────────────────────────────────
#  5. 快速基准测试（可直接运行）
# ──────────────────────────────────────────────────────────────────────────────

def _demo_eval(params: dict, fidelity: float) -> float:
    """模拟评估：Branin 函数（经典 BO 基准）"""
    x1 = params.get("x1", 0.0)
    x2 = params.get("x2", 0.0)
    a, b = 1.0, 5.1 / (4 * math.pi**2)
    c = 5 / math.pi
    r, s, t = 6.0, 10.0, 1 / (8 * math.pi)
    # 加噪声模拟低保真
    noise = (1.0 - fidelity) * 2.0
    val = a*(x2 - b*x1**2 + c*x1 - r)**2 + s*(1-t)*math.cos(x1) + s
    return -val + np.random.normal(0, noise)  # 转最大化


def benchmark_bohb_vs_random(n_random: int = 30, budget: int = 27):
    """对比 BOHB vs 随机搜索的效果"""
    bounds = {"x1": (-5.0, 10.0), "x2": (0.0, 15.0)}
    rng    = np.random.RandomState(0)

    # 随机搜索基线
    t0 = time.time()
    best_rand = -np.inf
    for _ in range(n_random):
        p = {k: float(rng.uniform(v[0], v[1])) for k, v in bounds.items()}
        sc = _demo_eval(p, 1.0)
        if sc > best_rand:
            best_rand = sc
    t_rand = time.time() - t0

    # BOHB
    t0 = time.time()
    opt = BOHBOptimizer(bounds, _demo_eval, eta=3,
                        min_fidelity=0.1, verbose=False)
    res = opt.run(budget=budget)
    t_bohb = time.time() - t0

    print(f"\n{'='*55}")
    print(f"  随机搜索:  best={best_rand:.4f}  calls={n_random}  "
          f"time={t_rand:.2f}s")
    print(f"  BOHB:      best={res['best_score']:.4f}  "
          f"calls={res['total_calls']}  time={t_bohb:.2f}s")
    print(f"  BOHB 加速比（vs同等calls）: "
          f"speedup_est={res['speedup_est']:.1f}x")
    print(f"{'='*55}\n")
    return {
        "random_best":  best_rand,
        "bohb_best":    res["best_score"],
        "random_calls": n_random,
        "bohb_calls":   res["total_calls"],
        "random_time":  round(t_rand, 3),
        "bohb_time":    round(t_bohb, 3),
        "speedup_est":  res["speedup_est"],
    }


if __name__ == "__main__":
    benchmark_bohb_vs_random()
