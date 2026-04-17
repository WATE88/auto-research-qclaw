"""
AutoResearch InsightEngine — 搜索 & 学习总结技能
=================================================
每 LEARN_INTERVAL 代触发一次「搜索+总结+应用」循环：

  1. [搜索]   扫描历史候选数据库，按多个维度聚类分析
  2. [总结]   提炼「高分区域」的参数规律，识别哪些参数组合容易出好成绩
  3. [应用]   动态调整：
               ① 策略权重（强化表现好的策略）
               ② random_mutate 的搜索中心（往高分区域偏移）
               ③ 注入「知识种子」基因组（直接基于归纳出的规律）
  4. [记忆]   把总结写入 evolution_monitor.db 的 insight_log 表，
               历史总结可被下次学习参考（迁移学习）

作者: AutoResearch WorkBuddy集成（2026-03-25）
"""

import sqlite3, json, math, copy, threading
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "evolution_monitor.db"

# ── 初始化 insight_log 表 ─────────────────────────────────────────────────────

def _ensure_insight_table():
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("""
            CREATE TABLE IF NOT EXISTS insight_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                generation  INTEGER,
                timestamp   TEXT,
                summary     TEXT,      -- JSON: 本次总结摘要
                applied     TEXT       -- JSON: 应用了哪些调整
            )
        """)
        con.commit()
        con.close()
    except Exception:
        pass


# ── 核心：InsightEngine ────────────────────────────────────────────────────────

class InsightEngine:
    """
    搜索 & 学习总结引擎
    挂载到 SelfEvolveController 后，每 LEARN_INTERVAL 代自动运行一次。
    """

    LEARN_INTERVAL    = 5     # 每N代触发一次学习
    MIN_SAMPLES       = 30    # 至少N个样本才开始学习
    TOP_RATIO         = 0.15  # 取前15%的高分候选作为「正样本」
    WEIGHT_BOOST      = 1.35  # 高分策略权重放大倍数
    WEIGHT_DECAY      = 0.85  # 低分策略权重衰减倍数
    PARAM_SHIFT_RATE  = 0.35  # 搜索中心向高分区域偏移的比例

    def __init__(self, controller):
        self._ctrl = controller
        self._last_learn_gen = -1
        self._knowledge: dict = {}   # 持久化的知识库（参数→推荐区间）
        self._lock = threading.Lock()
        _ensure_insight_table()
        self._load_knowledge()        # 恢复历史知识

        # ── 网络学习技能（WebLearner）─────────────────────────────────────────
        try:
            from autoresearch_web_learner import attach_web_learner
            self._web_learner = attach_web_learner(self)
            if self._web_learner:
                self._log("WebLearner（网络学习）已挂载 ✅", "INFO")
        except Exception as _wl_err:
            self._web_learner = None
            self._log(f"WebLearner 挂载失败（不影响主流程）: {_wl_err}", "WARN")

    # ── 日志 ──────────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "INSIGHT"):
        try:
            self._ctrl.log(f"[InsightEngine] {msg}", level)
        except Exception:
            print(f"[InsightEngine][{level}] {msg}")

    # ── 持久化知识 ────────────────────────────────────────────────────────────

    def _load_knowledge(self):
        """从 insight_log 最近一条记录恢复知识库"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            row = con.execute(
                "SELECT summary FROM insight_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            if row:
                data = json.loads(row[0])
                self._knowledge = data.get("knowledge", {})
                self._log(f"历史知识已恢复，共 {len(self._knowledge)} 条规律")
        except Exception:
            pass

    def _save_insight(self, gen: int, summary: dict, applied: dict):
        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute(
                "INSERT INTO insight_log(generation,timestamp,summary,applied) VALUES(?,?,?,?)",
                (gen, datetime.now().isoformat(), json.dumps(summary, ensure_ascii=False),
                 json.dumps(applied, ensure_ascii=False))
            )
            con.commit()
            con.close()
        except Exception as e:
            self._log(f"写入 insight_log 失败: {e}", "WARN")

    # ── 主入口：每代结束后由控制器调用 ──────────────────────────────────────────

    def learn_and_apply(self, current_gen: int) -> bool:
        """
        检查是否需要触发本轮学习；如需要则执行完整的「搜索→总结→应用」流程。
        返回 True 表示本轮执行了学习。
        """
        # ── 网络学习（异步后台，不阻塞本轮进化）────────────────────────────────
        if getattr(self, "_web_learner", None) is not None:
            try:
                self._web_learner.maybe_web_learn(current_gen)
                # 后验评分追踪：每代记录当前分数，用于评估网络知识有效性
                cur_score = getattr(self._ctrl, "best_score", 0.0)
                self._web_learner.record_post_apply_score(current_gen, cur_score)
            except Exception as _wle:
                self._log(f"WebLearner 触发失败: {_wle}", "DEBUG")

        if current_gen - self._last_learn_gen < self.LEARN_INTERVAL:
            return False

        self._log(f"第 {current_gen} 代触发学习总结...")
        try:
            candidates = self._search_candidates()
            if len(candidates) < self.MIN_SAMPLES:
                self._log(f"样本不足（{len(candidates)}/{self.MIN_SAMPLES}），跳过本次学习")
                return False

            summary = self._summarize(candidates, current_gen)
            applied = self._apply(summary, current_gen)

            self._save_insight(current_gen, summary, applied)
            self._last_learn_gen = current_gen

            self._log(
                f"✅ 学习完成  "
                f"高分区域={summary.get('top_region_label','?')}  "
                f"策略调整={applied.get('weight_adjustments',0)}条  "
                f"注入知识种子={applied.get('seeds_injected',0)}个"
            )
            return True
        except Exception as e:
            self._log(f"学习过程出错（不影响进化）: {e}", "WARN")
            import traceback; traceback.print_exc()
            return False

    # ── 步骤1：搜索历史候选 ────────────────────────────────────────────────────

    def _search_candidates(self) -> list:
        """从 SQLite 读取所有有效候选，返回 [{genome, score, strategy}]"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute("""
                SELECT config, score, strategy_name
                FROM candidates
                WHERE score > 0
                ORDER BY score DESC
            """).fetchall()
            con.close()
        except Exception:
            return []

        result = []
        for row in rows:
            try:
                genome = json.loads(row[0])
                result.append({
                    "genome": genome,
                    "score": float(row[1]),
                    "strategy": row[2] or "unknown"
                })
            except Exception:
                pass
        return result

    # ── 步骤2：总结规律 ────────────────────────────────────────────────────────

    def _summarize(self, candidates: list, gen: int) -> dict:
        """
        多维度分析高分候选 vs 低分候选，提炼规律。
        返回结构化的 summary 字典。
        """
        scores = np.array([c["score"] for c in candidates])
        n_top  = max(5, int(len(candidates) * self.TOP_RATIO))
        sorted_cands = sorted(candidates, key=lambda x: x["score"], reverse=True)
        top_cands    = sorted_cands[:n_top]
        low_cands    = sorted_cands[-n_top:]

        # ── A. 数值参数统计：高分区域 vs 低分区域 ─────────────────────────────
        num_keys = ["ucb_kappa", "ei_xi", "length_scale", "n_candidates", "n_random_init"]
        param_stats = {}
        for key in num_keys:
            top_vals = [c["genome"].get(key, 0) for c in top_cands if key in c["genome"]]
            low_vals = [c["genome"].get(key, 0) for c in low_cands if key in c["genome"]]
            if not top_vals:
                continue
            top_arr = np.array(top_vals, dtype=float)
            param_stats[key] = {
                "top_mean":   float(np.mean(top_arr)),
                "top_std":    float(np.std(top_arr)),
                "top_min":    float(np.min(top_arr)),
                "top_max":    float(np.max(top_arr)),
                "low_mean":   float(np.mean(low_vals)) if low_vals else 0.0,
                "direction":  "high" if np.mean(top_arr) > np.mean(low_vals) else "low"
            }

        # ── B. 离散参数统计 ────────────────────────────────────────────────────
        # acquisition
        acq_top   = {}
        for c in top_cands:
            a = c["genome"].get("acquisition", "?")
            acq_top[a] = acq_top.get(a, 0) + 1
        best_acq = max(acq_top, key=acq_top.get) if acq_top else "EI"

        # normalize_y
        norm_top = sum(1 for c in top_cands if c["genome"].get("normalize_y", False))
        normalize_preferred = norm_top >= len(top_cands) * 0.5

        # ── C. 策略胜率统计 ────────────────────────────────────────────────────
        strat_wins   = {}
        strat_totals = {}
        for c in candidates:
            s = c["strategy"]
            strat_totals[s] = strat_totals.get(s, 0) + 1
        for c in top_cands:
            s = c["strategy"]
            strat_wins[s] = strat_wins.get(s, 0) + 1

        strat_winrate = {}
        for s, total in strat_totals.items():
            wins = strat_wins.get(s, 0)
            strat_winrate[s] = wins / max(total, 1)

        best_strategies = sorted(strat_winrate, key=strat_winrate.get, reverse=True)[:3]

        # ── D. 规律标签 ───────────────────────────────────────────────────────
        labels = []
        if normalize_preferred:
            labels.append("normalize_y=True更优")
        kappa_stat = param_stats.get("ucb_kappa", {})
        if kappa_stat:
            if kappa_stat["top_mean"] < 2.0:
                labels.append("低kappa更保守探索")
            elif kappa_stat["top_mean"] > 5.0:
                labels.append("高kappa更激进探索")
        cand_stat = param_stats.get("n_candidates", {})
        if cand_stat and cand_stat["top_mean"] > 600:
            labels.append("大候选池更精准")
        top_region_label = " | ".join(labels) if labels else "尚未发现明显规律"

        # ── E. 更新知识库 ──────────────────────────────────────────────────────
        knowledge = {
            "best_acquisition":     best_acq,
            "normalize_preferred":  normalize_preferred,
            "best_strategies":      best_strategies,
            "param_top_ranges":     param_stats,
            "top_score_threshold":  float(np.percentile(scores, 85)),
            "updated_gen":          gen,
        }
        with self._lock:
            self._knowledge = knowledge

        summary = {
            "generation":         gen,
            "total_candidates":   len(candidates),
            "n_top":              n_top,
            "top_score":          float(top_cands[0]["score"]) if top_cands else 0.0,
            "top_region_label":   top_region_label,
            "best_acquisition":   best_acq,
            "normalize_preferred":normalize_preferred,
            "best_strategies":    best_strategies,
            "strategy_winrates":  {s: round(v, 3) for s, v in strat_winrate.items()},
            "param_stats":        param_stats,
            "knowledge":          knowledge,
        }
        return summary

    # ── 步骤3：应用知识反哺进化 ─────────────────────────────────────────────────

    def _apply(self, summary: dict, gen: int) -> dict:
        """
        根据总结结果动态调整控制器参数。
        """
        ctrl  = self._ctrl
        applied = {"weight_adjustments": 0, "seeds_injected": 0, "param_center_shift": []}

        # ── A. 策略权重动态调整 ──────────────────────────────────────────────
        winrates = summary.get("strategy_winrates", {})
        median_wr = np.median(list(winrates.values())) if winrates else 0.0

        for strat, wr in winrates.items():
            if strat not in ctrl._strategy_scores:
                continue
            if wr > median_wr * 1.5:   # 胜率显著高于中位数：提升权重
                ctrl._strategy_scores[strat] *= self.WEIGHT_BOOST
                applied["weight_adjustments"] += 1
            elif wr < median_wr * 0.5 and wr < 0.05:  # 胜率极低：衰减权重
                ctrl._strategy_scores[strat] *= self.WEIGHT_DECAY
                applied["weight_adjustments"] += 1

        # ── B. 搜索中心偏移：把 current_genome 向高分区域靠拢 ───────────────
        param_stats = summary.get("param_stats", {})
        genome = ctrl.current_genome

        for key, stat in param_stats.items():
            if key not in genome:
                continue
            current_val = genome[key]
            target_val  = stat["top_mean"]
            shift       = (target_val - current_val) * self.PARAM_SHIFT_RATE

            # 应用偏移（数值参数）
            if isinstance(current_val, float):
                new_val = current_val + shift
                # 保持在合理范围内
                bounds = {
                    "ucb_kappa":    (0.3, 12.0),
                    "ei_xi":        (1e-5, 0.2),
                    "length_scale": (0.05, 8.0),
                }
                if key in bounds:
                    lo, hi = bounds[key]
                    new_val = max(lo, min(hi, new_val))
                genome[key] = round(new_val, 6)
                applied["param_center_shift"].append(
                    f"{key}: {current_val:.4f}→{new_val:.4f}"
                )
            elif isinstance(current_val, int) and key == "n_candidates":
                new_val = int(current_val + shift)
                new_val = max(32, min(1500, new_val))
                genome[key] = new_val
                applied["param_center_shift"].append(f"n_candidates: {current_val}→{new_val}")

        # 更新 normalize_y
        if summary.get("normalize_preferred", False):
            genome["normalize_y"] = True
            applied["param_center_shift"].append("normalize_y → True")

        # 更新采集函数（向高分区域的最佳 acquisition 偏移）
        best_acq = summary.get("best_acquisition")
        if best_acq and ctrl.rng.rand() < 0.4:   # 40% 概率切换（保持探索多样性）
            genome["acquisition"] = best_acq
            applied["param_center_shift"].append(f"acquisition → {best_acq}")

        ctrl.current_genome = genome

        # ── C. 注入「知识种子」基因组（直接用学到的最优区间构造候选）────────
        knowledge = summary.get("knowledge", {})
        param_top_ranges = knowledge.get("param_top_ranges", {})
        if param_top_ranges:
            seed_genome = copy.deepcopy(genome)
            # 将数值参数设为高分区域的均值
            for key, stat in param_top_ranges.items():
                if key in seed_genome:
                    if isinstance(seed_genome[key], float):
                        seed_genome[key] = round(stat["top_mean"], 6)
                    elif isinstance(seed_genome[key], int):
                        seed_genome[key] = int(stat["top_mean"])
            seed_genome["normalize_y"] = knowledge.get("normalize_preferred", True)
            seed_genome["acquisition"] = knowledge.get("best_acquisition", "EI")

            # 把知识种子注入精英库（下一代生成候选时会被交叉引用）
            if hasattr(ctrl, "_elite_pool"):
                # 给知识种子一个偏高的虚拟分数（不超过历史最优）
                seed_score = min(ctrl.best_score * 0.98, summary["top_score"] * 0.99)
                ctrl._elite_pool.append((seed_score, seed_genome))
                ctrl._elite_pool.sort(key=lambda x: x[0], reverse=True)
                ctrl._elite_pool = ctrl._elite_pool[:6]  # 保持精英库大小
                applied["seeds_injected"] += 1

        # ── D. 记录日志摘要 ───────────────────────────────────────────────────
        self._log(
            f"应用完成 | "
            f"参数偏移: {', '.join(applied['param_center_shift'][:3])}{'...' if len(applied['param_center_shift'])>3 else ''} | "
            f"高分策略: {summary.get('best_strategies', [])[:2]}"
        )

        return applied


# ── 便捷函数：让控制器懒挂载 ─────────────────────────────────────────────────────

def attach_insight_engine(controller) -> Optional["InsightEngine"]:
    """在 SelfEvolveController.__init__ 末尾调用，安全挂载 InsightEngine。"""
    try:
        engine = InsightEngine(controller)
        controller._insight_engine = engine
        return engine
    except Exception as e:
        print(f"[InsightEngine] 挂载失败（不影响主流程）: {e}")
        controller._insight_engine = None
        return None
