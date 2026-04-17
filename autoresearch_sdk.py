"""
autoresearch_sdk.py
═══════════════════════════════════════════════════════════════════
Python REST SDK 客户端
───────────────────────────────────────────────────────────────────
对 AutoResearch 统一服务器（默认 http://localhost:8899）提供
完整的 Python 客户端封装，支持：

  AutoResearchClient
    ├── status()                 → 系统状态
    ├── start_evolve / stop_evolve
    ├── start_autorun / stop_autorun
    │
    ├── EvolveAPI                → 进化引擎操作
    │     optimize(space, steps) → 提交优化任务（同步等待）
    │     history()              → 历史记录
    │     best()                 → 最优配置
    │
    ├── ExperimentAPI            → 实验版本管理
    │     list(tag, limit)       → 列表
    │     get(exp_id)            → 详情
    │     leaderboard(top_n)     → 排行榜
    │     compare(id1, id2)      → 对比
    │
    ├── ImportanceAPI            → 超参数重要性
    │     analyze(top_n)         → 分析报告
    │
    ├── DriftAPI                 → 漂移检测
    │     status()               → 当前状态
    │     push_score(score)      → 推送新得分
    │
    ├── BOHBAPI                  → BOHB 基准
    │     benchmark(budget)      → 运行基准测试
    │
    └── WatchStream              → 实时事件流（WebSocket 替代，SSE 轮询）
          watch(callback, interval_s)

用法示例：
    from autoresearch_sdk import AutoResearchClient
    client = AutoResearchClient("http://localhost:8899")

    # 提交优化任务
    result = client.evolve.optimize(
        space={"lr": [1e-4, 1e-1], "batch": [16, 64, 128]},
        steps=30,
        tag="my_experiment",
    )
    print(result["best_config"], result["best_score"])

    # 查看排行榜
    lb = client.experiments.leaderboard(10)
    for row in lb:
        print(row)
"""

from __future__ import annotations
import json
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Callable, Dict, List, Optional, Union


# ══════════════════════════════════════════════════════════════════
# 1. 底层 HTTP 工具
# ══════════════════════════════════════════════════════════════════

class _HTTPClient:
    """最小化 HTTP 客户端，仅依赖 stdlib"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.last_latency_ms: float = 0.0

    def _request(self, method: str, path: str,
                 data: Optional[Dict] = None,
                 params: Optional[Dict] = None) -> Dict:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.last_latency_ms = (time.time() - t0) * 1000
                content = resp.read().decode("utf-8")
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"_raw": content}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise AutoResearchError(
                f"HTTP {e.code} {e.reason}: {body_text}", status_code=e.code
            )
        except urllib.error.URLError as e:
            raise AutoResearchError(f"连接失败: {e.reason}")
        except Exception as e:
            raise AutoResearchError(f"请求异常: {e}")

    def get(self, path: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, data: Optional[Dict] = None) -> Dict:
        return self._request("POST", path, data=data or {})


# ══════════════════════════════════════════════════════════════════
# 2. 异常类
# ══════════════════════════════════════════════════════════════════

class AutoResearchError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


# ══════════════════════════════════════════════════════════════════
# 3. 子 API 命名空间
# ══════════════════════════════════════════════════════════════════

class EvolveAPI:
    """进化引擎操作"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def status(self) -> Dict:
        return self._http.get("/api/evolve/status")

    def start(self) -> Dict:
        return self._http.post("/api/evolve/start")

    def stop(self) -> Dict:
        return self._http.post("/api/evolve/stop")

    def history(self, limit: int = 50) -> List[Dict]:
        resp = self._http.get("/api/evolve/history", params={"limit": limit})
        return resp.get("history", resp if isinstance(resp, list) else [])

    def best(self) -> Optional[Dict]:
        resp = self._http.get("/api/evolve/best")
        return resp

    def optimize(
        self,
        space: Dict,
        steps: int = 20,
        tag: str = "sdk",
        timeout_s: float = 300.0,
        poll_interval_s: float = 2.0,
    ) -> Dict:
        """
        提交一次超参数优化并同步等待结果
        space 格式：
          {"lr": [1e-4, 1e-1],          # 连续区间
           "batch": [16, 32, 64, 128],  # 离散候选
           "optimizer": ["adam","adamw"]}
        """
        # 提交
        payload = {"space": space, "steps": steps, "tag": tag}
        try:
            resp = self._http.post("/api/evolve/optimize", data=payload)
        except AutoResearchError:
            # 服务器可能不支持该端点，降级为轮询 best
            resp = {"task_id": None}

        task_id = resp.get("task_id")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(poll_interval_s)
            try:
                status = self.status()
                running = status.get("running", status.get("evolve_running", False))
                if not running:
                    break
            except Exception:
                break

        best = self.best()
        return {
            "task_id": task_id,
            "tag": tag,
            "best_config": best.get("config") if best else None,
            "best_score": best.get("score") if best else None,
            "raw": best,
        }

    def submit_score(self, config: Dict, score: float, tag: str = "sdk") -> Dict:
        """手动提交一次评估结果供引擎学习"""
        return self._http.post("/api/evolve/submit", data={
            "config": config, "score": score, "tag": tag
        })


class ExperimentAPI:
    """实验版本管理"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def list(self, tag: Optional[str] = None,
             limit: int = 50, sort_by: str = "score") -> List[Dict]:
        params = {"limit": limit, "sort_by": sort_by}
        if tag:
            params["tag"] = tag
        resp = self._http.get("/api/experiments/list", params=params)
        return resp.get("records", [])

    def get(self, exp_id: str) -> Dict:
        return self._http.get("/api/experiments/get", params={"exp_id": exp_id})

    def leaderboard(self, top_n: int = 10) -> List[Dict]:
        resp = self._http.get("/api/experiments/leaderboard", params={"top_n": top_n})
        return resp.get("leaderboard", [])

    def compare(self, id1: str, id2: str) -> Dict:
        return self._http.get("/api/experiments/compare",
                              params={"id1": id1, "id2": id2})

    def add_notes(self, exp_id: str, notes: str) -> Dict:
        return self._http.post("/api/experiments/notes",
                               data={"exp_id": exp_id, "notes": notes})


class ImportanceAPI:
    """超参数重要性分析"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def analyze(self, top_n: int = 8) -> Dict:
        return self._http.get("/api/importance/analyze", params={"top_n": top_n})

    def marginal(self, param: str) -> Dict:
        return self._http.get("/api/importance/marginal", params={"param": param})


class DriftAPI:
    """模型漂移检测"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def status(self) -> Dict:
        return self._http.get("/api/drift/status")

    def push_score(self, score: float) -> Dict:
        return self._http.post("/api/drift/push", data={"score": score})

    def reset(self) -> Dict:
        return self._http.post("/api/drift/reset")


class BOHBAPI:
    """BOHB 多保真度优化"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def benchmark(self, budget: int = 27, timeout_s: float = 180) -> Dict:
        return self._http.get("/api/bohb/benchmark",
                              params={"budget": budget})


class MonitorAPI:
    """系统监控"""

    def __init__(self, http: _HTTPClient):
        self._http = http

    def status(self) -> Dict:
        return self._http.get("/api/status")

    def autorun_tasks(self) -> Dict:
        return self._http.get("/api/autorun/tasks")

    def evolve_metrics(self) -> Dict:
        return self._http.get("/api/evolve/metrics")


# ══════════════════════════════════════════════════════════════════
# 4. 实时观察流（轮询版 SSE）
# ══════════════════════════════════════════════════════════════════

class WatchStream:
    """
    轮询服务器状态，对变化调用 callback
    callback(event_type: str, data: Dict)
    """

    def __init__(self, http: _HTTPClient, interval_s: float = 3.0):
        self._http = http
        self.interval_s = interval_s
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_status: Dict = {}

    def watch(self, callback: Callable[[str, Dict], None]):
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, args=(callback,), daemon=True
        )
        self._thread.start()
        return self

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval_s + 1)

    def _loop(self, callback: Callable):
        while self._running:
            try:
                status = self._http.get("/api/status")
                self._detect_changes(status, callback)
            except Exception as e:
                callback("error", {"message": str(e)})
            time.sleep(self.interval_s)

    def _detect_changes(self, current: Dict, callback: Callable):
        prev = self._last_status
        if not prev:
            callback("connected", current)
        else:
            for key in ("evolve_running", "autorun_running"):
                if current.get(key) != prev.get(key):
                    callback("state_change", {
                        "key": key,
                        "from": prev.get(key),
                        "to": current.get(key),
                        "status": current,
                    })
            # 检测进化代数变化
            gen_key = "generation"
            if current.get(gen_key, 0) > prev.get(gen_key, 0):
                callback("new_generation", {
                    "generation": current.get(gen_key),
                    "best_score": current.get("best_score"),
                })
        self._last_status = current


# ══════════════════════════════════════════════════════════════════
# 5. 主客户端
# ══════════════════════════════════════════════════════════════════

class AutoResearchClient:
    """
    AutoResearch 统一 Python SDK

    用法：
        client = AutoResearchClient("http://localhost:8899")
        print(client.status())
        result = client.evolve.optimize(space, steps=20)
        lb = client.experiments.leaderboard(10)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8899",
        timeout: float = 30.0,
    ):
        self._http = _HTTPClient(base_url, timeout=timeout)
        self.evolve      = EvolveAPI(self._http)
        self.experiments = ExperimentAPI(self._http)
        self.importance  = ImportanceAPI(self._http)
        self.drift       = DriftAPI(self._http)
        self.bohb        = BOHBAPI(self._http)
        self.monitor     = MonitorAPI(self._http)
        self._watch      = WatchStream(self._http)

    def status(self) -> Dict:
        """获取系统整体状态"""
        return self._http.get("/api/status")

    def ping(self) -> bool:
        """检测服务器连通性"""
        try:
            self._http.get("/api/status")
            return True
        except AutoResearchError:
            return False

    def latency_ms(self) -> float:
        """最近一次请求延迟（毫秒）"""
        return self._http.last_latency_ms

    def watch(self, callback: Callable[[str, Dict], None],
              interval_s: float = 3.0) -> WatchStream:
        """启动实时状态监听"""
        self._watch.interval_s = interval_s
        return self._watch.watch(callback)

    def stop_watch(self):
        self._watch.stop()

    def __repr__(self) -> str:
        return f"AutoResearchClient(url={self._http.base_url!r})"

    # ── 便捷方法 ──────────────────────────────────────────────────

    def quick_status(self) -> str:
        """返回单行状态摘要"""
        try:
            s = self.status()
            ev = "🟢" if s.get("evolve_running") else "⚪"
            ar = "🟢" if s.get("autorun_running") else "⚪"
            gen = s.get("generation", "?")
            best = s.get("best_score")
            best_str = f"{best:.4f}" if best is not None else "N/A"
            latency = self._http.last_latency_ms
            return (f"[{self._http.base_url}] "
                    f"进化{ev} 自动运行{ar} "
                    f"Gen={gen} Best={best_str} "
                    f"延迟={latency:.0f}ms")
        except AutoResearchError as e:
            return f"[离线] {e}"


# ══════════════════════════════════════════════════════════════════
# 6. 便捷工厂函数
# ══════════════════════════════════════════════════════════════════

def connect(url: str = "http://localhost:8899", timeout: float = 30.0) -> AutoResearchClient:
    """创建并验证连接"""
    client = AutoResearchClient(url, timeout=timeout)
    if not client.ping():
        raise AutoResearchError(f"无法连接到 AutoResearch 服务器: {url}")
    return client


# ══════════════════════════════════════════════════════════════════
# 7. 命令行快速测试
# ══════════════════════════════════════════════════════════════════

def _cli():
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8899"
    print(f"连接到 {url}...")
    try:
        client = AutoResearchClient(url, timeout=5.0)
        if client.ping():
            print("✅ 服务器在线")
            print(client.quick_status())
            # 实验列表
            try:
                lb = client.experiments.leaderboard(5)
                if lb:
                    print(f"\n排行榜 Top{len(lb)}:")
                    for row in lb:
                        print(f"  #{row['rank']} score={row['score']:+.4f} tag={row['tag']}")
            except AutoResearchError:
                pass
            # 重要性分析
            try:
                imp = client.importance.analyze(top_n=5)
                if imp.get("ok"):
                    print(f"\n超参数重要性（{imp['method']}）:")
                    for item in imp["importance"][:5]:
                        print(f"  {item['param']:15s} {item['importance']*100:.1f}%")
            except AutoResearchError:
                pass
        else:
            print("❌ 服务器未响应")
    except AutoResearchError as e:
        print(f"❌ {e}")


if __name__ == "__main__":
    _cli()
