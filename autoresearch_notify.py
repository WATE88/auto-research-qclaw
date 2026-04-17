"""
AutoResearch 通知推送模块 v1.0
================================
支持以下通知渠道（按优先级自动选择）：
  1. Windows Toast 通知（winotify）
  2. 跨平台通知（plyer）
  3. 系统命令备选（Windows msg / macOS osascript）
  4. 本地日志文件（兜底，永远可用）

触发场景：
  - 进化完成一代（每 N 代通知一次，避免刷屏）
  - 发现历史最优（立即通知）
  - 连续停滞触发重置（通知 + 建议）
  - 自动运行任务失败（立即告警）
  - 系统异常退出（立即告警）

用法：
  from autoresearch_notify import Notifier
  notifier = Notifier()
  notifier.on_new_best(gen=5, score=0.912)
  notifier.on_evolution_complete(gen=10, score=0.88, improvement=0.03)
  notifier.on_stagnation_reset(gen=15, stagnation_count=5)
  notifier.on_task_failed(task_name="Ackley5D", error="timeout")
  notifier.on_system_error("进化引擎崩溃", "NaN in GP kernel")
"""

import os
import sys
import time
import json
import platform
import threading
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
NOTIFY_LOG = BASE_DIR / "notify.log"
NOTIFY_CONFIG = BASE_DIR / "notify_config.json"


# ─────────────────────────────────────────────────────────────────────────────
#  配置管理
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "enabled": True,
    "best_score_threshold": 0.0,   # 只有高于此分才发"新最优"通知
    "notify_every_n_gens": 5,       # 每 N 代发一次普通进化通知（0=禁用）
    "notify_on_new_best": True,     # 是否通知新历史最优
    "notify_on_stagnation": True,   # 是否通知停滞重置
    "notify_on_task_fail": True,    # 是否通知任务失败
    "notify_on_error": True,        # 是否通知系统错误
    "cooldown_seconds": 30,         # 同类通知冷却时间（避免刷屏）
    "app_name": "AutoResearch",
}


def load_config() -> dict:
    if NOTIFY_CONFIG.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(NOTIFY_CONFIG.read_text("utf-8"))}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    try:
        NOTIFY_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  后端：尝试多种通知方式
# ─────────────────────────────────────────────────────────────────────────────

class _ToastBackend:
    """Windows winotify 后端"""
    _available = None

    @classmethod
    def is_available(cls) -> bool:
        if cls._available is None:
            try:
                from winotify import Notification
                cls._available = True
            except ImportError:
                cls._available = False
        return cls._available

    @staticmethod
    def send(title: str, body: str, icon: str = "", app_name: str = "AutoResearch"):
        from winotify import Notification, audio
        toast = Notification(
            app_id=app_name,
            title=title,
            msg=body,
            duration="short",
            icon=icon or "",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()


class _PlyerBackend:
    """plyer 跨平台后端"""
    _available = None

    @classmethod
    def is_available(cls) -> bool:
        if cls._available is None:
            try:
                from plyer import notification
                cls._available = True
            except ImportError:
                cls._available = False
        return cls._available

    @staticmethod
    def send(title: str, body: str, app_name: str = "AutoResearch", timeout: int = 8):
        from plyer import notification
        notification.notify(
            title=title,
            message=body,
            app_name=app_name,
            timeout=timeout,
        )


class _SysBackend:
    """系统命令后端（Windows msg / macOS osascript）"""

    @staticmethod
    def is_available() -> bool:
        return platform.system() in ("Windows", "Darwin")

    @staticmethod
    def send(title: str, body: str, **kwargs):
        sys_name = platform.system()
        if sys_name == "Windows":
            try:
                # PowerShell Toast（不依赖第三方库）
                ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = '{title.replace("'", "''")}'
$notify.BalloonTipText  = '{body.replace("'", "''")}'
$notify.Visible = $True
$notify.ShowBalloonTip(6000)
Start-Sleep -Seconds 6
$notify.Dispose()
"""
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        elif sys_name == "Darwin":
            try:
                subprocess.Popen(
                    ["osascript", "-e",
                     f'display notification "{body}" with title "{title}"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass


def _write_log(title: str, body: str, level: str = "INFO"):
    """兜底：写入本地日志文件（永远可用）"""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {title} | {body}\n"
        with NOTIFY_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  主 Notifier 类
# ─────────────────────────────────────────────────────────────────────────────

class Notifier:
    """
    AutoResearch 统一通知推送器。
    线程安全，自动选择可用后端，带冷却时间防刷屏。
    """

    def __init__(self):
        self.cfg = load_config()
        self._lock = threading.Lock()
        self._last_notify: dict = {}   # event_type -> last timestamp
        self._gen_counter = 0

        # 自动探测后端
        if _ToastBackend.is_available():
            self._backend_name = "winotify"
        elif _PlyerBackend.is_available():
            self._backend_name = "plyer"
        elif _SysBackend.is_available():
            self._backend_name = "sys"
        else:
            self._backend_name = "log_only"

        _write_log("Notifier", f"初始化完成，后端={self._backend_name}", "INIT")

    # ── 内部：实际发送 ────────────────────────────────────────────────────────

    def _send(self, title: str, body: str, event_type: str, level: str = "INFO"):
        """带冷却的内部发送"""
        if not self.cfg.get("enabled", True):
            _write_log(title, body, level)
            return

        now = time.time()
        cooldown = self.cfg.get("cooldown_seconds", 30)

        with self._lock:
            last = self._last_notify.get(event_type, 0)
            if now - last < cooldown:
                # 冷却中，只写日志
                _write_log(title, f"[冷却中] {body}", level)
                return
            self._last_notify[event_type] = now

        # 异步发送，不阻塞调用方
        threading.Thread(
            target=self._do_send,
            args=(title, body, level),
            daemon=True
        ).start()

    def _do_send(self, title: str, body: str, level: str):
        try:
            app = self.cfg.get("app_name", "AutoResearch")
            if self._backend_name == "winotify":
                _ToastBackend.send(title, body, app_name=app)
            elif self._backend_name == "plyer":
                _PlyerBackend.send(title, body, app_name=app)
            elif self._backend_name == "sys":
                _SysBackend.send(title, body)
        except Exception as e:
            _write_log("通知发送失败", str(e), "WARN")
        finally:
            _write_log(title, body, level)  # 始终写日志

    # ── 公开事件接口 ──────────────────────────────────────────────────────────

    def on_new_best(self, gen: int, score: float, genome_hint: str = ""):
        """发现历史最优时调用"""
        if not self.cfg.get("notify_on_new_best", True):
            return
        thr = self.cfg.get("best_score_threshold", 0.0)
        if score < thr:
            return
        title = f"🏆 AutoResearch · 新历史最优！"
        body  = (f"第 {gen} 代 · 得分 {score:.4f}"
                 + (f"\n策略: {genome_hint}" if genome_hint else ""))
        self._send(title, body, "new_best", "BEST")

    def on_evolution_complete(self, gen: int, score: float, improvement: float):
        """每代进化完成时调用（按 notify_every_n_gens 节流）"""
        n = self.cfg.get("notify_every_n_gens", 5)
        if n <= 0:
            return
        self._gen_counter += 1
        if self._gen_counter % n != 0:
            return
        sign = "+" if improvement >= 0 else ""
        title = f"⚙️ AutoResearch · 第 {gen} 代完成"
        body  = f"得分 {score:.4f}  (改进 {sign}{improvement:.4f})"
        self._send(title, body, "evo_complete", "INFO")

    def on_stagnation_reset(self, gen: int, stagnation_count: int):
        """连续停滞触发重置时调用"""
        if not self.cfg.get("notify_on_stagnation", True):
            return
        title = f"🔄 AutoResearch · 停滞重置"
        body  = (f"第 {gen} 代 · 连续 {stagnation_count} 代无提升\n"
                 f"已自动触发随机重置，增加多样性...")
        self._send(title, body, "stagnation", "WARN")

    def on_task_failed(self, task_name: str, error: str):
        """自动运行任务失败时调用"""
        if not self.cfg.get("notify_on_task_fail", True):
            return
        title = f"❌ AutoResearch · 任务失败"
        body  = f"任务: {task_name}\n错误: {error[:120]}"
        self._send(title, body, f"task_fail_{task_name}", "ERROR")

    def on_system_error(self, component: str, error: str):
        """系统级错误时调用（最高优先级，忽略冷却）"""
        if not self.cfg.get("notify_on_error", True):
            return
        title = f"🚨 AutoResearch · 系统错误"
        body  = f"组件: {component}\n{error[:120]}"
        # 系统错误不走冷却，直接异步发送
        threading.Thread(
            target=self._do_send,
            args=(title, body, "CRITICAL"),
            daemon=True
        ).start()

    def on_parallel_batch_done(self, batch_size: int, best_score: float, elapsed: float):
        """异步并行批次完成时调用"""
        title = f"⚡ AutoResearch · 并行批次完成"
        body  = (f"本批 {batch_size} 个候选全部评估完毕\n"
                 f"当前最优 {best_score:.4f} · 耗时 {elapsed:.1f}s")
        self._send(title, body, "parallel_batch", "INFO")

    def test(self):
        """测试所有通知渠道"""
        print(f"[Notifier] 后端={self._backend_name}")
        self.on_new_best(gen=1, score=0.912, genome_hint="UCB kappa=3.2")
        time.sleep(1)
        self.on_evolution_complete(gen=5, score=0.888, improvement=0.015)
        time.sleep(1)
        self.on_stagnation_reset(gen=15, stagnation_count=5)
        time.sleep(1)
        self.on_task_failed(task_name="Hartmann6D", error="Timeout after 30s")
        time.sleep(2)
        print("[Notifier] 测试完成，查看系统通知和 notify.log")


# ─────────────────────────────────────────────────────────────────────────────
#  单例（供其他模块直接 import）
# ─────────────────────────────────────────────────────────────────────────────

_notifier_instance: Notifier = None
_notifier_lock = threading.Lock()


def get_notifier() -> Notifier:
    """获取全局单例 Notifier"""
    global _notifier_instance
    if _notifier_instance is None:
        with _notifier_lock:
            if _notifier_instance is None:
                _notifier_instance = Notifier()
    return _notifier_instance


# ─────────────────────────────────────────────────────────────────────────────
#  CLI 测试入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== AutoResearch 通知测试 ===")
    n = get_notifier()
    n.test()
    print(f"\n通知日志位置: {NOTIFY_LOG}")
