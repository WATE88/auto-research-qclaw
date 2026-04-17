"""
AutoResearch 自主进化引擎 v1.0
================================
核心理念：让系统自动分析自身的每个组件，生成改进方案，
         验证改进效果，持久化最优版本，永无止境地自我提升。

进化循环：
  1. [分析] 审查当前算法性能和代码质量
  2. [诊断] 识别瓶颈：收敛速度 / 探索-利用平衡 / 参数范围
  3. [构思] 生成多个改进方案（突变策略池）
  4. [实验] 并行运行改进方案，与基线对比
  5. [选择] 择优保留，淘汰劣势
  6. [应用] 更新活跃算法配置
  7. [记录] 写入进化日志 + 数据库
  8. [循环] 回到步骤1，永不停止
"""

import os, sys, time, json, math, random, sqlite3, threading, traceback, copy, hashlib
from datetime import datetime
from pathlib import Path
import numpy as np

# ── 可选：通知推送（懒加载，失败不影响主流程）─────────────────────────────
def _get_notifier():
    try:
        from autoresearch_notify import get_notifier
        return get_notifier()
    except Exception:
        return None

# ── 路径配置 ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "evolution_monitor.db"

# ── 数据库初始化 ─────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA journal_mode=WAL")  # ✅ WAL 模式：防并发锁
    con.executescript("""
    CREATE TABLE IF NOT EXISTS generations (
        gen_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        generation  INTEGER,
        timestamp   TEXT,
        status      TEXT,          -- running / evaluating / done
        winner_id   TEXT,
        best_score  REAL,
        improvement REAL,
        log         TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS candidates (
        cand_id     TEXT PRIMARY KEY,
        generation  INTEGER,
        strategy_name TEXT,
        config      TEXT,           -- JSON: 算法配置
        score       REAL DEFAULT 0,
        trials      INTEGER DEFAULT 0,
        is_winner   INTEGER DEFAULT 0,
        created_at  TEXT,
        evaluated_at TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS evolution_metrics (
        ts          TEXT,
        generation  INTEGER,
        best_score  REAL,
        avg_score   REAL,
        diversity   REAL,           -- 种群多样性
        improvement REAL,
        cpu         REAL,
        mem         REAL
    );

    CREATE TABLE IF NOT EXISTS evolution_log (
        ts      TEXT,
        level   TEXT,
        msg     TEXT
    );

    CREATE TABLE IF NOT EXISTS algorithm_versions (
        version_id  TEXT PRIMARY KEY,
        generation  INTEGER,
        config      TEXT,           -- JSON: 完整算法配置快照
        score       REAL,
        active      INTEGER DEFAULT 0,
        created_at  TEXT
    );

    CREATE TABLE IF NOT EXISTS strategy_weights (
        strategy_name TEXT PRIMARY KEY,
        cumulative_score REAL DEFAULT 0.0,
        occurrence_count INTEGER DEFAULT 1,
        updated_at  TEXT
    );
    """)
    con.commit()
    con.close()


def db_log(level: str, msg: str):
    con = sqlite3.connect(str(DB_PATH))
    con.execute("INSERT INTO evolution_log VALUES(?,?,?)",
                (datetime.now().isoformat(), level, msg))
    con.commit(); con.close()


def db_upsert_generation(gen: dict):
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""
        INSERT INTO generations(generation,timestamp,status,winner_id,best_score,improvement,log)
        VALUES(:generation,:timestamp,:status,:winner_id,:best_score,:improvement,:log)
        ON CONFLICT(gen_id) DO NOTHING
    """, gen)
    con.commit(); con.close()
    # 按 generation 更新
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""
        UPDATE generations SET status=:status, winner_id=:winner_id,
            best_score=:best_score, improvement=:improvement, log=:log
        WHERE generation=:generation
    """, gen)
    con.commit(); con.close()


def db_upsert_candidate(cand: dict):
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""
        INSERT INTO candidates(cand_id,generation,strategy_name,config,score,trials,is_winner,created_at,evaluated_at)
        VALUES(:cand_id,:generation,:strategy_name,:config,:score,:trials,:is_winner,:created_at,:evaluated_at)
        ON CONFLICT(cand_id) DO UPDATE SET
            score=excluded.score, trials=excluded.trials,
            is_winner=excluded.is_winner, evaluated_at=excluded.evaluated_at
    """, cand)
    con.commit(); con.close()


def db_add_metric(generation, best_score, avg_score, diversity, improvement, cpu, mem):
    con = sqlite3.connect(str(DB_PATH))
    con.execute("INSERT INTO evolution_metrics VALUES(?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(), generation, best_score, avg_score,
                 diversity, improvement, cpu, mem))
    con.commit(); con.close()


def db_save_version(version_id, generation, config, score, active=0):
    con = sqlite3.connect(str(DB_PATH))
    con.execute("UPDATE algorithm_versions SET active=0")  # 清除旧 active
    con.execute("""
        INSERT INTO algorithm_versions(version_id,generation,config,score,active,created_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(version_id) DO UPDATE SET score=excluded.score, active=excluded.active
    """, (version_id, generation, json.dumps(config), score, active,
          datetime.now().isoformat()))
    con.commit(); con.close()


def db_save_strategy_weights(scores: dict, counts: dict):
    """把策略权重持久化到 SQLite，下次重启可以恢复。"""
    now = datetime.now().isoformat()
    con = sqlite3.connect(str(DB_PATH))
    for strat, sc in scores.items():
        cnt = counts.get(strat, 1)
        con.execute("""
            INSERT INTO strategy_weights(strategy_name, cumulative_score, occurrence_count, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(strategy_name) DO UPDATE SET
                cumulative_score=excluded.cumulative_score,
                occurrence_count=excluded.occurrence_count,
                updated_at=excluded.updated_at
        """, (strat, sc, cnt, now))
    con.commit(); con.close()


def db_load_strategy_weights() -> tuple:
    """
    从 SQLite 恢复策略权重。
    返回 (scores_dict, counts_dict)，表不存在或为空时返回 ({}, {})。
    """
    if not DB_PATH.exists():
        return {}, {}
    try:
        con = sqlite3.connect(str(DB_PATH))
        rows = con.execute(
            "SELECT strategy_name, cumulative_score, occurrence_count FROM strategy_weights"
        ).fetchall()
        con.close()
        scores = {r[0]: r[1] for r in rows}
        counts = {r[0]: r[2] for r in rows}
        return scores, counts
    except Exception:
        return {}, {}


# ── 可进化的贝叶斯优化器 ────────────────────────────────────────────────────

class EvolvableBayesianOptimizer:
    """
    可进化贝叶斯优化器。
    所有算法超参数（采集策略、GP 核参数、探索-利用系数）都被暴露为
    可改进的"基因"，自主进化引擎通过修改这些基因来提升优化器性能。
    """

    DEFAULT_GENOME = {
        # 采集函数
        "acquisition": "EI",        # EI / UCB / PI / Thompson
        "ei_xi":        0.01,       # EI 探索奖励
        "ucb_kappa":    2.576,      # UCB 置信区间宽度
        # GP 核参数
        "length_scale": 1.0,        # RBF 核长度尺度
        "noise_level":  1e-6,       # 观测噪声
        # 探索策略
        "n_random_init": 5,         # 随机初始化轮数
        "n_candidates":  256,       # 采集候选点数量
        # 归一化
        "normalize_y": True,        # 是否归一化目标值
    }

    def __init__(self, bounds: dict, genome: dict = None, rng_seed: int = 42):
        self.bounds = bounds
        self.genome = {**self.DEFAULT_GENOME, **(genome or {})}
        self.rng = np.random.RandomState(rng_seed)
        self.X:   list = []
        self.Y:   list = []
        self.Y_raw: list = []
        self.best_score = -np.inf
        self.best_params: dict = {}

    def _rbf(self, X1, X2):
        ls = max(self.genome["length_scale"], 1e-3)
        diff = X1[:, None, :] - X2[None, :, :]
        return np.exp(-0.5 * np.sum(diff**2, axis=-1) / ls**2)

    def _gp(self, x_new: np.ndarray):
        if len(self.X) < 2:
            return 0.5, 1.0
        # ── GP 滑动窗口（防止后期矩阵运算 O(N³) 爆炸）────────────────────────
        # 优先级：保留 top-K 最优点 + 最近 recent 个点，合集不超过 GP_WINDOW
        GP_WINDOW = 60      # 最大样本数（60×60 矩阵 ~0.3ms，200×200 ~15ms）
        RECENT    = 20      # 必须保留的最近样本数（保证局部精度）
        TOP_K     = 20      # 必须保留的历史最优样本数（保证全局最优记忆）
        n = len(self.X)
        if n > GP_WINDOW:
            Y_arr = np.array(self.Y)
            # top-K 最优索引
            top_idx  = set(np.argsort(Y_arr)[::-1][:TOP_K].tolist())
            # 最近 recent 索引
            recent_idx = set(range(max(0, n - RECENT), n))
            keep_idx   = sorted(top_idx | recent_idx)
            # 如果 keep 不足 GP_WINDOW，从中间补充（均匀采样历史）
            if len(keep_idx) < GP_WINDOW:
                remaining = [i for i in range(n) if i not in set(keep_idx)]
                step = max(1, len(remaining) // (GP_WINDOW - len(keep_idx)))
                extra = remaining[::step][: GP_WINDOW - len(keep_idx)]
                keep_idx = sorted(set(keep_idx) | set(extra))
            keep_idx = keep_idx[:GP_WINDOW]
            X = np.array(self.X)[keep_idx]
            Y = np.array(self.Y)[keep_idx]
        else:
            X = np.array(self.X)
            Y = np.array(self.Y)
        # ── 标准 GP 推断 ──────────────────────────────────────────────────────
        noise = max(self.genome["noise_level"], 1e-9)
        K    = self._rbf(X, X) + noise * np.eye(len(X))
        Ks   = self._rbf(x_new[None], X)[0]
        Kss  = 1.0 + noise
        try:
            L = np.linalg.cholesky(K)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, Y))
            mu = float(Ks @ alpha)
            v  = np.linalg.solve(L, Ks)
            var = max(float(Kss - v @ v), 1e-9)
        except np.linalg.LinAlgError:
            mu, var = float(np.mean(Y)), 1.0
        return mu, var

    def _acq(self, x_new: np.ndarray) -> float:
        mu, var = self._gp(x_new)
        sigma   = math.sqrt(var)
        best    = self.best_score if self.best_score > -np.inf else 0.0

        acq = self.genome["acquisition"]
        if acq == "UCB":
            return mu + self.genome["ucb_kappa"] * sigma
        elif acq == "PI":
            if sigma < 1e-9: return 0.0
            z = (mu - best) / sigma
            return 0.5 * (1 + math.erf(z / math.sqrt(2)))
        elif acq == "Thompson":
            return float(self.rng.normal(mu, sigma))
        else:  # EI
            if sigma < 1e-9: return 0.0
            xi = self.genome["ei_xi"]
            z  = (mu - best - xi) / sigma
            phi = math.exp(-0.5 * z**2) / math.sqrt(2 * math.pi)
            Phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))
            return (mu - best - xi) * Phi + sigma * phi

    def _normalize(self, x_raw: np.ndarray) -> np.ndarray:
        lo = np.array([v[0] for v in self.bounds.values()])
        hi = np.array([v[1] for v in self.bounds.values()])
        return (x_raw - lo) / (hi - lo + 1e-12)

    def suggest(self) -> dict:
        keys = list(self.bounds.keys())
        lo   = np.array([v[0] for v in self.bounds.values()])
        hi   = np.array([v[1] for v in self.bounds.values()])
        n_init = max(3, int(self.genome["n_random_init"]))
        n_cand = max(64, int(self.genome["n_candidates"]))

        if len(self.X) < n_init:
            x_raw = lo + self.rng.rand(len(keys)) * (hi - lo)
        else:
            cands  = lo + self.rng.rand(n_cand, len(keys)) * (hi - lo)
            scores = [self._acq(self._normalize(c)) for c in cands]
            x_raw  = cands[np.argmax(scores)]
        return {k: float(v) for k, v in zip(keys, x_raw)}

    def register(self, params: dict, score: float):
        keys  = list(self.bounds.keys())
        x_raw = np.array([params[k] for k in keys])
        self.X.append(self._normalize(x_raw).tolist())
        self.Y_raw.append(score)
        # 可选 Y 归一化
        if self.genome["normalize_y"] and len(self.Y_raw) > 1:
            arr = np.array(self.Y_raw)
            std = arr.std() + 1e-9
            self.Y = ((arr - arr.mean()) / std).tolist()
        else:
            self.Y = self.Y_raw.copy()
        if score > self.best_score:
            self.best_score = score
            self.best_params = params.copy()


# ── 目标函数（更真实的基准，带维度诅咒） ───────────────────────────────────

def branin(x1, x2):
    """Branin-Hoo 函数，全局最小在 ~0.397"""
    a=1; b=5.1/(4*math.pi**2); c=5/math.pi; r=6; s=10; t=1/(8*math.pi)
    val = a*(x2 - b*x1**2 + c*x1 - r)**2 + s*(1-t)*math.cos(x1) + s
    return 1.0 / (1.0 + val / 100)  # 转为最大化，范围约 [0,1]

def hartmann6(x):
    """Hartmann-6D 函数，标准 BO 基准"""
    alpha = [1.0, 1.2, 3.0, 3.2]
    A = [[10,3,17,3.5,1.7,8],[0.05,10,17,0.1,8,14],
         [3,3.5,1.7,10,17,8],[17,8,0.05,10,0.1,14]]
    P = [[1312,1696,5569,124,8283,5886],[2329,4135,8307,3736,1004,9991],
         [2348,1451,3522,2883,3047,6650],[4047,8828,8732,5743,1091,381]]
    outer = 0.0
    for i in range(4):
        inner = sum(A[i][j]*(x[j]-P[i][j]/1e4)**2 for j in range(6))
        outer += alpha[i] * math.exp(-inner)
    return outer / 3.32237  # 归一化到 [0,1]

def ackley_inv(params):
    """Ackley 函数的倒数（转最大化），用于测试多峰场景"""
    x = np.array(list(params.values()))
    n = len(x)
    val = (-20 * math.exp(-0.2 * math.sqrt(np.sum(x**2)/n))
           - math.exp(np.sum(np.cos(2*math.pi*x))/n)
           + 20 + math.e)
    return 1.0 / (1.0 + val / 20)

BENCHMARKS = {
    "Branin2D": {
        "bounds": {"x1": (-5.0, 10.0), "x2": (0.0, 15.0)},
        "fn": lambda p: branin(p["x1"], p["x2"]),
        "optimal": 0.980,
    },
    "Hartmann6D": {
        "bounds": {f"x{i}": (0.0, 1.0) for i in range(6)},
        "fn": lambda p: hartmann6([p[f"x{i}"] for i in range(6)]),
        "optimal": 1.0,
    },
    "Ackley5D": {
        "bounds": {f"x{i}": (-2.0, 2.0) for i in range(5)},
        "fn": lambda p: ackley_inv(p),
        "optimal": 1.0,
    },
}


# ── 基因组突变策略 ──────────────────────────────────────────────────────────

class MutationEngine:
    """
    基因突变引擎。
    定义了所有可以对算法基因组施加的突变操作。
    每个突变策略都针对不同的改进假设。
    """

    STRATEGIES = {
        "switch_to_ucb":     "将采集函数切换为 UCB（更激进探索）",
        "switch_to_ei":      "将采集函数切换为 EI（期望改进）",
        "switch_to_thompson":"将采集函数切换为 Thompson 采样",
        "increase_kappa":    "增大 UCB 置信区间（更多探索）",
        "decrease_kappa":    "减小 UCB 置信区间（更多利用）",
        "increase_xi":       "增大 EI 探索奖励",
        "decrease_xi":       "减小 EI 探索奖励",
        "tune_length_scale": "自适应调整 GP 核长度尺度",
        "more_candidates":   "增加采集候选点（更精细搜索）",
        "fewer_random_init": "减少随机初始化（更快进入贝叶斯阶段）",
        "enable_normalize":  "开启目标值归一化",
        "disable_normalize": "关闭目标值归一化",
        "random_mutate":     "随机扰动多个基因参数",
    }

    @staticmethod
    def mutate(genome: dict, strategy: str, rng: np.random.RandomState) -> dict:
        g = copy.deepcopy(genome)
        if strategy == "switch_to_ucb":
            g["acquisition"] = "UCB"
        elif strategy == "switch_to_ei":
            g["acquisition"] = "EI"
        elif strategy == "switch_to_thompson":
            g["acquisition"] = "Thompson"
        elif strategy == "increase_kappa":
            g["ucb_kappa"] = min(g["ucb_kappa"] * (1 + rng.uniform(0.1, 0.5)), 10.0)
        elif strategy == "decrease_kappa":
            g["ucb_kappa"] = max(g["ucb_kappa"] * (1 - rng.uniform(0.1, 0.4)), 0.5)
        elif strategy == "increase_xi":
            g["ei_xi"] = min(g["ei_xi"] * (1 + rng.uniform(0.2, 1.0)), 0.1)
        elif strategy == "decrease_xi":
            g["ei_xi"] = max(g["ei_xi"] * (1 - rng.uniform(0.1, 0.5)), 1e-5)
        elif strategy == "tune_length_scale":
            g["length_scale"] = float(rng.uniform(0.3, 3.0))
        elif strategy == "more_candidates":
            g["n_candidates"] = min(int(g["n_candidates"] * rng.uniform(1.5, 3.0)), 1024)
        elif strategy == "fewer_random_init":
            g["n_random_init"] = max(int(g["n_random_init"] - 1), 2)
        elif strategy == "enable_normalize":
            g["normalize_y"] = True
        elif strategy == "disable_normalize":
            g["normalize_y"] = False
        elif strategy == "random_mutate":
            # ── 方案A 增大变异率（2026-03-25 平台期突破模式）────────────────
            # 扰动幅度提升约3倍，搜索上界放宽，强制跳出局部最优
            g["ucb_kappa"]    = float(np.clip(rng.normal(g["ucb_kappa"],    1.5),  0.3, 12.0))
            g["ei_xi"]        = float(np.clip(rng.normal(g["ei_xi"],        0.02), 1e-5, 0.2))
            g["length_scale"] = float(np.clip(rng.normal(g["length_scale"], 1.0),  0.05, 8.0))
            g["n_candidates"] = int(np.clip(rng.normal(g["n_candidates"],   200),  32, 1500))
            g["n_random_init"]= int(np.clip(rng.choice([2, 4, 6, 8, 12]),    2, 15))
            g["normalize_y"]  = bool(rng.choice([True, False]))
            # 随机切换采集函数（增加多样性）
            g["acquisition"]  = str(rng.choice(["EI", "UCB", "PI", "Thompson"]))
        return g


# ── 候选方案评估器 ─────────────────────────────────────────────────────────

class CandidateEvaluator:
    """
    对一个算法基因组在所有基准上运行 N 次，返回平均性能得分。

    支持「粗筛 / 精筛」两档：
      粗筛（coarse）: n_trials_coarse × steps_coarse  —— 快速淘汰劣质候选
      精筛（fine）  : n_trials_fine   × steps_fine    —— 对 top-K 精确评估
    """

    # ── 粗筛参数（快速、低开销）
    COARSE_TRIALS = 4    # 每基准跑 4 次
    COARSE_STEPS  = 12   # 每次 12 步 BO

    # ── 精筛参数（高置信）
    FINE_TRIALS   = 12   # 每基准跑 12 次
    FINE_STEPS    = 20   # 每次 20 步 BO

    WEIGHTS = {"Branin2D": 0.3, "Hartmann6D": 0.4, "Ackley5D": 0.3}

    def __init__(self, n_trials: int = None, rng_seed: int = None):
        # n_trials 保留仅兼容旧调用（基线评估用），不影响 coarse/fine 路径
        self.n_trials = n_trials or self.FINE_TRIALS
        self.rng_seed = rng_seed or random.randint(0, 999999)

    def _run_single(self, genome: dict, benchmark_name: str,
                    n_trials: int, n_steps: int) -> float:
        """对单个基准跑 n_trials × n_steps，返回均值得分"""
        bench = BENCHMARKS[benchmark_name]
        bounds, fn = bench["bounds"], bench["fn"]
        scores = []
        for trial in range(n_trials):
            opt = EvolvableBayesianOptimizer(
                bounds, genome=genome,
                rng_seed=self.rng_seed + trial * 17
            )
            for _ in range(n_steps):
                try:
                    p = opt.suggest()
                    s = fn(p) + np.random.normal(0, 0.005)
                    opt.register(p, s)
                except Exception:
                    pass
            scores.append(opt.best_score if opt.best_score > -np.inf else 0.0)
        return float(np.mean(scores)) if scores else 0.0

    def evaluate_coarse(self, genome: dict) -> float:
        """粗筛：低开销快速评估（用于批量候选初筛）"""
        total = 0.0
        for bname, w in self.WEIGHTS.items():
            total += self._run_single(genome, bname, self.COARSE_TRIALS, self.COARSE_STEPS) * w
        return total

    def evaluate_fine(self, genome: dict) -> float:
        """精筛：高置信精确评估（用于 top-K 候选的最终定档）"""
        total = 0.0
        for bname, w in self.WEIGHTS.items():
            total += self._run_single(genome, bname, self.FINE_TRIALS, self.FINE_STEPS) * w
        return total

    def evaluate_all(self, genome: dict) -> float:
        """兼容旧接口（基线评估、外部调用），等同于精筛"""
        return self.evaluate_fine(genome)


# ── 自主进化控制器 ─────────────────────────────────────────────────────────

class SelfEvolveController:
    """
    无限循环的自主进化控制器 v1.1（增强版）
    每一代：
      - 自适应种群大小（根据近期提升率动态调整）
      - 精英交叉繁殖（混合多个精英基因组）
      - 停滞检测（连续N代无提升时重置探索）
      - 并行评估所有候选
      - 选出最优基因组 → 更新当前代
      - 永不停止
    """

    POPULATION_SIZE  = 6    # 初始每代候选方案数
    ELITE_RATIO      = 0.33  # 保留 top 1/3 精英
    TOP_K_FINE       = 2    # 粗筛后精筛的候选数量

    # 方案A（2026-03-25）：平台期突破模式 - 更激进的探索参数
    STAGNATION_LIMIT = 3    # 连续N代无提升则触发重置（原5→3，更快重置）
    MAX_POPULATION   = 14   # 最大种群上限（原10→14，允许更大探索批次）
    MIN_POPULATION   = 4    # 最小种群下限

    def __init__(self):
        self.generation   = 0
        self.current_genome = copy.deepcopy(EvolvableBayesianOptimizer.DEFAULT_GENOME)
        self.best_genome    = copy.deepcopy(self.current_genome)
        self.best_score     = 0.0
        self.history        = []   # [(gen, score, genome)]
        self.rng            = np.random.RandomState(42)
        self.stop_event     = threading.Event()
        self.logs           = []
        self.evaluator      = CandidateEvaluator()
        self._lock          = threading.Lock()

        # ── 改进9：通知推送（懒加载）─────────────────────────────────────────
        self._notifier = _get_notifier()

        # ── 改进4：并行评估器（KB策略）──────────────────────────────────────
        try:
            from autoresearch_parallel import ParallelCandidatePool
            self._parallel_pool = ParallelCandidatePool(n_workers=3)
        except Exception:
            self._parallel_pool = None

        # ── 改进1：BOHB 多保真度优化器（懒加载）────────────────────────────
        try:
            from autoresearch_bohb import BOHBEvolveAdapter
            self._bohb_adapter = BOHBEvolveAdapter(
                base_evaluator=self.evaluator, fidelity_scale=10)
        except Exception:
            self._bohb_adapter = None

        # ── 改进2：LLM 暖启动（懒加载）────────────────────────────────────
        try:
            from autoresearch_llm_warmstart import WarmStartEvolveMixin
            WarmStartEvolveMixin.setup(self)
        except Exception:
            self._warm_starter = None

        # ── 改进3：PBT-ASHA 早停适配（懒加载）─────────────────────────────
        try:
            from autoresearch_pbt_asha import PBTASHAEvolveAdapter
            self._pbt_asha = PBTASHAEvolveAdapter(
                base_evaluator=self.evaluator,
                population_size=min(6, self.POPULATION_SIZE),
                eta=3, min_resource=2.0, max_resource=15.0,
            )
        except Exception:
            self._pbt_asha = None

        # ── 漂移检测 + 自动重优化（懒加载）──────────────────────────────
        try:
            from autoresearch_drift import DriftEvolveAdapter
            self._drift_adapter = DriftEvolveAdapter(self, cooldown_s=300)
        except Exception:
            self._drift_adapter = None

        # ── 实验版本管理（懒加载）────────────────────────────────────────
        try:
            from autoresearch_version import get_store, get_version_manager
            self._exp_store = get_store()
            self._version_mgr = get_version_manager()
        except Exception:
            self._exp_store   = None
            self._version_mgr = None

        # ── 超参数重要性分析（懒加载）────────────────────────────────────
        try:
            from autoresearch_importance import ImportanceEvolveAdapter
            self._importance_adapter = ImportanceEvolveAdapter(self)
        except Exception:
            self._importance_adapter = None

        # ── 搜索 & 学习总结技能（InsightEngine）──────────────────────────
        try:
            from autoresearch_insight import attach_insight_engine
            attach_insight_engine(self)
            if self._insight_engine:
                self.log("[InsightEngine] 搜索学习总结技能已挂载 ✅", "INFO")
        except Exception as _ie_err:
            self._insight_engine = None
            self.log(f"[InsightEngine] 挂载失败（不影响主流程）: {_ie_err}", "WARN")

        # ── 综合增强模块（EnhancementHub）────────────────────────────────
        try:
            from autoresearch_enhancements import attach_enhancements
            self._enhancement_hub = attach_enhancements(
                self, insight=getattr(self, "_insight_engine", None)
            )
            self.log("[EnhancementHub] 多目标/重要性/A/B/Drift增强模块已挂载 ✅", "INFO")
        except Exception as _enh_err:
            self._enhancement_hub = None
            self.log(f"[EnhancementHub] 挂载失败（不影响主流程）: {_enh_err}", "WARN")

        # 统计
        self.total_candidates_evaluated = 0
        self.total_improvements         = 0

        # 停滞检测
        self._stagnation_count = 0
        self._dynamic_population = self.POPULATION_SIZE

        # 精英库（保留历代最优基因组池）
        self._elite_pool = []   # [(score, genome), ...]  最多保留6个

        # 策略加权采样：记录每个策略的历史累计得分和出现次数
        # 权重 = 累计得分 / 出现次数（滑动平均胜率），用于有偏随机采样
        _all_strats = list(MutationEngine.STRATEGIES.keys())
        self._strategy_scores = {s: 0.0 for s in _all_strats}  # 累计得分（作为winner时）
        self._strategy_counts = {s: 1   for s in _all_strats}  # 出现次数（拉普拉斯平滑初值=1）

        # 从数据库恢复上次的策略权重（跨重启持久化）
        _saved_scores, _saved_counts = db_load_strategy_weights()
        if _saved_scores:
            for s in _all_strats:
                if s in _saved_scores:
                    self._strategy_scores[s] = _saved_scores[s]
                    self._strategy_counts[s] = _saved_counts.get(s, 1)
            self.log(f"[权重恢复] 从 DB 恢复 {len(_saved_scores)} 个策略权重，"
                     f"top1={max(_saved_scores, key=lambda k: _saved_scores[k]/max(_saved_counts.get(k,1),1))}")

    def log(self, msg: str, level: str = "INFO"):
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}][Gen{self.generation:03d}][{level}] {msg}"
        print(line)
        with self._lock:
            self.logs.append(line)
            if len(self.logs) > 500:
                self.logs.pop(0)
        try:
            db_log(level, msg)
        except Exception:
            pass

    def _crossover(self, g1: dict, g2: dict) -> dict:
        """精英交叉：随机混合两个基因组的数值参数"""
        child = copy.deepcopy(g1)
        for key in ["ucb_kappa", "ei_xi", "length_scale", "n_candidates", "n_random_init"]:
            if self.rng.rand() > 0.5:
                child[key] = g2.get(key, g1.get(key))
        # 采集函数随机继承
        if self.rng.rand() > 0.5:
            child["acquisition"] = g2.get("acquisition", g1.get("acquisition"))
        child["n_candidates"] = int(child["n_candidates"])
        child["n_random_init"] = int(child["n_random_init"])
        return child

    def _gen_candidates(self) -> list:
        """生成当前代的候选基因组（含自适应种群 + 精英交叉 + 停滞重置）"""
        strategies = list(MutationEngine.STRATEGIES.keys())
        candidates = []
        pop_size = self._dynamic_population

        # 总是包含当前基因组（无突变基准）
        candidates.append({
            "strategy": "baseline",
            "genome": copy.deepcopy(self.current_genome)
        })

        # 精英交叉：如果精英库 >= 2，则额外生成1个交叉后代
        if len(self._elite_pool) >= 2:
            idx = self.rng.choice(len(self._elite_pool), size=2, replace=False)
            child = self._crossover(self._elite_pool[idx[0]][1], self._elite_pool[idx[1]][1])
            candidates.append({"strategy": "elite_crossover", "genome": child})

        # 停滞重置：多样性注入（随机全新基因组）
        if self._stagnation_count >= self.STAGNATION_LIMIT:
            self.log(f"🔄 停滞 {self._stagnation_count} 代，注入随机探索基因组", "RESET")
            # 方案A：一次注入2个差异化基因组，覆盖更广的搜索空间
            for _inject in range(2):
                fresh = copy.deepcopy(EvolvableBayesianOptimizer.DEFAULT_GENOME)
                fresh["acquisition"] = self.rng.choice(["EI", "UCB", "PI", "Thompson"])
                fresh["ucb_kappa"]   = float(self.rng.uniform(0.3, 12.0))   # 原 0.5-8.0
                fresh["ei_xi"]       = float(self.rng.uniform(1e-5, 0.15))  # 原 0.08
                fresh["length_scale"]= float(self.rng.uniform(0.1, 6.0))    # 原 0.2-4.0
                fresh["n_candidates"]= int(self.rng.choice([256, 512, 768, 1024, 1200]))
                fresh["n_random_init"]= int(self.rng.choice([2, 3, 5, 8]))
                fresh["normalize_y"] = bool(self.rng.choice([True, False]))
                candidates.append({"strategy": "diversity_reset", "genome": fresh})

        # 加权突变填充至 pop_size
        # 权重 = 各策略的累计得分均值（经拉普拉斯平滑），高胜率策略被更频繁采样
        remain = pop_size - len(candidates)
        if remain > 0:
            avg_scores = np.array(
                [self._strategy_scores[s] / self._strategy_counts[s] for s in strategies],
                dtype=float
            )
            # 归一化为概率（softmax 风格，带温度系数 τ 控制探索/利用平衡）
            tau = max(0.3, 1.0 - self.generation * 0.02)  # 随代数降温，越晚越贪婪
            exp_s = np.exp((avg_scores - avg_scores.max()) / tau)
            probs = exp_s / exp_s.sum()
            chosen = self.rng.choice(strategies, size=remain, replace=True, p=probs)
            for strat in chosen:
                g = MutationEngine.mutate(self.current_genome, strat, self.rng)
                candidates.append({"strategy": strat, "genome": g})
            # 日志：打印当前前3高权重策略
            top3_idx = np.argsort(avg_scores)[::-1][:3]
            top3_info = "  ".join(
                f"{strategies[i]}({avg_scores[i]:.3f})" for i in top3_idx
            )
            self.log(f"[加权采样 τ={tau:.2f}] top3权重策略: {top3_info}")

        return candidates

    def _evaluate_candidate(self, cand: dict, gen: int, fine: bool = False) -> dict:
        """
        评估单个候选基因组。
        fine=False → 粗筛（快速，用于批量初筛）
        fine=True  → 精筛（高置信，用于 top-K 定档）
        """
        cand_id = hashlib.md5(
            (json.dumps(cand["genome"], sort_keys=True) + str(gen)).encode()
        ).hexdigest()[:12]

        db_upsert_candidate({
            "cand_id": cand_id, "generation": gen,
            "strategy_name": cand["strategy"],
            "config": json.dumps(cand["genome"]),
            "score": 0.0, "trials": 0, "is_winner": 0,
            "created_at": datetime.now().isoformat(), "evaluated_at": ""
        })

        t0 = time.time()
        if fine:
            score = self.evaluator.evaluate_fine(cand["genome"])
            phase_label = "精筛"
            n_trials_used = self.evaluator.FINE_TRIALS
        else:
            score = self.evaluator.evaluate_coarse(cand["genome"])
            phase_label = "粗筛"
            n_trials_used = self.evaluator.COARSE_TRIALS
        elapsed = time.time() - t0

        cand["score"]   = score
        cand["cand_id"] = cand_id
        self.total_candidates_evaluated += 1

        db_upsert_candidate({
            "cand_id": cand_id, "generation": gen,
            "strategy_name": cand["strategy"],
            "config": json.dumps(cand["genome"]),
            "score": score, "trials": n_trials_used, "is_winner": 0,
            "created_at": datetime.now().isoformat(),
            "evaluated_at": datetime.now().isoformat()
        })

        self.log(f"  [{phase_label}][{cand['strategy']:>20s}] 评分={score:.4f}  耗时={elapsed:.1f}s")
        return cand

    def _run_generation(self):
        """执行一代进化"""
        gen = self.generation
        self.log(f"═══ 第 {gen} 代进化开始 ═══", "GEN")

        # 1. 生成候选
        candidates = self._gen_candidates()
        self.log(f"生成 {len(candidates)} 个候选方案")

        db_upsert_generation({
            "generation": gen, "timestamp": datetime.now().isoformat(),
            "status": "evaluating", "winner_id": "",
            "best_score": self.best_score, "improvement": 0.0, "log": ""
        })

        # 2. 两阶段评估：先并行粗筛，再对 top-K 精筛
        # ── 阶段 1：粗筛（全部并行）
        self.log(f"[阶段1] 并行粗筛 {len(candidates)} 个候选…")
        coarse_results = [None] * len(candidates)
        def coarse_worker(i, cand):
            coarse_results[i] = self._evaluate_candidate(cand, gen, fine=False)

        threads = []
        for i, cand in enumerate(candidates):
            t = threading.Thread(target=coarse_worker, args=(i, cand), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        coarse_valid = [r for r in coarse_results if r is not None]
        coarse_valid.sort(key=lambda x: x["score"], reverse=True)

        # ── 阶段 2：精筛 top-K（并行）
        top_k = coarse_valid[:self.TOP_K_FINE]
        self.log(f"[阶段2] 精筛 top-{self.TOP_K_FINE}: "
                 f"{[c['strategy'] for c in top_k]}")
        fine_results = [None] * len(top_k)
        def fine_worker(i, cand):
            fine_results[i] = self._evaluate_candidate(cand, gen, fine=True)

        threads = []
        for i, cand in enumerate(top_k):
            t = threading.Thread(target=fine_worker, args=(i, cand), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        # 合并结果：精筛结果覆盖 top-K 的粗筛分数
        fine_by_id = {r["cand_id"]: r for r in fine_results if r is not None}
        valid = []
        for c in coarse_valid:
            cid = c.get("cand_id", "")
            valid.append(fine_by_id[cid] if cid in fine_by_id else c)
        valid.sort(key=lambda x: x["score"], reverse=True)

        if not valid:
            self.log("本代无有效候选，跳过", "WARN")
            return

        # 3. 选出精英
        winner = valid[0]

        improvement = winner["score"] - self.best_score
        improved    = improvement > 1e-4

        self.log(f"本代最优: [{winner['strategy']}] 评分={winner['score']:.4f}  "
                 f"{'↑ +{:.4f}'.format(improvement) if improved else '→ 无提升'}")

        # 4. 更新最优 + 停滞检测
        if improved:
            self.best_score  = winner["score"]
            self.best_genome = copy.deepcopy(winner["genome"])
            self.total_improvements += 1
            self._stagnation_count = 0  # 重置停滞计数
            self.log(f"★ 新最佳！评分={self.best_score:.4f}  策略={winner['strategy']}", "WIN")
            # ── 通知：新历史最优 ──────────────────────────────────────────────
            if self._notifier:
                try:
                    self._notifier.on_new_best(
                        gen=gen, score=self.best_score,
                        genome_hint=f"{winner['genome'].get('acquisition','?')} kappa={winner['genome'].get('ucb_kappa',0):.2f}"
                    )
                except Exception:
                    pass
            db_save_version(
                version_id=winner["cand_id"],
                generation=gen,
                config={**winner["genome"], "_strategy": winner["strategy"]},
                score=winner["score"],
                active=1
            )
        else:
            self._stagnation_count += 1
            if self._stagnation_count > 0 and self._stagnation_count % 2 == 0:
                self.log(f"⚠ 停滞 {self._stagnation_count} 代，当前最优 {self.best_score:.4f}", "STAG")

        # 自适应种群大小：有提升时缩小（更精细利用），停滞时扩大（更广泛探索）
        if improved:
            self._dynamic_population = max(self.MIN_POPULATION, self._dynamic_population - 1)
        elif self._stagnation_count >= self.STAGNATION_LIMIT:
            self._dynamic_population = min(self.MAX_POPULATION, self._dynamic_population + 2)
            self._stagnation_count = 0  # 重置，允许重新增长
            # ── 通知：停滞重置 ────────────────────────────────────────────────
            if self._notifier:
                try:
                    self._notifier.on_stagnation_reset(gen=gen, stagnation_count=self.STAGNATION_LIMIT)
                except Exception:
                    pass

        # 维护精英库（最多保留6个不重复最优基因组）
        self._elite_pool.append((winner["score"], copy.deepcopy(winner["genome"])))
        self._elite_pool.sort(key=lambda x: x[0], reverse=True)
        self._elite_pool = self._elite_pool[:6]

        # 更新策略加权历史
        # ① winner 策略：累计得分 + 出现次数 +1
        # ② 其他参评策略（runner-up）：出现次数 +1，得分按比例给（避免全 0 马太效应）
        win_strat = winner.get("strategy", "")
        if win_strat in self._strategy_scores:
            self._strategy_scores[win_strat] += winner["score"]
            self._strategy_counts[win_strat] += 1
        # runner-up 也记录出现，得到小额奖励（避免从未被选中的策略沦为死权重）
        for cand in valid[1:]:
            s = cand.get("strategy", "")
            if s in self._strategy_scores:
                self._strategy_counts[s] += 1
                self._strategy_scores[s] += cand["score"] * 0.2  # 小额补偿

        # 每代结束后持久化策略权重到 SQLite（跨重启恢复进化记忆）
        try:
            db_save_strategy_weights(self._strategy_scores, self._strategy_counts)
        except Exception as _e:
            self.log(f"[权重持久化] 写入失败（不影响运行）: {_e}", "WARN")

        # ✅ 进化基因组反哺 autorun：把本代最优基因组推给 AutoRunEngine
        try:
            # 懒导入，避免循环引用
            from autoresearch_unified_server import _autorun_engine as _ae
            if _ae is not None and hasattr(_ae, "push_evolved_genome"):
                _genome_copy = copy.deepcopy(winner["genome"])
                _genome_copy["_gen"] = self.generation
                _ae.push_evolved_genome(
                    _genome_copy,
                    tag=f"gen{self.generation}_{winner.get('strategy','?')}"
                )
                self.log(f"[反哺] 最优基因组已推送 → AutoRun  "
                         f"acq={_genome_copy.get('acquisition','?')}  "
                         f"kappa={_genome_copy.get('ucb_kappa',0):.3f}")
        except Exception as _fe:
            self.log(f"[反哺] 推送跳过: {_fe}", "DEBUG")

        # 5. 更新下一代基础（精英继承）
        n_elite = max(1, int(len(valid) * self.ELITE_RATIO))
        # 以加权平均方式混合精英基因组
        if n_elite > 1:
            new_genome = copy.deepcopy(valid[0]["genome"])
            # 对数值参数做精英加权平均（top1权重更高）
            weights = np.array([1.0 / (i + 1) for i in range(n_elite)])
            weights = weights / weights.sum()
            for key in ["ucb_kappa", "ei_xi", "length_scale", "n_candidates", "n_random_init"]:
                vals = np.array([valid[i]["genome"].get(key, self.current_genome[key])
                                 for i in range(n_elite)])
                new_genome[key] = float(np.dot(weights, vals))
            new_genome["n_candidates"] = int(new_genome["n_candidates"])
            new_genome["n_random_init"] = int(new_genome["n_random_init"])
        else:
            new_genome = copy.deepcopy(valid[0]["genome"])

        self.current_genome = new_genome
        self.log(f"种群大小={self._dynamic_population}  精英库={len(self._elite_pool)}", "INFO")

        # 6. 标记 winner
        con = sqlite3.connect(str(DB_PATH))
        con.execute("UPDATE candidates SET is_winner=1 WHERE cand_id=?", (winner["cand_id"],))
        con.commit(); con.close()

        # 7. 记录
        self.history.append((gen, winner["score"], copy.deepcopy(winner["genome"])))

        # 8. 多样性评估（基因组间的欧氏距离）
        def genome_vec(g):
            return np.array([
                g.get("ucb_kappa",2.576)/10, g.get("ei_xi",0.01)/0.1,
                g.get("length_scale",1.0)/5, g.get("n_candidates",256)/1024,
                1.0 if g.get("normalize_y",True) else 0.0
            ])
        if len(valid) > 1:
            vecs = [genome_vec(v["genome"]) for v in valid]
            dists = []
            for i in range(len(vecs)):
                for j in range(i+1, len(vecs)):
                    dists.append(np.linalg.norm(vecs[i]-vecs[j]))
            diversity = float(np.mean(dists)) if dists else 0.0
        else:
            diversity = 0.0

        avg_score = float(np.mean([v["score"] for v in valid]))

        db_upsert_generation({
            "generation": gen, "timestamp": datetime.now().isoformat(),
            "status": "done", "winner_id": winner["cand_id"],
            "best_score": winner["score"],
            "improvement": float(improvement), "log": ""
        })

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
        except Exception:
            cpu, mem = 0.0, 0.0

        db_add_metric(gen, self.best_score, avg_score, diversity, float(improvement), cpu, mem)

        self.log(f"第 {gen} 代完成  avg={avg_score:.4f}  diversity={diversity:.3f}  "
                 f"全局最优={self.best_score:.4f}  累计提升次数={self.total_improvements}")

        # ── 通知：每代完成（内部节流，每N代发一次）───────────────────────────
        if self._notifier:
            try:
                self._notifier.on_evolution_complete(gen=gen, score=winner["score"],
                                                     improvement=float(improvement))
            except Exception:
                pass

        # ── 搜索 & 学习总结技能：每 LEARN_INTERVAL 代自动触发 ────────────────
        if getattr(self, "_insight_engine", None) is not None:
            try:
                self._insight_engine.learn_and_apply(gen)
            except Exception as _ins_err:
                self.log(f"[InsightEngine] 本轮跳过: {_ins_err}", "DEBUG")

        # ── EnhancementHub：每代通知（多目标/参数重要性/Drift响应）──────────
        if getattr(self, "_enhancement_hub", None) is not None:
            try:
                # 检查是否有漂移事件（通过 drift_adapter）
                _drift_event = None
                da = getattr(self, "_drift_adapter", None)
                if da:
                    events = getattr(da._detector, "events", [])
                    if events and abs(events[-1].ts - time.time()) < 5:
                        ev = events[-1]
                        _drift_event = {"method": ev.method, "score": ev.score,
                                        "threshold": ev.threshold}
                self._enhancement_hub.on_generation_end(
                    gen=gen,
                    best_score=self.best_score,
                    drift_event=_drift_event
                )
            except Exception as _enh_err:
                self.log(f"[EnhancementHub] 本轮跳过: {_enh_err}", "DEBUG")

    def run_forever(self):
        """无限进化主循环"""
        self.log("★ AutoResearch 自主进化引擎启动 ★", "START")
        self.log(f"初始基因组: {json.dumps(self.current_genome, indent=2)}")

        # 先评估基线
        self.log("评估初始基线...")
        baseline_score = self.evaluator.evaluate_all(self.current_genome)
        self.best_score = baseline_score
        self.log(f"基线评分: {baseline_score:.4f}")

        db_save_version(
            version_id="baseline_v0",
            generation=0,
            config={**self.current_genome, "_strategy": "baseline"},
            score=baseline_score,
            active=1
        )

        while not self.stop_event.is_set():
            try:
                self._run_generation()
                self.generation += 1
                time.sleep(0.5)   # 短暂休息，让监控有时间读取
            except KeyboardInterrupt:
                self.log("收到中断信号，正在停止...", "STOP")
                break
            except Exception as e:
                self.log(f"本代出错: {traceback.format_exc()}", "ERR")
                time.sleep(2)
                self.generation += 1  # 跳过出错的代

        self.log(f"进化结束。总代数={self.generation}  "
                 f"全局最优={self.best_score:.4f}  "
                 f"累计提升={self.total_improvements}次")


# ── 主入口 ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  AutoResearch 自主进化引擎 v1.0")
    print("  ──────────────────────────────────────────────────")
    print("  系统将持续分析自身算法，生成改进方案，无限迭代")
    print("=" * 65)

    init_db()
    print(f"[DB] 数据库: {DB_PATH}")

    controller = SelfEvolveController()

    # 优雅退出
    import signal
    def _sig(sig, frame):
        print("\n[STOP] 收到停止信号，等待当前代完成...")
        controller.stop_event.set()
    signal.signal(signal.SIGINT, _sig)

    controller.run_forever()


if __name__ == "__main__":
    main()
