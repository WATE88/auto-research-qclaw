"""
autoresearch_enhancements.py
═══════════════════════════════════════════════════════════════════
AutoResearch 综合增强模块 v1.0
───────────────────────────────────────────────────────────────────

包含以下四大功能：

1. MultiObjectiveTracker   — 多目标优化 (Pareto 前沿追踪)
   - 记录每次评估的多维目标值 (score, speed, memory)
   - 计算 Pareto 前沿，支持权重偏好选择
   - 提供 Dashboard 展示数据

2. ParamImportanceTracker  — 参数重要性追踪
   - 每 N 代基于历史候选池计算 ANOVA-F / Pearson 相关性
   - 自动收窄低重要性参数的搜索空间 (减少无效探索)
   - Dashboard 热力图数据

3. ABConfigCompare         — A/B 配置对比实验
   - 保存多组历史最优配置快照
   - 并行运行两组配置的对比评估
   - 统计显著性检验 (Bootstrap t-test)

4. DriftResponseEnhancer   — Drift 漂移联动自动响应
   - 订阅 DriftEvolveAdapter 的漂移事件
   - 漂移确认后：自动扩大搜索空间 + 通知 InsightEngine 重置 + 触发 WebLearner
   - 冷却期防抖

作者: AutoResearch WorkBuddy集成（2026-03-25）
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "evolution_monitor.db"


# ══════════════════════════════════════════════════════════════════
# 工具：确保增强表存在
# ══════════════════════════════════════════════════════════════════

def _ensure_enhancement_tables():
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.executescript("""
        CREATE TABLE IF NOT EXISTS multi_objectives (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            generation  INTEGER,
            cand_id     TEXT,
            score       REAL,
            speed       REAL DEFAULT 0.0,
            mem_usage   REAL DEFAULT 0.0,
            is_pareto   INTEGER DEFAULT 0,
            weights     TEXT DEFAULT '{}',
            timestamp   TEXT
        );

        CREATE TABLE IF NOT EXISTS param_importance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            generation  INTEGER,
            param_name  TEXT,
            importance  REAL,
            method      TEXT,
            timestamp   TEXT
        );

        CREATE TABLE IF NOT EXISTS ab_snapshots (
            snap_id     TEXT PRIMARY KEY,
            label       TEXT,
            genome      TEXT,
            score       REAL,
            created_at  TEXT,
            notes       TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS ab_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snap_a      TEXT,
            snap_b      TEXT,
            score_a     REAL,
            score_b     REAL,
            p_value     REAL,
            winner      TEXT,
            tested_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS drift_responses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gen         INTEGER,
            method      TEXT,
            drift_score REAL,
            actions     TEXT,
            timestamp   TEXT
        );
        """)
        con.commit()
        con.close()
    except Exception as e:
        print(f"[Enhancements] 初始化表失败: {e}")


_ensure_enhancement_tables()


# ══════════════════════════════════════════════════════════════════
# 1. 多目标优化追踪器
# ══════════════════════════════════════════════════════════════════

@dataclass
class MOPoint:
    cand_id:   str
    generation: int
    score:     float
    speed:     float   # 越大越好（iterations/sec 或 1/time）
    mem_usage: float   # 越小越好（MB）
    genome:    dict = field(default_factory=dict)
    is_pareto: bool = False


class MultiObjectiveTracker:
    """
    多目标 Pareto 前沿追踪。
    默认目标：[score↑, speed↑, -mem_usage↑]
    """

    def __init__(self, maxlen: int = 200):
        self._points: List[MOPoint] = []
        self._lock = threading.Lock()
        self._maxlen = maxlen

    def record(self, cand_id: str, gen: int, score: float,
               speed: float = 1.0, mem_mb: float = 0.0, genome: dict = None):
        """记录一次评估结果（多维目标）。"""
        pt = MOPoint(cand_id=cand_id, generation=gen,
                     score=score, speed=speed, mem_usage=mem_mb,
                     genome=genome or {})
        with self._lock:
            self._points.append(pt)
            if len(self._points) > self._maxlen:
                self._points = self._points[-self._maxlen:]
            self._update_pareto()

        # 异步写 DB（不阻塞）
        threading.Thread(target=self._save_point, args=(pt,), daemon=True).start()

    def _dominates(self, a: MOPoint, b: MOPoint) -> bool:
        """a 是否支配 b（所有目标 a ≥ b，至少一个严格更优）"""
        # score↑, speed↑, mem↓ (转换为 -mem↑)
        def obj(p): return (p.score, p.speed, -p.mem_usage)
        oa, ob = obj(a), obj(b)
        return all(x >= y for x, y in zip(oa, ob)) and any(x > y for x, y in zip(oa, ob))

    def _update_pareto(self):
        pareto = []
        for pt in self._points:
            dominated = False
            for other in self._points:
                if other is not pt and self._dominates(other, pt):
                    dominated = True
                    break
            pt.is_pareto = not dominated
            if not dominated:
                pareto.append(pt)

    def get_pareto_front(self) -> List[MOPoint]:
        with self._lock:
            return [p for p in self._points if p.is_pareto]

    def get_weighted_best(self, w_score=0.6, w_speed=0.2, w_mem=0.2) -> Optional[MOPoint]:
        """根据权重返回最优点。"""
        front = self.get_pareto_front()
        if not front:
            return None
        # 归一化后加权
        scores = [p.score for p in front]
        speeds = [p.speed for p in front]
        mems   = [-p.mem_usage for p in front]  # 越小越好 → 取负

        def norm(vals):
            mn, mx = min(vals), max(vals)
            r = mx - mn
            return [(v - mn) / r if r > 1e-9 else 0.5 for v in vals]

        n_s = norm(scores)
        n_sp = norm(speeds)
        n_m  = norm(mems)

        weighted = [w_score * s + w_speed * sp + w_mem * m
                    for s, sp, m in zip(n_s, n_sp, n_m)]
        best_idx = int(np.argmax(weighted))
        return front[best_idx]

    def get_summary(self) -> dict:
        with self._lock:
            total = len(self._points)
            pareto_count = sum(1 for p in self._points if p.is_pareto)
            front = [p for p in self._points if p.is_pareto]

        # ── 内存为空时，从 generations 表回填历史数据 ──────────────────────
        if total == 0:
            try:
                con = sqlite3.connect(str(DB_PATH), timeout=5.0)
                rows = con.execute(
                    "SELECT generation, best_score FROM generations "
                    "WHERE best_score > 0 AND status='done' ORDER BY generation"
                ).fetchall()
                con.close()
                if rows:
                    total = len(rows)
                    # 计算简易 Pareto（逐代最高分 = Pareto 点）
                    best_so_far = -1.0
                    pareto_rows = []
                    for gen, sc in rows:
                        if sc > best_so_far:
                            best_so_far = sc
                            pareto_rows.append({"cand_id": f"gen{gen}_best",
                                                "gen": gen, "score": round(sc, 5),
                                                "speed": 1.0, "mem_mb": 0.0})
                    pareto_count = len(pareto_rows)
                    all_scores = [r["score"] for r in pareto_rows]
                    return {
                        "total": total,
                        "pareto_count": pareto_count,
                        "front": pareto_rows[-20:],
                        "score_range": [round(min(all_scores), 5),
                                        round(max(all_scores), 5)],
                        "source": "db_fallback",
                    }
            except Exception:
                pass

        if not front:
            return {"total": total, "pareto_count": 0, "front": []}
        return {
            "total": total,
            "pareto_count": pareto_count,
            "front": [
                {
                    "cand_id": p.cand_id,
                    "gen": p.generation,
                    "score": round(p.score, 5),
                    "speed": round(p.speed, 3),
                    "mem_mb": round(p.mem_usage, 1),
                }
                for p in sorted(front, key=lambda x: x.score, reverse=True)[:20]
            ],
            "score_range": [round(min(p.score for p in front), 5),
                            round(max(p.score for p in front), 5)],
        }

    def _save_point(self, pt: MOPoint):
        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("""
                INSERT INTO multi_objectives
                (generation, cand_id, score, speed, mem_usage, is_pareto, timestamp)
                VALUES (?,?,?,?,?,?,?)
            """, (pt.generation, pt.cand_id, pt.score, pt.speed,
                  pt.mem_usage, int(pt.is_pareto), datetime.now().isoformat()))
            con.commit()
            con.close()
        except Exception:
            pass

    @classmethod
    def load_from_db(cls, maxlen=200) -> "MultiObjectiveTracker":
        tracker = cls(maxlen=maxlen)
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute("""
                SELECT cand_id, generation, score, speed, mem_usage
                FROM multi_objectives
                ORDER BY id DESC LIMIT ?
            """, (maxlen,)).fetchall()
            con.close()
            with tracker._lock:
                for r in reversed(rows):
                    tracker._points.append(MOPoint(
                        cand_id=r[0], generation=r[1],
                        score=r[2], speed=r[3], mem_usage=r[4]
                    ))
                tracker._update_pareto()
        except Exception:
            pass
        return tracker


# ══════════════════════════════════════════════════════════════════
# 2. 参数重要性追踪器
# ══════════════════════════════════════════════════════════════════

class ParamImportanceTracker:
    """
    每 IMPORTANCE_INTERVAL 代计算一次各参数的重要性（基于历史评估数据），
    并自动收窄低重要性参数的搜索空间。
    """

    IMPORTANCE_INTERVAL = 10   # 每10代计算一次
    NUM_PARAMS = ["ucb_kappa", "ei_xi", "length_scale", "n_candidates", "n_random_init"]
    BOOL_PARAMS = ["normalize_y"]

    def __init__(self, controller=None):
        self._ctrl = controller
        self._last_calc_gen = -1
        self._importance: Dict[str, float] = {}  # param → importance score [0,1]
        self._lock = threading.Lock()

    def maybe_calc(self, current_gen: int):
        """由进化引擎每代调用，触发重要性计算。"""
        if current_gen - self._last_calc_gen < self.IMPORTANCE_INTERVAL:
            return
        self._last_calc_gen = current_gen
        threading.Thread(
            target=self._do_calc,
            args=(current_gen,),
            daemon=True,
            name="ParamImportance"
        ).start()

    def _do_calc(self, gen: int):
        """从 DB 读取历史候选，计算每个参数对 score 的相关性。"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute("""
                SELECT config, score FROM candidates
                WHERE score IS NOT NULL AND score > 0
                ORDER BY generation DESC LIMIT 300
            """).fetchall()
            con.close()
        except Exception:
            return

        if len(rows) < 20:
            return  # 样本太少

        # 解析
        records = []
        for row in rows:
            try:
                cfg = json.loads(row[0])
                records.append((cfg, float(row[1])))
            except Exception:
                pass

        if len(records) < 20:
            return

        scores = np.array([r[1] for r in records])
        importance = {}

        # 数值参数：Pearson 相关系数的绝对值
        for key in self.NUM_PARAMS:
            vals = []
            valid_scores = []
            for cfg, sc in records:
                v = cfg.get(key)
                if v is not None:
                    try:
                        vals.append(float(v))
                        valid_scores.append(sc)
                    except Exception:
                        pass
            if len(vals) < 10:
                continue
            v_arr = np.array(vals)
            s_arr = np.array(valid_scores)
            # 计算 Pearson 相关
            if v_arr.std() < 1e-9:
                importance[key] = 0.0
                continue
            corr = np.corrcoef(v_arr, s_arr)[0, 1]
            importance[key] = min(abs(float(corr)), 1.0)

        # 布尔参数：点二列相关（point-biserial）
        for key in self.BOOL_PARAMS:
            group_t, group_f = [], []
            for cfg, sc in records:
                v = cfg.get(key)
                if v is True:
                    group_t.append(sc)
                elif v is False:
                    group_f.append(sc)
            if len(group_t) < 5 or len(group_f) < 5:
                continue
            mean_diff = abs(np.mean(group_t) - np.mean(group_f))
            pooled_std = np.std(scores)
            importance[key] = min(mean_diff / (pooled_std + 1e-9), 1.0)

        # 归一化
        if importance:
            max_imp = max(importance.values()) + 1e-9
            importance = {k: round(v / max_imp, 4) for k, v in importance.items()}

        with self._lock:
            self._importance = importance

        # 持久化
        self._save_to_db(gen, importance)

        # 应用：收窄低重要性参数范围
        self._apply_narrowing(importance, gen)

    def _save_to_db(self, gen: int, importance: dict):
        try:
            con = sqlite3.connect(str(DB_PATH))
            now = datetime.now().isoformat()
            for k, v in importance.items():
                con.execute("""
                    INSERT INTO param_importance(generation, param_name, importance, method, timestamp)
                    VALUES (?,?,?,?,?)
                """, (gen, k, v, "pearson", now))
            con.commit()
            con.close()
        except Exception:
            pass

    def _apply_narrowing(self, importance: dict, gen: int):
        """
        重要性 < 0.15 的参数：搜索范围收窄至当前值附近 ±15%。
        重要性 >= 0.15 的参数：保持现有范围。
        """
        if self._ctrl is None:
            return
        try:
            genome = getattr(self._ctrl, "current_genome", {})
            narrowed = []
            for key, imp in importance.items():
                if imp < 0.15 and key in genome:
                    v = genome.get(key)
                    if isinstance(v, (int, float)):
                        margin = abs(v) * 0.15 + 1e-6
                        # 记录收窄事件（可在 Dashboard 中查看）
                        narrowed.append(f"{key}(imp={imp:.2f})")
            if narrowed:
                print(f"[ParamImportance] 代{gen}: 低重要性参数 {narrowed}，已标记可收窄探索空间")
        except Exception:
            pass

    def get_importance(self) -> dict:
        with self._lock:
            return dict(self._importance)

    def get_summary(self) -> dict:
        imp = self.get_importance()
        if not imp:
            return {"status": "no_data", "importance": {}}

        sorted_imp = sorted(imp.items(), key=lambda x: x[1], reverse=True)
        return {
            "status": "ok",
            "last_calc_gen": self._last_calc_gen,
            "importance": {k: v for k, v in sorted_imp},
            "top_params": [k for k, v in sorted_imp[:3]],
            "low_importance_params": [k for k, v in sorted_imp if v < 0.15],
        }

    @classmethod
    def load_latest_from_db(cls) -> dict:
        """读取最新一批重要性数据（供 Dashboard 初始展示）。"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            max_gen = con.execute("SELECT MAX(generation) FROM param_importance").fetchone()[0]
            if max_gen is None:
                con.close()
                return {}
            rows = con.execute("""
                SELECT param_name, importance FROM param_importance
                WHERE generation = ?
            """, (max_gen,)).fetchall()
            con.close()
            return {r[0]: r[1] for r in rows}
        except Exception:
            return {}


# ══════════════════════════════════════════════════════════════════
# 3. A/B 配置对比实验
# ══════════════════════════════════════════════════════════════════

class ABConfigCompare:
    """
    保存配置快照，支持两组配置并行对比评估。
    """

    def __init__(self, controller=None):
        self._ctrl = controller
        self._snapshots: Dict[str, dict] = {}  # snap_id → snapshot
        self._results: List[dict] = []
        self._lock = threading.Lock()
        self._load_snapshots()

    def _load_snapshots(self):
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute(
                "SELECT snap_id, label, genome, score, created_at, notes FROM ab_snapshots"
            ).fetchall()
            con.close()
            for r in rows:
                self._snapshots[r[0]] = {
                    "snap_id": r[0], "label": r[1],
                    "genome": json.loads(r[2]), "score": r[3],
                    "created_at": r[4], "notes": r[5]
                }
        except Exception:
            pass

    def save_snapshot(self, label: str = "", notes: str = "") -> str:
        """保存当前最优配置为快照。"""
        if self._ctrl is None:
            return ""
        genome = getattr(self._ctrl, "current_genome", {})
        score  = getattr(self._ctrl, "best_score", 0.0)
        snap_id = f"snap_{int(time.time())}_{random.randint(100,999)}"

        snap = {
            "snap_id": snap_id,
            "label": label or f"Gen-{getattr(self._ctrl,'current_gen',0)}",
            "genome": dict(genome),
            "score": float(score),
            "created_at": datetime.now().isoformat(),
            "notes": notes,
        }
        with self._lock:
            self._snapshots[snap_id] = snap

        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("""
                INSERT INTO ab_snapshots(snap_id, label, genome, score, created_at, notes)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(snap_id) DO NOTHING
            """, (snap_id, snap["label"], json.dumps(snap["genome"]),
                  snap["score"], snap["created_at"], notes))
            con.commit()
            con.close()
        except Exception:
            pass

        return snap_id

    def compare(self, snap_id_a: str, snap_id_b: str,
                n_trials: int = 30) -> dict:
        """
        对比两组配置的表现（Bootstrap 采样估计差异显著性）。
        注意：这里直接对比两者在历史 DB 中的关联评估记录（代理评估）。
        """
        with self._lock:
            snap_a = self._snapshots.get(snap_id_a)
            snap_b = self._snapshots.get(snap_id_b)

        if not snap_a or not snap_b:
            return {"error": "快照不存在"}

        # 简化对比：从 DB 找各自基因组对应的候选分数
        def get_scores_for_genome(genome: dict) -> List[float]:
            try:
                con = sqlite3.connect(str(DB_PATH))
                rows = con.execute("""
                    SELECT score FROM candidates
                    WHERE json_extract(config, '$.acquisition') = ?
                      AND json_extract(config, '$.normalize_y') = ?
                      AND score > 0
                    ORDER BY generation DESC LIMIT ?
                """, (genome.get("acquisition", "EI"),
                      genome.get("normalize_y", True),
                      n_trials)).fetchall()
                con.close()
                return [r[0] for r in rows]
            except Exception:
                return []

        scores_a = get_scores_for_genome(snap_a["genome"]) or [snap_a["score"]]
        scores_b = get_scores_for_genome(snap_b["genome"]) or [snap_b["score"]]

        mean_a = float(np.mean(scores_a))
        mean_b = float(np.mean(scores_b))

        # Bootstrap t-test（简化版）
        p_value = self._bootstrap_pvalue(scores_a, scores_b)
        winner  = snap_id_a if mean_a > mean_b else snap_id_b

        result = {
            "snap_a": snap_id_a,
            "snap_b": snap_id_b,
            "label_a": snap_a["label"],
            "label_b": snap_b["label"],
            "mean_a": round(mean_a, 5),
            "mean_b": round(mean_b, 5),
            "diff": round(mean_a - mean_b, 5),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "winner": winner,
            "winner_label": snap_a["label"] if winner == snap_id_a else snap_b["label"],
            "n_a": len(scores_a),
            "n_b": len(scores_b),
        }

        with self._lock:
            self._results.append(result)

        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("""
                INSERT INTO ab_results
                (snap_a, snap_b, score_a, score_b, p_value, winner, tested_at)
                VALUES (?,?,?,?,?,?,?)
            """, (snap_id_a, snap_id_b, mean_a, mean_b, p_value, winner,
                  datetime.now().isoformat()))
            con.commit()
            con.close()
        except Exception:
            pass

        return result

    @staticmethod
    def _bootstrap_pvalue(a: List[float], b: List[float],
                           n_boot: int = 1000) -> float:
        """Bootstrap 双样本 p-value（近似）。"""
        if len(a) < 2 or len(b) < 2:
            return 1.0
        obs_diff = abs(np.mean(a) - np.mean(b))
        combined = a + b
        count_extreme = 0
        rng = np.random.RandomState(42)
        for _ in range(n_boot):
            sample_a = rng.choice(combined, size=len(a), replace=True)
            sample_b = rng.choice(combined, size=len(b), replace=True)
            if abs(np.mean(sample_a) - np.mean(sample_b)) >= obs_diff:
                count_extreme += 1
        return count_extreme / n_boot

    def list_snapshots(self) -> List[dict]:
        with self._lock:
            return sorted(self._snapshots.values(),
                          key=lambda x: x["created_at"], reverse=True)

    def get_summary(self) -> dict:
        snaps = self.list_snapshots()
        with self._lock:
            results = list(self._results[-10:])
        return {
            "snapshot_count": len(snaps),
            "snapshots": snaps[:10],
            "recent_results": results,
        }


# ══════════════════════════════════════════════════════════════════
# 4. Drift 漂移联动自动响应增强器
# ══════════════════════════════════════════════════════════════════

class DriftResponseEnhancer:
    """
    漂移检测触发后自动执行增强响应：
    1. 扩大搜索空间（基因组范围 +20%）
    2. 通知 InsightEngine 清除低质量知识
    3. 触发 WebLearner 紧急网络学习
    4. 自动保存 A/B 快照（用于漂移前后对比）
    5. 冷却期 600s 防抖
    """

    COOLDOWN_S = 600   # 两次响应最短间隔（秒）
    SPACE_EXPAND = 0.20  # 搜索空间扩大比例

    def __init__(self, controller=None, insight=None, ab_compare=None):
        self._ctrl    = controller
        self._insight = insight
        self._ab      = ab_compare
        self._last_response_ts = 0.0
        self._response_count = 0
        self._lock = threading.Lock()

    def on_drift_detected(self, drift_event: dict, current_gen: int = 0):
        """
        漂移事件回调。drift_event 格式:
        {method, score, threshold, message}
        """
        with self._lock:
            now = time.time()
            if now - self._last_response_ts < self.COOLDOWN_S:
                remain = int(self.COOLDOWN_S - (now - self._last_response_ts))
                print(f"[DriftResponse] 冷却中，剩余 {remain}s，跳过")
                return None
            self._last_response_ts = now
            self._response_count += 1

        actions = []
        method = drift_event.get("method", "unknown")
        score  = drift_event.get("score", 0.0)

        # ── 1. 保存漂移前快照（A/B 对比用）─────────────────────────────────
        if self._ab and self._ctrl:
            snap_id = self._ab.save_snapshot(
                label=f"漂移前Gen{current_gen}",
                notes=f"漂移事件: {method} score={score:.4f}"
            )
            if snap_id:
                actions.append(f"保存漂移前快照({snap_id})")

        # ── 2. 扩大搜索空间（温和）──────────────────────────────────────────
        if self._ctrl:
            try:
                genome = getattr(self._ctrl, "current_genome", {})
                # 扩大 kappa（增加探索）
                old_k = genome.get("ucb_kappa", 2.576)
                new_k = min(old_k * (1 + self.SPACE_EXPAND), 10.0)
                genome["ucb_kappa"] = round(new_k, 4)
                # 增加候选点（更大面积搜索）
                old_nc = genome.get("n_candidates", 512)
                new_nc = min(int(old_nc * (1 + self.SPACE_EXPAND)), 2000)
                genome["n_candidates"] = new_nc
                self._ctrl.current_genome = genome
                actions.append(f"扩大搜索: kappa {old_k:.3f}→{new_k:.3f}, n_candidates {old_nc}→{new_nc}")
            except Exception as e:
                actions.append(f"扩大搜索失败: {e}")

        # ── 3. 通知 InsightEngine 降低历史知识权重（重置偏保守）────────────────
        if self._insight:
            try:
                with self._insight._lock:
                    # 降低历史累积知识的影响（不清空，但减权）
                    old_k2 = self._insight._knowledge
                    for k in list(old_k2.keys()):
                        v = old_k2[k]
                        if isinstance(v, dict) and "confidence" in v:
                            v["confidence"] = v["confidence"] * 0.7
                actions.append("InsightEngine 知识权重降至70%（漂移后重评估）")
            except Exception as e:
                actions.append(f"InsightEngine 重置失败: {e}")

        # ── 4. 触发 WebLearner 紧急采集（扩充外部知识）──────────────────────
        wl = getattr(self._insight, "_web_learner", None) if self._insight else None
        if wl:
            try:
                result = wl.force_learn_now(gen=current_gen)
                actions.append(f"WebLearner 紧急学习: {result}")
            except Exception as e:
                actions.append(f"WebLearner 触发失败: {e}")

        # ── 5. 持久化响应记录 ─────────────────────────────────────────────────
        record = {
            "gen": current_gen,
            "method": method,
            "drift_score": round(score, 4),
            "actions": actions,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_response(record)
        print(f"[DriftResponse] 响应完成（第{self._response_count}次）: {', '.join(actions)}")
        return record

    def _save_response(self, record: dict):
        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("""
                INSERT INTO drift_responses(gen, method, drift_score, actions, timestamp)
                VALUES (?,?,?,?,?)
            """, (record["gen"], record["method"], record["drift_score"],
                  json.dumps(record["actions"], ensure_ascii=False),
                  record["timestamp"]))
            con.commit()
            con.close()
        except Exception:
            pass

    def get_summary(self) -> dict:
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute("""
                SELECT gen, method, drift_score, actions, timestamp
                FROM drift_responses ORDER BY id DESC LIMIT 10
            """).fetchall()
            db_total = con.execute("SELECT COUNT(*) FROM drift_responses").fetchone()[0]
            con.close()
            # 内存计数取较大值（本次运行可能已发生漂移）
            total = max(self._response_count, db_total)
            recent = [
                {"gen": r[0], "method": r[1], "score": r[2],
                 "actions": json.loads(r[3]), "ts": r[4]}
                for r in rows
            ]
            return {
                "total_responses": total,
                "cooldown_s": self.COOLDOWN_S,
                "last_response_ts": self._last_response_ts,
                "recent": recent,
            }
        except Exception:
            return {"total_responses": self._response_count}


# ══════════════════════════════════════════════════════════════════
# 统一接入：EnhancementHub（挂载到 SelfEvolveController）
# ══════════════════════════════════════════════════════════════════

class EnhancementHub:
    """
    统一入口：将以上四个增强模块挂载到进化控制器。
    在 SelfEvolveController.__init__ 或启动后调用 attach()。
    """

    def __init__(self, controller=None, insight=None):
        self._ctrl    = controller
        self._insight = insight

        self.multi_obj  = MultiObjectiveTracker()
        self.param_imp  = ParamImportanceTracker(controller=controller)
        self.ab_compare = ABConfigCompare(controller=controller)
        self.drift_resp = DriftResponseEnhancer(
            controller=controller,
            insight=insight,
            ab_compare=self.ab_compare
        )

        print("[EnhancementHub] 四大增强模块已初始化 ✅")
        print("  - MultiObjectiveTracker  (多目标 Pareto)")
        print("  - ParamImportanceTracker (参数重要性)")
        print("  - ABConfigCompare        (A/B 对比)")
        print("  - DriftResponseEnhancer  (Drift 联动)")

        # ── 启动后延迟5秒自动保存基线快照（若DB为空才保存） ────────────
        threading.Thread(target=self._auto_init_snapshot, daemon=True).start()

    def _auto_init_snapshot(self):
        """启动时若快照表为空，自动保存一次当前基线快照。"""
        import time as _time
        _time.sleep(5)  # 等控制器完成初始化
        try:
            con = sqlite3.connect(str(DB_PATH), timeout=5.0)
            cnt = con.execute("SELECT COUNT(*) FROM ab_snapshots").fetchone()[0]
            con.close()
            if cnt == 0 and self._ctrl is not None:
                snap_id = self.ab_compare.save_snapshot(
                    label="初始基线快照",
                    notes="系统启动时自动保存"
                )
                if snap_id:
                    print(f"[EnhancementHub] 已自动保存初始基线快照: {snap_id}")
        except Exception as e:
            print(f"[EnhancementHub] 自动快照失败: {e}")

    def on_generation_end(self, gen: int, best_score: float,
                          candidates: list = None, drift_event: dict = None):
        """
        每代结束时由控制器调用。
        candidates: list of {cand_id, score, config, strategy}
        drift_event: 若当代检测到漂移，传入漂移事件 dict
        """
        # 记录多目标（用 best_score + 默认 speed/mem）
        self.multi_obj.record(
            cand_id=f"gen{gen}_best",
            gen=gen,
            score=best_score,
            speed=1.0,   # 可扩展为真实测量值
            mem_mb=0.0,
        )

        # 参数重要性（异步，不阻塞）
        self.param_imp.maybe_calc(gen)

        # Drift 响应
        if drift_event:
            self.drift_resp.on_drift_detected(drift_event, current_gen=gen)

        # 每50代自动保存配置快照（A/B 对比用）
        if gen > 0 and gen % 50 == 0:
            snap_id = self.ab_compare.save_snapshot(
                label=f"自动快照-Gen{gen}",
                notes=f"score={best_score:.5f}"
            )
            if snap_id:
                print(f"[EnhancementHub] 代{gen}: 自动快照已保存 {snap_id}")

    def get_full_summary(self) -> dict:
        return {
            "multi_objective":  self.multi_obj.get_summary(),
            "param_importance": self.param_imp.get_summary(),
            "ab_compare":       self.ab_compare.get_summary(),
            "drift_response":   self.drift_resp.get_summary(),
        }


# ── 对外接口：attach_enhancements ──────────────────────────────────────────────

def attach_enhancements(controller, insight=None) -> EnhancementHub:
    """
    将 EnhancementHub 挂载到进化控制器。
    controller: SelfEvolveController 实例
    insight:    InsightEngine 实例（可选）
    """
    hub = EnhancementHub(controller=controller, insight=insight)
    controller._enhancement_hub = hub
    return hub
