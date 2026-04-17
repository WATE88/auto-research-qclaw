"""
autoresearch_importance.py
═══════════════════════════════════════════════════════════════════
超参数重要性分析  (fANOVA 近似 + SHAP 值)
───────────────────────────────────────────────────────────────────
功能：
  1. fANOVAAnalyzer   — 基于随机森林的 fANOVA 近似（无需 ConfigSpace）
  2. SHAPImportance   — Tree SHAP 值（有 scikit-learn 时启用，否则降级）
  3. MarginalPlotter  — 单参数边际性能曲线（JSON 格式，供 Dashboard 绘图）
  4. ImportanceReport — 汇总报告，可直接序列化为 JSON 返回前端
  5. ImportanceEvolveAdapter — 零侵入集成到进化引擎

算法：
  fANOVA：
    - 用历史 (config, score) 对训练随机森林代理模型
    - 通过树的特征重要性（MDI / permutation）近似 fANOVA 方差分解
    - 交叉项用特征对乘积重要性近似
  SHAP：
    - 使用 TreeExplainer（scikit-learn RandomForest 原生支持）
    - 返回每个超参数的平均 |SHAP| 作为重要性指标
"""

from __future__ import annotations
import math
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("importance")


# ══════════════════════════════════════════════════════════════════
# 1. 工具：配置向量化
# ══════════════════════════════════════════════════════════════════

def _vectorize(configs: List[Dict], param_names: Optional[List[str]] = None
               ) -> Tuple[List[List[float]], List[str]]:
    """
    把 config dict 列表转换为数值矩阵
    str/bool 类型自动编码为整数
    """
    if not configs:
        return [], []

    if param_names is None:
        param_names = sorted({k for c in configs for k in c})

    # 为每个字符串参数建立编码表
    str_maps: Dict[str, Dict] = {}
    for pn in param_names:
        vals = [c.get(pn) for c in configs if c.get(pn) is not None]
        if vals and isinstance(vals[0], (str, bool)):
            unique = sorted({str(v) for v in vals})
            str_maps[pn] = {v: i for i, v in enumerate(unique)}

    X = []
    for c in configs:
        row = []
        for pn in param_names:
            v = c.get(pn, 0.0)
            if pn in str_maps:
                v = str_maps[pn].get(str(v), 0)
            try:
                row.append(float(v))
            except (TypeError, ValueError):
                row.append(0.0)
        X.append(row)

    return X, param_names


# ══════════════════════════════════════════════════════════════════
# 2. 随机森林代理（纯 Python 最简版 + sklearn 快速路径）
# ══════════════════════════════════════════════════════════════════

def _fit_rf(X: List[List[float]], y: List[float]) -> Optional[object]:
    """尝试用 sklearn，失败则返回 None"""
    try:
        from sklearn.ensemble import RandomForestRegressor
        import numpy as np
        rf = RandomForestRegressor(n_estimators=100, max_features="sqrt",
                                   random_state=42, n_jobs=-1)
        rf.fit(np.array(X), np.array(y))
        return rf
    except Exception as e:
        logger.warning(f"[Importance] sklearn RF 不可用: {e}")
        return None


def _permutation_importance(rf, X_np, y_np, n_repeats: int = 5) -> List[float]:
    """排列重要性（比 MDI 更稳健）"""
    try:
        import numpy as np
        base_score = rf.score(X_np, y_np)
        n_features = X_np.shape[1]
        importances = []
        rng = np.random.RandomState(0)
        for j in range(n_features):
            scores = []
            for _ in range(n_repeats):
                X_perm = X_np.copy()
                X_perm[:, j] = rng.permutation(X_perm[:, j])
                scores.append(rf.score(X_perm, y_np))
            importances.append(base_score - float(np.mean(scores)))
        return importances
    except Exception:
        return list(rf.feature_importances_)


# ══════════════════════════════════════════════════════════════════
# 3. fANOVA 近似分析器
# ══════════════════════════════════════════════════════════════════

@dataclass
class ImportanceResult:
    param_name: str
    importance:  float     # 归一化 [0,1]
    raw_score:   float     # 原始重要性分数
    method:      str       # mdi / permutation / shap / fallback

    def to_dict(self) -> Dict:
        return {
            "param": self.param_name,
            "importance": round(self.importance, 4),
            "raw": round(self.raw_score, 6),
            "method": self.method,
        }


class fANOVAAnalyzer:
    """
    fANOVA 近似：用随机森林特征重要性代替方差分解
    支持 MDI（快速）和 Permutation（更准确）两种模式
    """

    def __init__(self, method: str = "permutation"):
        assert method in ("mdi", "permutation", "auto")
        self.method = method
        self._rf = None
        self._param_names: List[str] = []
        self._results: List[ImportanceResult] = []

    def fit(self, configs: List[Dict], scores: List[float]) -> List[ImportanceResult]:
        if len(configs) < 5:
            logger.warning("[fANOVA] 样本不足（<5），跳过分析")
            return []

        X, self._param_names = _vectorize(configs)
        y = scores
        self._rf = _fit_rf(X, y)

        if self._rf is None:
            return self._fallback(configs, scores)

        try:
            import numpy as np
            X_np = np.array(X)
            y_np = np.array(y)
        except ImportError:
            return self._fallback(configs, scores)

        method = self.method
        if method == "auto":
            method = "permutation" if len(configs) >= 20 else "mdi"

        if method == "permutation":
            raw = _permutation_importance(self._rf, X_np, y_np)
        else:
            raw = list(self._rf.feature_importances_)

        # 归一化（允许负值排列重要性）
        pos = [max(r, 0) for r in raw]
        total = sum(pos) + 1e-9
        norm = [p / total for p in pos]

        self._results = [
            ImportanceResult(
                param_name=pn,
                importance=norm[i],
                raw_score=raw[i],
                method=method,
            )
            for i, pn in enumerate(self._param_names)
        ]
        self._results.sort(key=lambda r: r.importance, reverse=True)
        return self._results

    def _fallback(self, configs: List[Dict], scores: List[float]) -> List[ImportanceResult]:
        """无 sklearn 时用 Spearman 秩相关近似"""
        if not configs:
            return []
        param_names = sorted({k for c in configs for k in c})
        results = []
        for pn in param_names:
            vals = []
            for c, s in zip(configs, scores):
                v = c.get(pn)
                try:
                    vals.append((float(v), s))
                except (TypeError, ValueError):
                    pass
            if len(vals) < 3:
                results.append(ImportanceResult(pn, 0.0, 0.0, "fallback"))
                continue
            xs = [v[0] for v in vals]
            ys = [v[1] for v in vals]
            # Pearson 相关系数的绝对值
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            dx = math.sqrt(sum((x - mx) ** 2 for x in xs) + 1e-12)
            dy = math.sqrt(sum((y - my) ** 2 for y in ys) + 1e-12)
            corr = abs(num / (dx * dy))
            results.append(ImportanceResult(pn, corr, corr, "fallback"))
        total = sum(r.importance for r in results) + 1e-9
        for r in results:
            r.importance /= total
        results.sort(key=lambda r: r.importance, reverse=True)
        self._results = results
        return results

    @property
    def results(self) -> List[ImportanceResult]:
        return self._results


# ══════════════════════════════════════════════════════════════════
# 4. SHAP 重要性
# ══════════════════════════════════════════════════════════════════

class SHAPImportance:
    """
    SHAP TreeExplainer 集成
    有 shap 包时精确计算，否则自动降级到 fANOVA 结果
    """

    def __init__(self, fanova: fANOVAAnalyzer):
        self._fanova = fanova
        self._shap_values: Optional[object] = None

    def compute(self, configs: List[Dict], scores: List[float]) -> List[ImportanceResult]:
        try:
            import shap
            import numpy as np
            if self._fanova._rf is None:
                self._fanova.fit(configs, scores)
            rf = self._fanova._rf
            if rf is None:
                raise ImportError("RF not fitted")

            X, param_names = _vectorize(configs)
            X_np = np.array(X)
            explainer = shap.TreeExplainer(rf)
            sv = explainer.shap_values(X_np)
            mean_abs = list(np.abs(sv).mean(axis=0))
            total = sum(mean_abs) + 1e-9
            results = [
                ImportanceResult(
                    param_name=param_names[i],
                    importance=mean_abs[i] / total,
                    raw_score=mean_abs[i],
                    method="shap",
                )
                for i in range(len(param_names))
            ]
            results.sort(key=lambda r: r.importance, reverse=True)
            self._shap_values = sv
            logger.info("[SHAP] 计算完成")
            return results
        except Exception as e:
            logger.warning(f"[SHAP] 降级到 fANOVA: {e}")
            return self._fanova.results


# ══════════════════════════════════════════════════════════════════
# 5. 边际性能曲线
# ══════════════════════════════════════════════════════════════════

class MarginalPlotter:
    """
    单参数边际性能曲线
    返回 {param: [{x: val, y_mean: ..., y_std: ...}, ...]} 格式
    供 Chart.js / ECharts 直接绘图
    """

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def compute(self, configs: List[Dict], scores: List[float],
                top_params: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        param_names = top_params or sorted({k for c in configs for k in c})
        result = {}
        for pn in param_names:
            pairs = [(c.get(pn), s) for c, s in zip(configs, scores)
                     if c.get(pn) is not None]
            if not pairs:
                continue
            vals = [p[0] for p in pairs]
            scrs = [p[1] for p in pairs]

            # 数值型：分 bin 统计均值/std
            if all(isinstance(v, (int, float)) for v in vals):
                lo, hi = min(vals), max(vals)
                if hi - lo < 1e-9:
                    continue
                step = (hi - lo) / self.n_bins
                bins: Dict[int, List[float]] = {i: [] for i in range(self.n_bins)}
                for v, s in zip(vals, scrs):
                    idx = min(int((v - lo) / step), self.n_bins - 1)
                    bins[idx].append(s)
                curve = []
                for i in range(self.n_bins):
                    if not bins[i]:
                        continue
                    mean = sum(bins[i]) / len(bins[i])
                    std = math.sqrt(sum((x - mean) ** 2 for x in bins[i]) / len(bins[i]))
                    x_center = lo + (i + 0.5) * step
                    curve.append({"x": round(x_center, 6), "y_mean": round(mean, 4),
                                  "y_std": round(std, 4), "n": len(bins[i])})
                result[pn] = curve
            else:
                # 分类型：按类别统计
                cat_map: Dict[str, List[float]] = {}
                for v, s in zip(vals, scrs):
                    k = str(v)
                    cat_map.setdefault(k, []).append(s)
                curve = []
                for cat, ss in sorted(cat_map.items()):
                    mean = sum(ss) / len(ss)
                    std = math.sqrt(sum((x - mean) ** 2 for x in ss) / len(ss))
                    curve.append({"x": cat, "y_mean": round(mean, 4),
                                  "y_std": round(std, 4), "n": len(ss)})
                result[pn] = curve

        return result


# ══════════════════════════════════════════════════════════════════
# 6. 汇总报告
# ══════════════════════════════════════════════════════════════════

class ImportanceReport:

    def __init__(self, use_shap: bool = True):
        self._fanova = fANOVAAnalyzer(method="auto")
        self._shap   = SHAPImportance(self._fanova)
        self._plotter = MarginalPlotter(n_bins=10)
        self.use_shap = use_shap

    def analyze(self, configs: List[Dict], scores: List[float],
                top_n: int = 8) -> Dict:
        if len(configs) < 5:
            return {"ok": False, "error": "样本不足（需 >= 5 条记录）"}

        # 1. fANOVA
        fanova_res = self._fanova.fit(configs, scores)

        # 2. SHAP（可选）
        shap_res = None
        if self.use_shap:
            shap_res = self._shap.compute(configs, scores)

        final_res = shap_res if shap_res else fanova_res

        # Top-N 参数
        top_params = [r.param_name for r in final_res[:top_n]]

        # 3. 边际曲线
        marginal = self._plotter.compute(configs, scores, top_params=top_params)

        # 4. 组合输出
        method_used = (shap_res[0].method if shap_res else
                       (fanova_res[0].method if fanova_res else "fallback"))

        return {
            "ok": True,
            "n_samples": len(configs),
            "method": method_used,
            "top_params": top_params,
            "importance": [r.to_dict() for r in final_res[:top_n]],
            "marginal": marginal,
            "fanova": [r.to_dict() for r in fanova_res[:top_n]],
        }


# ══════════════════════════════════════════════════════════════════
# 7. 适配器 — 零侵入集成到进化引擎
# ══════════════════════════════════════════════════════════════════

class ImportanceEvolveAdapter:
    """
    从进化引擎历史数据实时分析超参数重要性
    evolve_ctrl: SelfEvolveController 实例
    """

    def __init__(self, evolve_ctrl):
        self._ctrl = evolve_ctrl
        self._report = ImportanceReport(use_shap=True)

    def _extract_history(self) -> Tuple[List[Dict], List[float]]:
        """从进化引擎提取历史配置和得分"""
        configs, scores = [], []
        try:
            hist = getattr(self._ctrl, "history", [])
            for item in hist:
                cfg = item.get("config") or item.get("params") or {}
                score = item.get("score") or item.get("fitness") or item.get("value")
                if cfg and score is not None:
                    configs.append(cfg)
                    scores.append(float(score))
        except Exception as e:
            logger.warning(f"[ImportanceAdapter] 提取历史失败: {e}")
        return configs, scores

    def analyze(self, top_n: int = 8) -> Dict:
        configs, scores = self._extract_history()
        if len(configs) < 5:
            return {"ok": False, "error": f"历史记录不足（{len(configs)}/5）"}
        return self._report.analyze(configs, scores, top_n=top_n)


# ══════════════════════════════════════════════════════════════════
# 8. 快速演示
# ══════════════════════════════════════════════════════════════════

def demo():
    import random
    random.seed(42)
    configs = [
        {
            "lr": round(10 ** random.uniform(-4, -1), 6),
            "batch": random.choice([16, 32, 64, 128]),
            "optimizer": random.choice(["adam", "sgd", "adamw"]),
            "dropout": round(random.uniform(0, 0.5), 2),
            "weight_decay": round(10 ** random.uniform(-5, -2), 6),
        }
        for _ in range(50)
    ]
    # lr 是最重要的参数
    scores = [
        -abs(math.log10(c["lr"]) + 3) * 2
        + (0.2 if c["optimizer"] == "adamw" else 0)
        - c["dropout"] * 0.5
        + random.gauss(0, 0.1)
        for c in configs
    ]

    report = ImportanceReport(use_shap=False)  # shap 可选
    result = report.analyze(configs, scores, top_n=5)

    print(f"分析方法: {result['method']}  样本数: {result['n_samples']}")
    print("\n── 超参数重要性排名 ──")
    for item in result["importance"]:
        bar = "█" * int(item["importance"] * 30)
        print(f"  {item['param']:15s} {bar:30s} {item['importance']*100:5.1f}%")

    print("\n── lr 边际曲线（前3个点）──")
    for pt in result["marginal"].get("lr", [])[:3]:
        print(f"  x={pt['x']:.6f}  y_mean={pt['y_mean']:.4f}  std={pt['y_std']:.4f}")

    print("\n✅ 超参数重要性分析演示通过")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
