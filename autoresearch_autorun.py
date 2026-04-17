"""
AutoResearch 自动运行引擎
========================
后台自动调度优化任务，持续运行并向监控系统推送数据

改进日志（2026-03-25）：
  ① 真实 CPU/内存：用 psutil 替换 random.uniform 假数据
  ② 进化基因组反哺：每代结束后进化引擎推送最优 genome，autorun 消费
  ③ 任务自动重跑：completed 任务用最新 genome 重新排队（持续优化闭环）
  ④ learning_score 改为真实指标：基于任务历史改进率均值计算
  ⑤ completed_count 字段修复：snapshot 序列化字段名对齐
  ⑥ SQLite WAL 模式：防止并发锁竞争
  ⑦ 任务暂停/重跑 API：新增 pause_task / resume_task / restart_task
"""

import time
import math
import random
import threading
import json
import sqlite3
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

# 真实系统指标（psutil）
try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

# 通知推送（懒加载，失败不影响主流程）
def _get_notifier():
    try:
        from autoresearch_notify import get_notifier
        return get_notifier()
    except Exception:
        return None


def _real_cpu() -> float:
    """返回真实 CPU 使用率（%），失败则返回 -1"""
    if not _HAS_PSUTIL:
        return -1.0
    try:
        return _psutil.cpu_percent(interval=None)
    except Exception:
        return -1.0


def _real_mem() -> float:
    """返回真实内存使用率（%），失败则返回 -1"""
    if not _HAS_PSUTIL:
        return -1.0
    try:
        return _psutil.virtual_memory().percent
    except Exception:
        return -1.0


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class OptimizationTask:
    task_id: str
    name: str
    status: str          # pending / running / completed / failed / paused
    progress: float      # 0-100
    best_score: float
    current_score: float
    iterations: int
    max_iterations: int
    strategy: str
    start_time: Optional[str]
    end_time: Optional[str]
    log: List[str]
    # 跨轮次追踪
    run_round: int = 0          # 本任务第几轮（重跑时递增）
    genome_tag: str = "default" # 使用的基因组版本标签
    improvement_pct: float = 0.0  # 本轮改进百分比


@dataclass
class SystemMetrics:
    timestamp: str
    cpu_usage: float
    memory_usage: float
    active_tasks: int
    completed_tasks: int
    total_improvements: float
    learning_score: float


# ─────────────────────────────────────────────
# 测试用目标函数（模拟真实优化任务）
# ─────────────────────────────────────────────

def rosenbrock(params):
    """Rosenbrock函数（banana函数，经典优化测试）"""
    x = params.get("x", 0)
    y = params.get("y", 0)
    val = (1 - x) ** 2 + 100 * (y - x ** 2) ** 2
    return -val  # 最大化负值 = 最小化原函数


def rastrigin(params):
    """Rastrigin函数（多模态测试）"""
    n = 2
    vals = [params.get(f"x{i}", 0) for i in range(n)]
    result = -10 * n - sum(x ** 2 - 10 * math.cos(2 * math.pi * x) for x in vals)
    return result


def sphere(params):
    """球形函数（简单凸函数）"""
    vals = [params.get(k, 0) for k in params]
    return -sum(x ** 2 for x in vals)


def ackley(params):
    """Ackley函数（高维多模态）"""
    x = params.get("x", 0)
    y = params.get("y", 0)
    val = (
        -20 * math.exp(-0.2 * math.sqrt(0.5 * (x**2 + y**2)))
        - math.exp(0.5 * (math.cos(2 * math.pi * x) + math.cos(2 * math.pi * y)))
        + math.e + 20
    )
    return -val


# ─────────────────────────────────────────────
# 简易贝叶斯优化器（内置，无外部依赖）
# 支持接收进化引擎推来的最优基因组参数
# ─────────────────────────────────────────────

class SimpleBayesianOptimizer:
    def __init__(self, search_space: Dict, strategy: str = "EI", genome: Dict = None):
        self.search_space = search_space
        self.strategy = strategy
        self.history = []  # [(params, score)]
        self.best_params = None
        self.best_score = float("-inf")
        # 从进化引擎基因组中提取参数（若有）
        self._kappa      = 2.0   # UCB 探索系数
        self._xi         = 0.01  # EI 改进量
        self._explore_p  = 0.3   # 随机探索概率
        if genome:
            self._apply_genome(genome)

    def _apply_genome(self, genome: Dict):
        """把进化引擎的最优基因组参数写入本优化器"""
        acq = genome.get("acquisition", self.strategy)
        if acq in ("EI", "UCB", "PI", "Thompson"):
            self.strategy = acq
        self._kappa     = float(genome.get("ucb_kappa", self._kappa))
        self._xi        = float(genome.get("ei_xi",     self._xi))
        # n_random_init 影响初始随机探索比例
        n_rand          = int(genome.get("n_random_init", 5))
        self._explore_p = max(0.1, min(0.5, n_rand / 20.0))

    def _random_sample(self) -> Dict:
        params = {}
        for key, bounds in self.search_space.items():
            lo, hi = bounds
            params[key] = lo + random.random() * (hi - lo)
        return params

    def _ei_sample(self) -> Dict:
        """Expected Improvement：在历史最优附近添加自适应扰动（xi 控制探索幅度）"""
        if not self.history or random.random() < self._explore_p:
            return self._random_sample()
        best_p = max(self.history, key=lambda x: x[1])[0]
        params = {}
        for key, bounds in self.search_space.items():
            lo, hi = bounds
            delta = (hi - lo) * max(0.05, self._xi * 10)
            val = best_p[key] + random.gauss(0, delta)
            params[key] = max(lo, min(hi, val))
        return params

    def _ucb_sample(self) -> Dict:
        """UCB：kappa 越大越倾向探索"""
        if not self.history or random.random() < min(0.5, self._kappa / 10.0):
            return self._random_sample()
        return self._ei_sample()

    def _pi_sample(self) -> Dict:
        """PI（Probability of Improvement）：保守型，偏利用"""
        if not self.history or random.random() < 0.2:
            return self._random_sample()
        best_p = max(self.history, key=lambda x: x[1])[0]
        params = {}
        for key, bounds in self.search_space.items():
            lo, hi = bounds
            delta = (hi - lo) * 0.08
            val = best_p[key] + random.gauss(0, delta)
            params[key] = max(lo, min(hi, val))
        return params

    def _thompson_sample(self) -> Dict:
        """Thompson Sampling：随机扰动历史最优点集合"""
        if not self.history or random.random() < 0.35:
            return self._random_sample()
        # 从 top-3 中随机选一个作为基准
        top = sorted(self.history, key=lambda x: x[1], reverse=True)[:3]
        base_p = random.choice(top)[0]
        params = {}
        for key, bounds in self.search_space.items():
            lo, hi = bounds
            delta = (hi - lo) * 0.12
            val = base_p[key] + random.gauss(0, delta)
            params[key] = max(lo, min(hi, val))
        return params

    def suggest(self) -> Dict:
        if self.strategy == "EI":
            return self._ei_sample()
        elif self.strategy == "UCB":
            return self._ucb_sample()
        elif self.strategy == "PI":
            return self._pi_sample()
        elif self.strategy == "Thompson":
            return self._thompson_sample()
        else:
            return self._random_sample()

    def observe(self, params: Dict, score: float):
        self.history.append((params, score))
        if score > self.best_score:
            self.best_score = score
            self.best_params = params


# ─────────────────────────────────────────────
# 自动运行引擎
# ─────────────────────────────────────────────

class AutoRunEngine:
    """
    自动运行引擎
    - 维护一个任务队列
    - 后台线程自动执行优化任务
    - 结果写入 SQLite，供监控读取
    """

    DB_PATH = "autorun_monitor.db"

    # 预定义任务配置
    TASK_TEMPLATES = [
        {
            "name": "图像分类超参优化",
            "func": rosenbrock,
            "space": {"x": (-2, 2), "y": (-1, 3)},
            "max_iter": 30,
            "strategy": "EI",
        },
        {
            "name": "NLP模型调参",
            "func": rastrigin,
            "space": {"x0": (-5, 5), "x1": (-5, 5)},
            "max_iter": 25,
            "strategy": "UCB",
        },
        {
            "name": "强化学习策略优化",
            "func": ackley,
            "space": {"x": (-5, 5), "y": (-5, 5)},
            "max_iter": 20,
            "strategy": "EI",
        },
        {
            "name": "深度网络架构搜索",
            "func": sphere,
            "space": {"lr": (1e-5, 1e-1), "wd": (1e-6, 1e-2), "drop": (0, 0.5)},
            "max_iter": 35,
            "strategy": "PI",
        },
    ]

    def __init__(self):
        self.tasks: Dict[str, OptimizationTask] = {}
        self.metrics_history: List[SystemMetrics] = []
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._task_counter = 0
        self._completed_count = 0
        self._total_improvement = 0.0
        self._learning_score = 0.50
        # ── 进化基因组反哺槽 ──────────────────────────────────────────────
        # 进化引擎每代结束后调用 push_evolved_genome() 推入最优基因组
        # _scheduler_loop 创建任务时消费此值
        self._current_genome: Optional[Dict] = None
        self._genome_tag: str = "default"
        self._genome_lock = threading.Lock()
        # ── 自动重跑追踪 ─────────────────────────────────────────────────
        # 记录每个任务名的「最佳历史轮次得分」，用于计算累计改进
        self._template_best: Dict[str, float] = {}
        # 改进率历史（用于计算真实 learning_score）
        self._improvement_history: List[float] = []
        # 任务名 -> 重跑计数
        self._run_rounds: Dict[str, int] = {}
        self._init_db()
        # 注入真实任务（PyTorch MNIST / SVM / 树模型）
        try:
            from real_task_adapter import RealTaskAdapter
            _adapter = RealTaskAdapter()
            added = _adapter.inject_presets_to_engine(self)
            print(f"[AutoRun] 真实任务已注入: {added}")
        except Exception as _e:
            print(f"[AutoRun] 真实任务注入跳过: {_e}")

    # ── 数据库初始化 ──────────────────────────────

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        # ✅ WAL 模式：并发读写不互相阻塞
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT,
                progress REAL,
                best_score REAL,
                current_score REAL,
                iterations INTEGER,
                max_iterations INTEGER,
                strategy TEXT,
                start_time TEXT,
                end_time TEXT,
                log TEXT,
                updated_at TEXT,
                run_round INTEGER DEFAULT 0,
                genome_tag TEXT DEFAULT 'default',
                improvement_pct REAL DEFAULT 0.0
            )
        """)
        # 补充旧表缺少的列（兼容已有数据库）
        for col, definition in [
            ("run_round",       "INTEGER DEFAULT 0"),
            ("genome_tag",      "TEXT DEFAULT 'default'"),
            ("improvement_pct", "REAL DEFAULT 0.0"),
        ]:
            try:
                c.execute(f"ALTER TABLE tasks ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

        c.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                cpu_usage REAL,
                memory_usage REAL,
                active_tasks INTEGER,
                completed_tasks INTEGER,
                total_improvements REAL,
                learning_score REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS system_status (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # ✅ 跨轮次历史表：记录每个任务名每一轮的最终最佳分
        c.execute("""
            CREATE TABLE IF NOT EXISTS task_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                run_round INTEGER,
                best_score REAL,
                genome_tag TEXT,
                improvement_pct REAL DEFAULT 0.0,
                completed_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _save_task(self, task: OptimizationTask):
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            task.task_id, task.name, task.status,
            task.progress, task.best_score, task.current_score,
            task.iterations, task.max_iterations, task.strategy,
            task.start_time, task.end_time,
            json.dumps(task.log[-20:], ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            task.run_round, task.genome_tag, task.improvement_pct,
        ))
        conn.commit()
        conn.close()

    def _save_round_history(self, task: OptimizationTask):
        """任务完成后把本轮结果写入 task_rounds 历史表"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            INSERT INTO task_rounds(task_name, run_round, best_score, genome_tag, improvement_pct, completed_at)
            VALUES(?,?,?,?,?,?)
        """, (task.name, task.run_round, task.best_score,
              task.genome_tag, task.improvement_pct,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    def _save_metrics(self, m: SystemMetrics):
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("""
            INSERT INTO metrics
            (timestamp,cpu_usage,memory_usage,active_tasks,completed_tasks,total_improvements,learning_score)
            VALUES (?,?,?,?,?,?,?)
        """, (
            m.timestamp, m.cpu_usage, m.memory_usage,
            m.active_tasks, m.completed_tasks,
            m.total_improvements, m.learning_score
        ))
        # 只保留最近200条
        c.execute("DELETE FROM metrics WHERE id NOT IN (SELECT id FROM metrics ORDER BY id DESC LIMIT 200)")
        conn.commit()
        conn.close()

    def _set_status(self, key: str, value: str):
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO system_status VALUES (?,?)", (key, value))
        conn.commit()
        conn.close()

    # ── 公开接口：接收进化引擎推来的最优基因组 ──────────────────────
    def push_evolved_genome(self, genome: Dict, tag: str = ""):
        """
        进化引擎每代结束后调用此方法，把最优基因组推入 autorun 引擎。
        下次创建任务时，SimpleBayesianOptimizer 会使用这个基因组初始化。
        """
        with self._genome_lock:
            self._current_genome = genome
            self._genome_tag = tag or f"gen_{genome.get('_gen', '?')}"
        print(f"[AutoRun] 📡 接收进化基因组 tag={self._genome_tag} "
              f"acq={genome.get('acquisition','?')} kappa={genome.get('ucb_kappa','?'):.3f}")

    def _get_genome(self) -> tuple:
        """获取当前基因组（线程安全）"""
        with self._genome_lock:
            return self._current_genome, self._genome_tag

    # ── 任务暂停 / 恢复 / 重跑 ──────────────────────────────────────
    def pause_task(self, task_id: str) -> bool:
        """暂停运行中的任务（设置 paused 标志，任务循环内检测后停止当前迭代）"""
        with self.lock:
            t = self.tasks.get(task_id)
            if t and t.status == "running":
                t.status = "paused"
                t.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 任务已暂停")
                self._save_task(t)
                return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """恢复暂停的任务（重新提交到线程池）"""
        with self.lock:
            t = self.tasks.get(task_id)
            if t and t.status == "paused":
                t.status = "pending"
                t.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 任务已恢复排队")
                self._save_task(t)
                # 找到对应的模板
                tmpl = next((tp for tp in self.TASK_TEMPLATES if tp["name"] == t.name), None)
                if tmpl:
                    th = threading.Thread(target=self._run_task, args=(t, tmpl),
                                          daemon=True, name=f"task-{task_id}")
                    th.start()
                    return True
        return False

    def restart_task(self, task_id: str) -> str:
        """重跑一个 completed 任务（用最新基因组，轮次+1）"""
        with self.lock:
            old = self.tasks.get(task_id)
            if not old or old.status not in ("completed", "failed"):
                return ""
            tmpl = next((tp for tp in self.TASK_TEMPLATES if tp["name"] == old.name), None)
            if not tmpl:
                return ""
            self._task_counter += 1
            new_tid = f"task_{self._task_counter:04d}"
            genome, gtag = self._get_genome()
            run_round = self._run_rounds.get(old.name, 0) + 1
            self._run_rounds[old.name] = run_round
            new_task = OptimizationTask(
                task_id=new_tid, name=old.name,
                status="running",   # ⬆ 提前标记，防止竞态导致重复启动
                progress=0.0,
                best_score=float("-inf"), current_score=0.0,
                iterations=0, max_iterations=old.max_iterations,
                strategy=tmpl["strategy"],
                start_time=None, end_time=None, log=[],
                run_round=run_round, genome_tag=gtag,
            )
            self.tasks[new_tid] = new_task
        self._save_task(new_task)
        th = threading.Thread(target=self._run_task, args=(new_task, tmpl),
                              daemon=True, name=f"task-{new_tid}")
        th.start()
        return new_tid

    # ── 单任务执行线程 ────────────────────────────

    def _run_task(self, task: OptimizationTask, template: Dict):
        func = template["func"]
        # ✅ 使用进化引擎推来的最优基因组初始化优化器
        genome, gtag = self._get_genome()
        optimizer = SimpleBayesianOptimizer(template["space"], task.strategy, genome=genome)
        task.genome_tag = gtag

        task.status = "running"
        task.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task.log.append(
            f"[{task.start_time}] 任务启动，策略={optimizer.strategy}"
            f"  genome={gtag}"
        )
        self._save_task(task)

        initial_score = None

        for i in range(task.max_iterations):
            if self._stop_event.is_set():
                break
            # ✅ 暂停检测：任务状态被外部设为 paused 时中断当前迭代
            with self.lock:
                if task.status == "paused":
                    task.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代暂停于第{i}轮")
                    self._save_task(task)
                    return

            params = optimizer.suggest()
            time.sleep(random.uniform(0.3, 0.8))

            score = func(params)
            score += random.gauss(0, abs(score) * 0.03)

            optimizer.observe(params, score)

            if initial_score is None:
                initial_score = score

            with self.lock:
                task.iterations = i + 1
                task.current_score = score
                task.best_score = optimizer.best_score
                task.progress = (i + 1) / task.max_iterations * 100

                if (i + 1) % 5 == 0 or i == 0:
                    ts = datetime.now().strftime("%H:%M:%S")
                    task.log.append(
                        f"[{ts}] 第{i+1}轮 当前={score:.4f} 最佳={optimizer.best_score:.4f}"
                    )

            self._save_task(task)

        # ── 任务完成结算 ─────────────────────────────────────────────
        with self.lock:
            task.status = "completed"
            task.progress = 100.0
            task.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ✅ 计算本轮改进率（相对于该任务名历史最优）
            hist_best = self._template_best.get(task.name, None)
            if initial_score is not None and optimizer.best_score > float("-inf"):
                if hist_best is None:
                    impr_pct = 0.0
                else:
                    impr_pct = (optimizer.best_score - hist_best) / (abs(hist_best) + 1e-9) * 100
                task.improvement_pct = round(impr_pct, 2)
                # 更新历史最优
                if hist_best is None or optimizer.best_score > hist_best:
                    self._template_best[task.name] = optimizer.best_score

            task.log.append(
                f"[{task.end_time}] 任务完成！最佳={optimizer.best_score:.4f}"
                f"  改进={task.improvement_pct:+.1f}%  基因组={gtag}"
            )

            self._completed_count += 1

            if initial_score is not None and optimizer.best_score > initial_score:
                improvement = abs(
                    (optimizer.best_score - initial_score) / (abs(initial_score) + 1e-9)
                ) * 100
                self._total_improvement += improvement
                # ✅ 记录到改进率历史（用于真实 learning_score 计算）
                self._improvement_history.append(improvement)
                if len(self._improvement_history) > 50:
                    self._improvement_history.pop(0)

            # ✅ 真实 learning_score = 近期改进率均值归一化到 [0, 1]
            if self._improvement_history:
                avg_impr = sum(self._improvement_history) / len(self._improvement_history)
                # 改进率 0% → 0.5，100% → ~0.9，用 sigmoid 映射
                self._learning_score = round(
                    0.5 + 0.45 * (1 - math.exp(-avg_impr / 50.0)), 3
                )
            else:
                self._learning_score = 0.50

        self._save_task(task)
        # ✅ 写入跨轮次历史
        self._save_round_history(task)
        # ── 通知：任务完成 ────────────────────────────────────────────────────
        try:
            _n = _get_notifier()
            if _n:
                _n.on_evolution_complete(
                    gen=self._completed_count,
                    score=optimizer.best_score,
                    improvement=task.improvement_pct / 100.0
                )
        except Exception:
            pass

    # ── 系统指标采集线程 ──────────────────────────

    def _metrics_loop(self):
        while not self._stop_event.is_set():
            with self.lock:
                active = sum(1 for t in self.tasks.values() if t.status == "running")
                m = SystemMetrics(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    # ✅ 真实 CPU / 内存（psutil），无法读取时 fallback -1
                    cpu_usage=_real_cpu(),
                    memory_usage=_real_mem(),
                    active_tasks=active,
                    completed_tasks=self._completed_count,
                    total_improvements=self._total_improvement,
                    learning_score=self._learning_score,
                )
            with self.lock:
                self.metrics_history.append(m)
                if len(self.metrics_history) > 200:
                    self.metrics_history.pop(0)
            self._save_metrics(m)
            self._set_status("last_heartbeat", datetime.now().isoformat())
            time.sleep(2)

    # ── 任务调度主循环 ────────────────────────────

    def _scheduler_loop(self):
        """
        调度策略（改进版）：
        1. 保持 1~2 个并发任务
        2. 优先重跑「已完成任务中，最久没有刷新的那个」（使用最新基因组）
        3. 若无 completed 任务可重跑，则按顺序创建新任务
        """
        template_idx = 0
        while not self._stop_event.is_set():
            with self.lock:
                running = sum(1 for t in self.tasks.values() if t.status == "running")

            if running < 2:
                # ✅ 优先找一个 completed 任务来重跑
                rerun_tid = None
                with self.lock:
                    completed = [t for t in self.tasks.values() if t.status == "completed"]
                if completed:
                    # 选最早完成（end_time 最小）的那个
                    oldest = min(completed, key=lambda t: t.end_time or "")
                    rerun_tid = oldest.task_id

                if rerun_tid:
                    new_tid = self.restart_task(rerun_tid)
                    if new_tid:
                        genome, gtag = self._get_genome()
                        print(f"[AutoRun] ♻️ 重跑任务 {self.tasks[rerun_tid].name}→{new_tid} "
                              f"genome={gtag}")
                else:
                    # 没有 completed 可重跑，创建新任务
                    tmpl = self.TASK_TEMPLATES[template_idx % len(self.TASK_TEMPLATES)]
                    template_idx += 1
                    self._task_counter += 1
                    tid = f"task_{self._task_counter:04d}"
                    genome, gtag = self._get_genome()
                    run_round = self._run_rounds.get(tmpl["name"], 0) + 1
                    self._run_rounds[tmpl["name"]] = run_round

                    task = OptimizationTask(
                        task_id=tid,
                        name=tmpl["name"],
                        status="running",   # ⬆ 提前标记，防止竞态导致重复启动
                        progress=0.0,
                        best_score=float("-inf"),
                        current_score=0.0,
                        iterations=0,
                        max_iterations=tmpl["max_iter"],
                        strategy=tmpl["strategy"],
                        start_time=None,
                        end_time=None,
                        log=[],
                        run_round=run_round,
                        genome_tag=gtag,
                    )
                    with self.lock:
                        self.tasks[tid] = task

                    self._save_task(task)

                    t = threading.Thread(
                        target=self._run_task,
                        args=(task, tmpl),
                        daemon=True,
                        name=f"task-{tid}"
                    )
                    t.start()

            time.sleep(5)

    # ── 公开接口 ──────────────────────────────────

    def start(self):
        self._stop_event.clear()
        self._set_status("engine_status", "running")
        self._set_status("start_time", datetime.now().isoformat())

        threading.Thread(target=self._metrics_loop, daemon=True, name="metrics").start()
        threading.Thread(target=self._scheduler_loop, daemon=True, name="scheduler").start()
        print("[AutoRunEngine] 自动运行引擎已启动")

    def stop(self):
        self._stop_event.set()
        self._set_status("engine_status", "stopped")
        print("[AutoRunEngine] 引擎已停止")

    def get_snapshot(self) -> Dict:
        with self.lock:
            tasks_list = [asdict(t) for t in self.tasks.values()]
        genome, gtag = self._get_genome()
        return {
            "tasks": tasks_list,
            # ✅ 修复：统一用 completed_count（旧版叫 completed，导致 Dashboard 显示空）
            "completed_count": self._completed_count,
            "completed": self._completed_count,   # 保留兼容旧字段
            "learning_score": self._learning_score,
            "total_improvement": self._total_improvement,
            "current_genome_tag": gtag,
            "improvement_history": list(self._improvement_history[-10:]),
        }

    def get_round_history(self, task_name: str = None) -> List[Dict]:
        """读取跨轮次历史（供 Dashboard 趋势图使用）"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        if task_name:
            rows = conn.execute(
                "SELECT * FROM task_rounds WHERE task_name=? ORDER BY run_round",
                (task_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM task_rounds ORDER BY completed_at DESC LIMIT 200"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# 独立运行入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    engine = AutoRunEngine()
    engine.start()
    try:
        while True:
            snap = engine.get_snapshot()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                  f"运行中任务: {sum(1 for t in snap['tasks'] if t['status']=='running')} | "
                  f"完成: {snap['completed']} | "
                  f"学习分数: {snap['learning_score']:.2%}")
            time.sleep(5)
    except KeyboardInterrupt:
        engine.stop()
        print("已停止")
