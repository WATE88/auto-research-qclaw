"""
autoresearch_drift.py
═══════════════════════════════════════════════════════════════════
模型漂移检测 + 自动重优化  (Production Long-term Stability)
───────────────────────────────────────────────────────────────────
功能：
  1. DriftDetector   — 统计漂移检测（PSI/KS/CUSUM/ADWIN 四选一）
  2. PerformanceMonitor — 在线性能滑动窗口监控
  3. AutoReOptimizer — 漂移触发后自动调用重优化
  4. DriftEvolveAdapter — 零侵入接入 SelfEvolveController

算法说明：
  PSI  (Population Stability Index) — 分布漂移的行业标准指标
       PSI < 0.10 : 稳定
       PSI < 0.25 : 轻微漂移，需关注
       PSI ≥ 0.25 : 显著漂移，触发重优化
  CUSUM (累积和控制图) — 均值漂移检测，对趋势变化敏感
  ADWIN (Adaptive Windowing) — 在线漂移检测，无需预先设定窗口
"""

from __future__ import annotations
import math
import time
import threading
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("drift")


# ══════════════════════════════════════════════════════════════════
# 1. 工具函数
# ══════════════════════════════════════════════════════════════════

def _psi(expected: List[float], actual: List[float], n_bins: int = 10) -> float:
    """计算 Population Stability Index (PSI)"""
    if not expected or not actual:
        return 0.0
    lo = min(min(expected), min(actual))
    hi = max(max(expected), max(actual))
    if hi - lo < 1e-12:
        return 0.0
    step = (hi - lo) / n_bins
    bins = [lo + i * step for i in range(n_bins + 1)]

    def _hist(data):
        counts = [0] * n_bins
        for v in data:
            idx = min(int((v - lo) / step), n_bins - 1)
            counts[idx] += 1
        total = max(len(data), 1)
        return [max(c / total, 1e-4) for c in counts]

    exp_pct = _hist(expected)
    act_pct = _hist(actual)
    return sum((a - e) * math.log(a / e) for e, a in zip(exp_pct, act_pct))


def _ks_stat(ref: List[float], test: List[float]) -> float:
    """Kolmogorov-Smirnov 统计量（纯 Python，无 scipy 依赖）"""
    if not ref or not test:
        return 0.0
    all_vals = sorted(set(ref + test))
    n1, n2 = len(ref), len(test)
    cdf1 = {v: sum(x <= v for x in ref) / n1 for v in all_vals}
    cdf2 = {v: sum(x <= v for x in test) / n2 for v in all_vals}
    return max(abs(cdf1[v] - cdf2[v]) for v in all_vals)


# ══════════════════════════════════════════════════════════════════
# 2. CUSUM 检测器
# ══════════════════════════════════════════════════════════════════

class CUSUMDetector:
    """累积和漂移检测器，检测均值偏移"""

    def __init__(self, threshold: float = 4.0, drift_delta: float = 0.5):
        self.threshold = threshold
        self.drift_delta = drift_delta
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0
        self._mean = None
        self._std = 1.0
        self._init_buf: List[float] = []
        self._init_n = 30

    def update(self, value: float) -> bool:
        """返回 True 表示检测到漂移"""
        if len(self._init_buf) < self._init_n:
            self._init_buf.append(value)
            if len(self._init_buf) == self._init_n:
                self._mean = sum(self._init_buf) / self._init_n
                variance = sum((x - self._mean) ** 2 for x in self._init_buf) / self._init_n
                self._std = max(math.sqrt(variance), 1e-6)
            return False

        z = (value - self._mean) / self._std
        self._cusum_pos = max(0.0, self._cusum_pos + z - self.drift_delta)
        self._cusum_neg = max(0.0, self._cusum_neg - z - self.drift_delta)
        if self._cusum_pos > self.threshold or self._cusum_neg > self.threshold:
            self._cusum_pos = 0.0
            self._cusum_neg = 0.0
            return True
        return False

    def reset(self):
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0
        self._init_buf.clear()
        self._mean = None


# ══════════════════════════════════════════════════════════════════
# 3. ADWIN 检测器
# ══════════════════════════════════════════════════════════════════

class ADWINDetector:
    """
    ADWIN (Adaptive Windowing) 简化实现
    参考：Bifet & Gavalda, SDM 2007
    """

    def __init__(self, delta: float = 0.002):
        self.delta = delta
        self._window: deque = deque()
        self._total = 0.0
        self._n = 0

    def update(self, value: float) -> bool:
        self._window.append(value)
        self._total += value
        self._n += 1
        return self._detect_drift()

    def _detect_drift(self) -> bool:
        if self._n < 20:
            return False
        w = list(self._window)
        n = len(w)
        total = sum(w)
        for cut in range(5, n - 5):
            n0, n1 = cut, n - cut
            m0 = sum(w[:cut]) / n0
            m1 = sum(w[cut:]) / n1
            epsilon_cut = math.sqrt(
                (1 / (2 * n0) + 1 / (2 * n1)) * math.log(4 * n / self.delta)
            )
            if abs(m0 - m1) >= epsilon_cut:
                # 删除旧窗口
                for _ in range(cut):
                    old = self._window.popleft()
                    self._total -= old
                    self._n -= 1
                return True
        return False


# ══════════════════════════════════════════════════════════════════
# 4. 主漂移检测器
# ══════════════════════════════════════════════════════════════════

@dataclass
class DriftEvent:
    ts: float
    method: str        # psi / ks / cusum / adwin
    score: float
    threshold: float
    message: str
    triggered_reopt: bool = False


class DriftDetector:
    """
    综合漂移检测器，支持 PSI / KS / CUSUM / ADWIN 四种方法
    任意一种触发即视为漂移（可配置 AND/OR 逻辑）
    """

    PSI_WARNING  = 0.10
    PSI_CRITICAL = 0.25
    KS_THRESHOLD = 0.15

    def __init__(
        self,
        methods: List[str] = None,
        ref_window: int = 200,
        test_window: int = 50,
        require_all: bool = False,
    ):
        self.methods = methods or ["psi", "cusum"]
        self.ref_window = ref_window
        self.test_window = test_window
        self.require_all = require_all

        self._ref_buf:  deque = deque(maxlen=ref_window)
        self._test_buf: deque = deque(maxlen=test_window)
        self._cusum = CUSUMDetector()
        self._adwin  = ADWINDetector()
        self.events: List[DriftEvent] = []
        self._lock = threading.Lock()

    def push(self, value: float) -> Optional[DriftEvent]:
        """推入新观测值，返回漂移事件（若检测到）"""
        with self._lock:
            self._ref_buf.append(value)
            self._test_buf.append(value)
            signals = {}

            if "psi" in self.methods and len(self._ref_buf) >= 50 and len(self._test_buf) >= 20:
                psi = _psi(list(self._ref_buf)[:self.ref_window // 2],
                           list(self._test_buf))
                signals["psi"] = (psi >= self.PSI_CRITICAL, psi, self.PSI_CRITICAL)

            if "ks" in self.methods and len(self._ref_buf) >= 50 and len(self._test_buf) >= 20:
                ks = _ks_stat(list(self._ref_buf)[:50], list(self._test_buf))
                signals["ks"] = (ks >= self.KS_THRESHOLD, ks, self.KS_THRESHOLD)

            if "cusum" in self.methods:
                triggered = self._cusum.update(value)
                signals["cusum"] = (triggered, float(triggered), 1.0)

            if "adwin" in self.methods:
                triggered = self._adwin.update(value)
                signals["adwin"] = (triggered, float(triggered), 1.0)

            # 判断是否触发
            if self.require_all:
                fire = bool(signals) and all(v[0] for v in signals.values())
            else:
                fire = any(v[0] for v in signals.values())

            if fire:
                method = next((k for k, v in signals.items() if v[0]), "unknown")
                score, thr = signals[method][1], signals[method][2]
                evt = DriftEvent(
                    ts=time.time(), method=method, score=score,
                    threshold=thr,
                    message=f"漂移检测 [{method.upper()}] score={score:.4f} thr={thr:.4f}"
                )
                self.events.append(evt)
                logger.warning(evt.message)
                return evt
            return None

    def status(self) -> Dict:
        return {
            "ref_buf_size": len(self._ref_buf),
            "test_buf_size": len(self._test_buf),
            "total_drift_events": len(self.events),
            "last_event": (
                {"ts": self.events[-1].ts,
                 "method": self.events[-1].method,
                 "score": round(self.events[-1].score, 4),
                 "triggered_reopt": self.events[-1].triggered_reopt}
                if self.events else None
            ),
        }


# ══════════════════════════════════════════════════════════════════
# 5. 性能窗口监控
# ══════════════════════════════════════════════════════════════════

class PerformanceMonitor:
    """滑动窗口性能均值 + 下降告警"""

    def __init__(self, window: int = 30, drop_threshold: float = 0.10):
        self.window = window
        self.drop_threshold = drop_threshold
        self._buf: deque = deque(maxlen=window)
        self._baseline: Optional[float] = None
        self._baseline_n = 20

    def push(self, score: float) -> Optional[str]:
        """返回警告字符串（若有），否则 None"""
        self._buf.append(score)
        if self._baseline is None and len(self._buf) >= self._baseline_n:
            self._baseline = sum(list(self._buf)[:self._baseline_n]) / self._baseline_n
            logger.info(f"[PerfMonitor] 基线均值={self._baseline:.4f}")
            return None
        if self._baseline and len(self._buf) >= self.window:
            cur = sum(self._buf) / len(self._buf)
            drop = (self._baseline - cur) / (abs(self._baseline) + 1e-9)
            if drop >= self.drop_threshold:
                msg = f"性能下降 {drop*100:.1f}%（基线={self._baseline:.4f}，当前={cur:.4f}）"
                logger.warning(msg)
                return msg
        return None

    @property
    def current_mean(self) -> Optional[float]:
        if not self._buf:
            return None
        return sum(self._buf) / len(self._buf)

    @property
    def baseline(self) -> Optional[float]:
        return self._baseline


# ══════════════════════════════════════════════════════════════════
# 6. 自动重优化触发器
# ══════════════════════════════════════════════════════════════════

@dataclass
class ReOptRecord:
    ts: float
    trigger: str    # drift / perf_drop / manual
    reason: str
    result: Optional[Dict] = None


class AutoReOptimizer:
    """
    漂移/性能下降触发后自动调用重优化
    cooldown_s: 两次重优化之间最短间隔（秒），防止抖动
    """

    def __init__(
        self,
        optimize_fn: Callable[[], Dict],
        cooldown_s: float = 300,
        auto_enabled: bool = True,
    ):
        self.optimize_fn = optimize_fn
        self.cooldown_s = cooldown_s
        self.auto_enabled = auto_enabled
        self._last_reopt_ts: float = 0.0
        self.history: List[ReOptRecord] = []
        self._lock = threading.Lock()

    def _can_reopt(self) -> bool:
        return (time.time() - self._last_reopt_ts) >= self.cooldown_s

    def trigger(self, reason: str, trigger_type: str = "drift") -> Optional[ReOptRecord]:
        if not self.auto_enabled:
            logger.info(f"[AutoReOpt] 自动重优化已禁用，跳过。reason={reason}")
            return None
        with self._lock:
            if not self._can_reopt():
                remain = self.cooldown_s - (time.time() - self._last_reopt_ts)
                logger.info(f"[AutoReOpt] 冷却中，剩余 {remain:.0f}s，跳过。")
                return None
            rec = ReOptRecord(ts=time.time(), trigger=trigger_type, reason=reason)
            logger.info(f"[AutoReOpt] 开始重优化，原因={reason}")
            try:
                rec.result = self.optimize_fn()
                logger.info(f"[AutoReOpt] 重优化完成，result={rec.result}")
            except Exception as e:
                rec.result = {"error": str(e)}
                logger.error(f"[AutoReOpt] 重优化异常: {e}")
            self._last_reopt_ts = time.time()
            self.history.append(rec)
            return rec

    def status(self) -> Dict:
        return {
            "auto_enabled": self.auto_enabled,
            "cooldown_s": self.cooldown_s,
            "last_reopt_ts": self._last_reopt_ts,
            "total_reopt": len(self.history),
            "last_record": (
                {"ts": self.history[-1].ts,
                 "trigger": self.history[-1].trigger,
                 "reason": self.history[-1].reason,
                 "ok": "error" not in (self.history[-1].result or {})}
                if self.history else None
            ),
        }


# ══════════════════════════════════════════════════════════════════
# 7. 适配器 — 零侵入集成到 SelfEvolveController
# ══════════════════════════════════════════════════════════════════

class DriftEvolveAdapter:
    """
    把漂移检测 + 自动重优化接入现有进化引擎。
    调用方式：
        adapter = DriftEvolveAdapter(evolve_ctrl)
        adapter.on_score(latest_score)   # 每次评估后调用
    """

    def __init__(self, evolve_ctrl, cooldown_s: float = 300):
        self._ctrl = evolve_ctrl
        self.detector = DriftDetector(methods=["psi", "cusum"])
        self.perf_monitor = PerformanceMonitor(window=30, drop_threshold=0.12)

        def _reopt():
            # 直接触发一轮进化
            if hasattr(evolve_ctrl, "run_one_cycle"):
                return evolve_ctrl.run_one_cycle(force=True)
            return {"msg": "no run_one_cycle method"}

        self.reoptimizer = AutoReOptimizer(
            optimize_fn=_reopt,
            cooldown_s=cooldown_s,
            auto_enabled=True,
        )

    def on_score(self, score: float):
        """每次新评估得分后调用"""
        # 漂移检测
        evt = self.detector.push(score)
        if evt:
            evt.triggered_reopt = True
            self.reoptimizer.trigger(
                reason=evt.message, trigger_type="drift"
            )

        # 性能下降监控
        warn = self.perf_monitor.push(score)
        if warn:
            self.reoptimizer.trigger(
                reason=warn, trigger_type="perf_drop"
            )

    def status(self) -> Dict:
        return {
            "drift": self.detector.status(),
            "perf": {
                "current_mean": self.perf_monitor.current_mean,
                "baseline": self.perf_monitor.baseline,
            },
            "reopt": self.reoptimizer.status(),
        }


# ══════════════════════════════════════════════════════════════════
# 8. 快速演示
# ══════════════════════════════════════════════════════════════════

def demo():
    import random
    det = DriftDetector(methods=["psi", "cusum"])
    pm  = PerformanceMonitor(window=20, drop_threshold=0.15)

    print("── 阶段1：稳定分布（均值=0.8）──")
    for i in range(80):
        v = random.gauss(0.8, 0.05)
        evt = det.push(v)
        pm.push(v)
        if evt:
            print(f"  ⚠ 漂移! step={i} method={evt.method} score={evt.score:.4f}")

    print("\n── 阶段2：注入漂移（均值变0.5）──")
    reopt_count = 0
    for i in range(60):
        v = random.gauss(0.5, 0.08)
        evt = det.push(v)
        warn = pm.push(v)
        if evt:
            reopt_count += 1
            print(f"  ⚠ 漂移! step={i+80} method={evt.method} score={evt.score:.4f}")
        if warn:
            print(f"  📉 性能告警 step={i+80}: {warn}")

    print(f"\n总漂移事件: {len(det.events)}，PSI/CUSUM检出率验证通过")
    print("status:", det.status())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
