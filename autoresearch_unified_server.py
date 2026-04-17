"""
AutoResearch 统一监控服务器 v2.0
================================
单端口 8899 同时驱动：
  - 自主进化系统（SelfEvolveController）
  - 自动运行引擎（AutoRunEngine）

路由：
  GET  /                    → 统一Dashboard HTML
  GET  /api/snapshot        → 完整双系统快照 JSON
  GET  /ws                  → WebSocket 实时推送（1s间隔）
"""

# ── 编码修复：必须在其他所有 import 之前 ─────────────────────────────────────
import os, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
try:
    import autoresearch_encoding  # 强制 UTF-8 控制台 + stdio
except ImportError:
    pass

import json, sqlite3, threading, time, hashlib, base64, struct, socket
import traceback  # 提前导入，避免子线程循环import（Python 3.14.3 issue）
import dataclasses  # 同上
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, TCPServer
from pathlib import Path

BASE_DIR     = Path(__file__).parent
PORT         = 8899
HTML_FILE    = BASE_DIR / "autoresearch_unified_dashboard.html"
HTML_V2_FILE = BASE_DIR / "autoresearch_dashboard_v2.html"
EVOLVE_DB = BASE_DIR / "evolution_monitor.db"
AUTORUN_DB = BASE_DIR / "autorun_monitor.db"

# ── 懒加载两个引擎（避免循环import影响启动速度）──────────────────────────────

_evolve_ctrl = None
_autorun_engine = None
_evolve_lock = threading.Lock()   # 独立锁，避免两引擎互相阻塞
_autorun_lock = threading.Lock()

# ── 快照缓存（后台刷新，HTTP直接读，永不阻塞）─────────────────────────────────
_snapshot_cache = {"data": None, "ts": 0.0}
_snapshot_cache_lock = threading.Lock()

def _refresh_snapshot_loop():
    """后台线程：每2秒刷新一次快照缓存"""
    _snap_err_log = BASE_DIR / "snapshot_error.log"
    while True:
        try:
            snap = _build_snapshot_now()
            with _snapshot_cache_lock:
                _snapshot_cache["data"] = snap
                _snapshot_cache["ts"] = time.time()
        except Exception as e:
            try:
                _snap_err_log.write_text(
                    f"{datetime.now().isoformat()} ERROR: {e}\n{traceback.format_exc()}",
                    encoding='utf-8'
                )
            except Exception:
                pass
        time.sleep(2)

def get_cached_snapshot() -> dict:
    """HTTP请求直接读缓存，若缓存为空则立即计算一次（非阻塞兜底）"""
    with _snapshot_cache_lock:
        data = _snapshot_cache.get("data")
    if data:
        return data
    # 缓存还没刷进来，尝试快速同步读（不依赖引擎锁，只读DB）
    try:
        return _build_snapshot_now()
    except Exception:
        return {
            "evolve": {"status": "initializing", "live": {}, "generations": [],
                       "candidates": [], "best_curve": [], "strategy_dist": [], "logs": []},
            "autorun": {"status": "initializing", "tasks": [], "metrics": [], "summary": {}},
            "system": {"cpu": 0, "mem": 0, "server_time": datetime.now().isoformat(),
                       "evolve_running": False, "autorun_running": False}
        }


def _start_evolve():
    """在独立线程中安全启动进化引擎"""
    global _evolve_ctrl
    _log_file = BASE_DIR / "evolve_start.log"
    with _evolve_lock:
        if _evolve_ctrl is not None:
            return
        try:
            _log_file.write_text("starting...\n", encoding='utf-8')
            sys.path.insert(0, str(BASE_DIR))
            from autoresearch_self_evolve import SelfEvolveController, init_db as evolve_init_db
            _log_file.write_text("imported ok\n", encoding='utf-8')
            evolve_init_db()
            _log_file.write_text("db init ok\n", encoding='utf-8')
            ctrl = SelfEvolveController()
            _evolve_ctrl = ctrl   # 先赋值，让快照立即可读
            _log_file.write_text("ctrl created, starting thread\n", encoding='utf-8')
            t = threading.Thread(target=ctrl.run_forever, daemon=True, name="EvolveEngine")
            t.start()
            _log_file.write_text(f"thread started: {t.ident}\n", encoding='utf-8')
        except Exception as e:
            import traceback
            _log_file.write_text(f"ERROR: {e}\n{traceback.format_exc()}\n", encoding='utf-8')


def _start_autorun():
    """在独立线程中安全启动自动运行引擎"""
    global _autorun_engine
    with _autorun_lock:
        if _autorun_engine is not None:
            return
        try:
            from autoresearch_autorun import AutoRunEngine
            eng = AutoRunEngine()
            eng.start()
            _autorun_engine = eng
            sys.stdout.buffer.write(b"[Unified] Autorun engine started\n")
            sys.stdout.buffer.flush()
        except Exception as e:
            err_msg = f"[Unified] Autorun engine failed: {e}\n"
            sys.stdout.buffer.write(err_msg.encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()


# ── 读取进化系统快照 ─────────────────────────────────────────────────────────

def read_evolve_snapshot() -> dict:
    if not EVOLVE_DB.exists():
        return {"generations": [], "candidates": [], "metrics": [],
                "versions": [], "logs": [], "summary": {}, "best_curve": [],
                "strategy_dist": [], "status": "waiting"}
    try:
        con = sqlite3.connect(str(EVOLVE_DB), timeout=2.0)
        con.row_factory = sqlite3.Row

        generations = [dict(r) for r in con.execute(
            "SELECT * FROM generations ORDER BY generation DESC LIMIT 30"
        ).fetchall()]

        candidates = [dict(r) for r in con.execute(
            "SELECT * FROM candidates ORDER BY generation DESC, score DESC LIMIT 100"
        ).fetchall()]

        metrics = [dict(r) for r in con.execute(
            "SELECT * FROM evolution_metrics ORDER BY ts DESC LIMIT 80"
        ).fetchall()]
        metrics.reverse()

        versions = [dict(r) for r in con.execute(
            "SELECT * FROM algorithm_versions ORDER BY generation DESC LIMIT 10"
        ).fetchall()]

        logs = [dict(r) for r in con.execute(
            "SELECT * FROM evolution_log ORDER BY ts DESC LIMIT 60"
        ).fetchall()]
        logs.reverse()

        summary_row = con.execute("""
            SELECT
                MAX(generation) AS current_gen,
                COUNT(DISTINCT generation) AS total_gens,
                MAX(best_score) AS global_best,
                (SELECT COUNT(*) FROM candidates) AS total_candidates,
                (SELECT COUNT(*) FROM algorithm_versions) AS total_versions
            FROM generations
        """).fetchone()
        summary = dict(summary_row) if summary_row else {}

        best_curve = [dict(r) for r in con.execute(
            "SELECT generation, best_score, avg_score, improvement, diversity FROM evolution_metrics ORDER BY ts"
        ).fetchall()]

        strategy_dist = [dict(r) for r in con.execute(
            "SELECT strategy_name, COUNT(*) as cnt, AVG(score) as avg_score "
            "FROM candidates WHERE score > 0 GROUP BY strategy_name ORDER BY avg_score DESC"
        ).fetchall()]

        con.close()

        # 实时状态从内存控制器获取
        ctrl = _evolve_ctrl
        status = "running" if (ctrl and not ctrl.stop_event.is_set()) else "stopped"
        live = {}
        if ctrl:
            # 计算策略权重排行（供 Dashboard 展示）
            strat_weights = {}
            for s in getattr(ctrl, "_strategy_scores", {}):
                cnt   = ctrl._strategy_counts.get(s, 1)
                score = ctrl._strategy_scores.get(s, 0.0)
                strat_weights[s] = round(score / cnt, 4)
            strat_rank = sorted(strat_weights.items(), key=lambda x: x[1], reverse=True)

            live = {
                "current_gen": ctrl.generation,
                "best_score": round(ctrl.best_score, 4),
                "total_improvements": ctrl.total_improvements,
                "total_candidates": ctrl.total_candidates_evaluated,
                "active_genome": ctrl.current_genome,
                "recent_logs": ctrl.logs[-20:] if ctrl.logs else [],
                "strategy_weights": strat_weights,          # {策略名: 平均得分}
                "strategy_rank": strat_rank[:5],            # top-5 策略排行
            }

        return {
            "generations": generations,
            "candidates": candidates,
            "metrics": metrics,
            "versions": versions,
            "logs": logs,
            "summary": summary,
            "best_curve": best_curve,
            "strategy_dist": strategy_dist,
            "status": status,
            "live": live,
            "server_time": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "status": "error", "server_time": datetime.now().isoformat()}


# ── 读取自动运行系统快照 ─────────────────────────────────────────────────────

def read_autorun_snapshot() -> dict:
    engine = _autorun_engine
    if not engine:
        # 尝试从数据库读取历史数据
        if not AUTORUN_DB.exists():
            return {"tasks": [], "metrics": [], "status": "waiting"}
        try:
            con = sqlite3.connect(str(AUTORUN_DB))
            con.row_factory = sqlite3.Row
            tasks = [dict(r) for r in con.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 20"
            ).fetchall()]
            metrics = [dict(r) for r in con.execute(
                "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 60"
            ).fetchall()]
            metrics.reverse()
            con.close()
            return {"tasks": tasks, "metrics": metrics, "status": "db_only"}
        except Exception as e:
            return {"tasks": [], "metrics": [], "status": "error", "error": str(e)}

    # 从内存引擎读取实时数据（非阻塞：acquire超时则用空数据）
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu, mem = 0.0, 0.0

    tasks_data = []
    metrics_data = []
    got_lock = engine.lock.acquire(timeout=1.0)
    try:
        if got_lock:
            for t in engine.tasks.values():
                d = {
                    "task_id": t.task_id,
                    "name": t.name,
                    "status": t.status,
                    "progress": round(t.progress, 1),
                    "best_score": round(t.best_score, 4) if t.best_score and t.best_score != float("-inf") else 0,
                    "current_score": round(t.current_score, 4) if t.current_score else 0,
                    "iterations": t.iterations,
                    "max_iterations": t.max_iterations,
                    "strategy": t.strategy,
                    "log": t.log[-5:] if t.log else [],
                    "run_round": getattr(t, "run_round", 0),
                    "genome_tag": getattr(t, "genome_tag", "default"),
                    "improvement_pct": getattr(t, "improvement_pct", 0.0),
                }
                tasks_data.append(d)
            metrics_data = list(engine.metrics_history)[-60:]
    finally:
        if got_lock:
            engine.lock.release()

    running = sum(1 for t in tasks_data if t["status"] == "running")
    # ✅ 修复：completed_count 从引擎实例读，不从 tasks_data 计数
    completed_count = engine._completed_count

    # 策略分布
    strategy_counts = {}
    for t in tasks_data:
        s = t.get("strategy", "EI")
        strategy_counts[s] = strategy_counts.get(s, 0) + 1

    # ✅ 跨轮次历史
    try:
        round_history = engine.get_round_history()
    except Exception:
        round_history = []

    return {
        "tasks": tasks_data,
        "metrics": [{"ts": m.timestamp, "cpu": m.cpu_usage, "mem": m.memory_usage,
                     "active": m.active_tasks, "completed": m.completed_tasks,
                     "learning_score": m.learning_score,
                     "improvement": m.total_improvements} for m in metrics_data],
        "summary": {
            "running": running,
            "completed_count": completed_count,
            "completed": completed_count,  # 兼容旧字段
            "total": len(tasks_data),
            "cpu": round(cpu, 1),
            "mem": round(mem, 1),
            "current_genome_tag": getattr(engine, "_genome_tag", "default"),
            "learning_score": round(engine._learning_score, 3),
        },
        "strategy_counts": strategy_counts,
        "round_history": round_history,
        "status": "running",
        "server_time": datetime.now().isoformat()
    }


# ── 合并快照（内部计算用，不直接被HTTP调用）──────────────────────────────────

def _build_snapshot_now() -> dict:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu, mem = 0.0, 0.0

    return {
        "evolve": read_evolve_snapshot(),
        "autorun": read_autorun_snapshot(),
        "system": {
            "cpu": round(cpu, 1),
            "mem": round(mem, 1),
            "server_time": datetime.now().isoformat(),
            "evolve_running": _evolve_ctrl is not None and not _evolve_ctrl.stop_event.is_set(),
            "autorun_running": _autorun_engine is not None,
        }
    }


# ── WebSocket 实现 ──────────────────────────────────────────────────────────

_ws_clients = []
_ws_lock = threading.Lock()


def _ws_encode(text: str) -> bytes:
    payload = text.encode("utf-8")
    n = len(payload)
    if n <= 125:
        header = bytes([0x81, n])
    elif n <= 65535:
        header = bytes([0x81, 126]) + struct.pack(">H", n)
    else:
        header = bytes([0x81, 127]) + struct.pack(">Q", n)
    return header + payload


def _ws_handshake(conn: socket.socket, key: str):
    accept = base64.b64encode(
        hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()
    ).decode()
    resp = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    )
    conn.sendall(resp.encode())


def _ws_handle(conn: socket.socket):
    with _ws_lock:
        _ws_clients.append(conn)
    # 立即推送一次（读缓存，不阻塞）
    try:
        conn.sendall(_ws_encode(json.dumps(get_cached_snapshot(), ensure_ascii=False)))
    except Exception:
        pass
    try:
        while True:
            data = conn.recv(256)
            if not data:
                break
    except Exception:
        pass
    finally:
        with _ws_lock:
            if conn in _ws_clients:
                _ws_clients.remove(conn)
        try:
            conn.close()
        except Exception:
            pass


def _ws_broadcast_loop():
    while True:
        time.sleep(2)
        try:
            payload = json.dumps(get_cached_snapshot(), ensure_ascii=False)
        except Exception as e:
            payload = json.dumps({"error": str(e)})
        frame = _ws_encode(payload)
        dead = []
        with _ws_lock:
            for conn in list(_ws_clients):
                try:
                    conn.sendall(frame)
                except Exception:
                    dead.append(conn)
            for c in dead:
                _ws_clients.remove(c)
                try:
                    c.close()
                except Exception:
                    pass


# ── HTTP 请求处理 ─────────────────────────────────────────────────────────

class UnifiedHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]

        # WebSocket 升级
        upgrade = self.headers.get("Upgrade", "").lower()
        conn_hdr = self.headers.get("Connection", "").lower()
        if upgrade == "websocket" and "upgrade" in conn_hdr:
            key = self.headers.get("Sec-WebSocket-Key", "")
            _ws_handshake(self.connection, key)
            t = threading.Thread(target=_ws_handle, args=(self.connection,), daemon=True)
            t.start()
            self.close_connection = False
            return

        if path in ("/", "/index.html"):
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        elif path in ("/v2", "/v2/", "/v2/index.html", "/dashboard_v2"):
            self._serve_file(HTML_V2_FILE, "text/html; charset=utf-8")
        elif path == "/api/snapshot":
            self._serve_json(get_cached_snapshot())
        elif path == "/api/evolve":
            self._serve_json(get_cached_snapshot().get("evolve", {}))

        # ── Dashboard V2：进化摘要（轻量，只含 summary + live + strategy_dist）──
        elif path == "/api/evolve/summary":
            snap = get_cached_snapshot().get("evolve", {})
            ctrl = _evolve_ctrl
            live = snap.get("live", {})
            summary = snap.get("summary", {})
            # 合并 live 字段到摘要，方便前端直接使用
            result = {
                "ok": True,
                "current_gen":       live.get("current_gen",  summary.get("current_gen", 0)),
                "best_score":        live.get("best_score",   summary.get("global_best", 0)),
                "global_best":       summary.get("global_best", live.get("best_score", 0)),
                "total_gens":        summary.get("total_gens", 0),
                "total_candidates":  summary.get("total_candidates", live.get("total_candidates", 0)),
                "total_improvements":live.get("total_improvements", 0),
                "best_strategy":     (snap.get("strategy_dist") or [{}])[0].get("strategy_name", "—"),
                "status":            snap.get("status", "unknown"),
                "strategy_dist":     snap.get("strategy_dist", []),
                "active_genome":     live.get("active_genome", {}),
            }
            self._serve_json(result)

        # ── Dashboard V2：最优配置（best_config + 解释）────────────────────────
        elif path == "/api/evolve/best_config":
            snap = get_cached_snapshot().get("evolve", {})
            live = snap.get("live", {})
            genome = live.get("active_genome", {})
            best_score = live.get("best_score", snap.get("summary", {}).get("global_best", 0))
            # 尝试从 MCP 模块读取 top-5
            top5 = []
            try:
                ctrl = _evolve_ctrl
                if ctrl:
                    strat_rank = live.get("strategy_rank", [])
                    top5 = [{"strategy": s, "avg_score": v} for s, v in strat_rank[:5]]
            except Exception:
                pass
            self._serve_json({
                "ok": True,
                "best_score": best_score,
                "genome": genome,
                "top5_candidates": top5,
                "explanation": {k: f"当前最优值: {v}" for k, v in genome.items()} if genome else {},
            })

        # ── Dashboard V2：进化历史曲线（支持 ?limit=N）────────────────────────
        elif path.startswith("/api/evolve/history"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            limit = int(qs.get("limit", ["100"])[0])
            snap = get_cached_snapshot().get("evolve", {})
            best_curve = snap.get("best_curve", [])
            if limit and len(best_curve) > limit:
                best_curve = best_curve[-limit:]
            candidates = snap.get("candidates", [])[:limit]
            self._serve_json({
                "ok": True,
                "best_curve":  best_curve,
                "candidates":  candidates,
                "total":       len(snap.get("best_curve", [])),
            })

        # ── Dashboard V2：Drift 摘要（漂移事件概览）──────────────────────────
        elif path == "/api/drift/summary":
            ctrl = _evolve_ctrl
            adapter = getattr(ctrl, "_drift_adapter", None) if ctrl else None
            if adapter:
                try:
                    events = list(getattr(adapter.detector, "events", []))
                    last_event = events[-1].__dict__ if events else None
                    self._serve_json({
                        "ok": True,
                        "total_events":   len(events),
                        "last_event":     last_event,
                        "perf_baseline":  getattr(adapter.perf_monitor, "_baseline", None),
                        "reopt_count":    len(getattr(adapter.reoptimizer, "_history", [])),
                    })
                except Exception as e:
                    self._serve_json({"ok": False, "error": str(e)})
            else:
                # 无 adapter 时返回空摘要（不报错）
                self._serve_json({
                    "ok": True,
                    "total_events": 0,
                    "last_event": None,
                    "perf_baseline": None,
                    "reopt_count": 0,
                    "msg": "drift adapter not attached",
                })

        elif path == "/api/autorun":
            self._serve_json(get_cached_snapshot().get("autorun", {}))
        elif path == "/api/autorun/rounds":
            # 跨轮次历史（可选 ?name=xxx 筛选任务名）
            eng = _autorun_engine
            if eng:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                name = qs.get("name", [None])[0]
                self._serve_json(eng.get_round_history(name))
            else:
                self._serve_json([])
        elif path == "/api/status":
            self._serve_json({
                "evolve_running": _evolve_ctrl is not None,
                "autorun_running": _autorun_engine is not None,
                "server_time": datetime.now().isoformat()
            })
        # ── 改进9：通知测试接口 ───────────────────────────────────────────────
        elif path == "/api/notify/test":
            try:
                from autoresearch_notify import get_notifier
                n = get_notifier()
                n.on_new_best(gen=0, score=0.999, genome_hint="测试通知 · 系统运行正常")
                self._serve_json({"ok": True, "backend": n._backend_name,
                                  "msg": f"通知已发送，后端={n._backend_name}"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})
        # ── 改进4：并行基准测试接口 ───────────────────────────────────────────
        elif path == "/api/parallel/benchmark":
            def _run_bench():
                try:
                    from autoresearch_parallel import benchmark_comparison
                    return benchmark_comparison(n_steps=8, batch_size=4, n_workers=4)
                except Exception as e:
                    return {"error": str(e)}
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_run_bench)
                try:
                    result = fut.result(timeout=120)
                except Exception as e:
                    result = {"error": str(e)}
            self._serve_json(result)
        # ── 改进1：BOHB 多保真度基准测试 ──────────────────────────────────────
        elif path == "/api/bohb/benchmark":
            def _run_bohb():
                try:
                    from autoresearch_bohb import benchmark_bohb_vs_random
                    return benchmark_bohb_vs_random(n_random=27, budget=27)
                except Exception as e:
                    return {"error": str(e)}
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_run_bohb)
                try:
                    result = fut.result(timeout=180)
                except Exception as e:
                    result = {"error": str(e)}
            self._serve_json(result)
        # ── 改进2：LLM 暖启动测试 ─────────────────────────────────────────────
        elif path == "/api/warmstart/test":
            def _run_ws():
                try:
                    from autoresearch_llm_warmstart import LLMWarmStarter, HeuristicPrior
                    bounds = {"x1": (-5.0, 10.0), "x2": (0.0, 15.0)}
                    ws = LLMWarmStarter(fallback_to_heuristic=True)
                    pts = ws.suggest(bounds, n=5, task_desc="暖启动测试")
                    mode = "llm" if ws.llm.is_available() else "heuristic"
                    return {
                        "ok": True, "mode": mode,
                        "n_points": len(pts),
                        "points": pts[:3],   # 只返回前3个避免响应过大
                        "msg": f"暖启动成功，模式={mode}，生成 {len(pts)} 个初始点"
                    }
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_run_ws)
                try:
                    result = fut.result(timeout=60)
                except Exception as e:
                    result = {"ok": False, "error": str(e)}
            self._serve_json(result)
        # ── 改进3：PBT-ASHA 早停基准测试 ──────────────────────────────────────
        elif path == "/api/pbt/benchmark":
            def _run_pbt():
                try:
                    from autoresearch_pbt_asha import benchmark_pbt_asha
                    return benchmark_pbt_asha(population_size=6, max_resource=18)
                except Exception as e:
                    return {"error": str(e)}
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_run_pbt)
                try:
                    result = fut.result(timeout=120)
                except Exception as e:
                    result = {"error": str(e)}
            self._serve_json(result)

        # ── 漂移检测状态 ────────────────────────────────────────────────────
        elif path == "/api/drift/status":
            try:
                ctrl = _evolve_ctrl
                adapter = getattr(ctrl, "_drift_adapter", None) if ctrl else None
                if adapter:
                    self._serve_json({"ok": True, **adapter.status()})
                else:
                    self._serve_json({"ok": True, "msg": "drift adapter not attached",
                                      "drift": {}, "perf": {}, "reopt": {}})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 实验版本管理：列表 ───────────────────────────────────────────────
        elif path == "/api/experiments/list":
            try:
                from autoresearch_version import api_list
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                tag   = qs.get("tag",  [None])[0]
                limit = int(qs.get("limit", ["50"])[0])
                sort  = qs.get("sort_by", ["score"])[0]
                self._serve_json(api_list(tag=tag, limit=limit, sort_by=sort))
            except Exception as e:
                self._serve_json({"error": str(e)})

        # ── 实验版本管理：排行榜 ─────────────────────────────────────────────
        elif path == "/api/experiments/leaderboard":
            try:
                from autoresearch_version import api_leaderboard
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                top_n = int(qs.get("top_n", ["10"])[0])
                self._serve_json(api_leaderboard(top_n=top_n))
            except Exception as e:
                self._serve_json({"error": str(e)})

        # ── 实验版本管理：对比 ───────────────────────────────────────────────
        elif path == "/api/experiments/compare":
            try:
                from autoresearch_version import api_compare
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                id1 = qs.get("id1", [""])[0]
                id2 = qs.get("id2", [""])[0]
                self._serve_json(api_compare(id1, id2))
            except Exception as e:
                self._serve_json({"error": str(e)})

        # ── 实验版本管理：详情 ───────────────────────────────────────────────
        elif path == "/api/experiments/get":
            try:
                from autoresearch_version import api_get
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                exp_id = qs.get("exp_id", [""])[0]
                self._serve_json(api_get(exp_id))
            except Exception as e:
                self._serve_json({"error": str(e)})

        # ── 超参数重要性分析 ─────────────────────────────────────────────────
        elif path == "/api/importance/analyze":
            def _run_importance():
                try:
                    from autoresearch_importance import ImportanceReport
                    from autoresearch_version import get_store
                    qs = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
                    top_n = int(qs.get("top_n", ["8"])[0])
                    store = get_store()
                    records = store.query(sort_by="ts", ascending=True, limit=500)
                    if not records:
                        return {"ok": False, "error": "没有实验记录（请先运行优化）"}
                    configs = [r.config for r in records]
                    scores  = [r.score  for r in records]
                    rpt = ImportanceReport(use_shap=False)
                    return rpt.analyze(configs, scores, top_n=top_n)
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_run_importance)
                try:
                    result = fut.result(timeout=60)
                except Exception as e:
                    result = {"ok": False, "error": str(e)}
            self._serve_json(result)

        # ── 网络学习：状态查询（GET）─────────────────────────────────────────
        elif path == "/api/web_learning/status":
            try:
                ctrl = _evolve_ctrl
                ie   = getattr(ctrl, "_insight_engine", None) if ctrl else None
                wl   = getattr(ie,   "_web_learner",    None) if ie   else None
                if wl:
                    self._serve_json({"ok": True, **wl.get_knowledge_summary()})
                else:
                    self._serve_json({"ok": False, "status": "not_attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 知识来源评分（KnowledgeRater）────────────────────────────────────
        elif path == "/api/web_learning/source_ratings":
            try:
                ctrl = _evolve_ctrl
                ie   = getattr(ctrl, "_insight_engine", None) if ctrl else None
                wl   = getattr(ie,   "_web_learner",    None) if ie   else None
                if wl:
                    self._serve_json({"ok": True, "ratings": wl.get_source_ratings(),
                                      "summary": wl.get_knowledge_summary_v2()})
                else:
                    self._serve_json({"ok": False, "status": "not_attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 参数重要性（独立路由，优先级高，从 DB 直接计算）────────────────────
        elif path == "/api/enhancements/param_importance":
            import json as _json2, math as _math2
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    try:
                        summary = hub.param_imp.get_summary()
                        if summary.get("status") == "ok" and summary.get("importance"):
                            self._serve_json({"ok": True, **summary})
                            return
                    except Exception:
                        pass
                # 从 evolution_monitor.db 直接计算 Pearson 重要性
                con2 = sqlite3.connect(str(EVOLVE_DB), timeout=5.0)
                rows2 = con2.execute(
                    "SELECT config, score FROM candidates WHERE score > 0 AND config IS NOT NULL AND config != '' ORDER BY created_at DESC LIMIT 500"
                ).fetchall()
                con2.close()
                if len(rows2) < 5:
                    self._serve_json({"ok": True, "status": "no_data", "importance": {}})
                    return
                NUM_K = ["ucb_kappa", "ei_xi", "length_scale", "n_candidates", "n_random_init"]
                pv = {k: [] for k in NUM_K}
                sl = []
                for cs, sc in rows2:
                    try:
                        c2 = _json2.loads(cs) if isinstance(cs, str) else cs
                        sl.append(float(sc))
                        for k in NUM_K:
                            pv[k].append(float(c2.get(k, 0)))
                    except Exception:
                        continue
                if len(sl) < 5:
                    self._serve_json({"ok": True, "status": "no_data", "importance": {}})
                    return
                def _pcorr(xs, ys):
                    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
                    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
                    return abs(num / (_math2.sqrt(sum((x-mx)**2 for x in xs)+1e-12) * _math2.sqrt(sum((y-my)**2 for y in ys)+1e-12)))
                imp2 = {k: round(_pcorr(pv[k], sl), 4) for k in NUM_K if len(pv[k]) == len(sl)}
                mx2 = max(imp2.values()) if imp2 else 1.0
                if mx2 > 0: imp2 = {k: round(v/mx2, 4) for k, v in imp2.items()}
                si = sorted(imp2.items(), key=lambda x: x[1], reverse=True)
                self._serve_json({"ok": True, "status": "ok", "source": "pearson_proxy",
                                  "sample_size": len(sl),
                                  "importance": dict(si),
                                  "top_params": [k for k,v in si[:3]],
                                  "low_importance_params": [k for k,v in si if v < 0.15]})
            except Exception as e2:
                self._serve_json({"ok": False, "status": "error", "error": str(e2), "importance": {}})

        # ── 多目标优化：Pareto 前沿摘要 ──────────────────────────────────────
        elif path == "/api/enhancements/multi_objective":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    self._serve_json({"ok": True, **hub.multi_obj.get_summary()})
                else:
                    # 降级：从DB读取历史数据
                    from autoresearch_enhancements import MultiObjectiveTracker
                    tracker = MultiObjectiveTracker.load_from_db()
                    self._serve_json({"ok": True, "offline": True, **tracker.get_summary()})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 参数重要性热力图数据 ───────────────────────────────────────────────
        # ── A/B 对比：快照列表 ────────────────────────────────────────────────
        elif path == "/api/enhancements/ab_snapshots":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    self._serve_json({"ok": True, **hub.ab_compare.get_summary()})
                else:
                    self._serve_json({"ok": False, "status": "not_attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── Drift 联动：响应历史 ──────────────────────────────────────────────
        elif path == "/api/enhancements/drift_responses":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    self._serve_json({"ok": True, **hub.drift_resp.get_summary()})
                else:
                    self._serve_json({"ok": False, "status": "not_attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 增强模块全量摘要 ──────────────────────────────────────────────────
        elif path == "/api/enhancements/summary":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    self._serve_json({"ok": True, **hub.get_full_summary()})
                else:
                    self._serve_json({"ok": False, "status": "not_attached",
                                      "msg": "增强模块未挂载，请先启动进化服务"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def do_POST(self):
        """✅ 任务控制 API：pause / resume / restart"""
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}

        eng = _autorun_engine
        if not eng:
            self._serve_json({"ok": False, "error": "autorun engine not running"})
            return

        task_id = body.get("task_id", "")

        if path == "/api/autorun/pause":
            ok = eng.pause_task(task_id)
            self._serve_json({"ok": ok, "task_id": task_id})

        elif path == "/api/autorun/resume":
            ok = eng.resume_task(task_id)
            self._serve_json({"ok": ok, "task_id": task_id})

        elif path == "/api/autorun/restart":
            new_tid = eng.restart_task(task_id)
            self._serve_json({"ok": bool(new_tid), "new_task_id": new_tid})

        # ── 漂移检测：推送新得分 ─────────────────────────────────────────────
        elif path == "/api/drift/push":
            try:
                score = float(body.get("score", 0.0))
                ctrl = _evolve_ctrl
                adapter = getattr(ctrl, "_drift_adapter", None) if ctrl else None
                if adapter:
                    evt = adapter.detector.push(score)
                    warn = adapter.perf_monitor.push(score)
                    self._serve_json({
                        "ok": True, "score": score,
                        "drift_detected": evt is not None,
                        "drift_event": evt.__dict__ if evt else None,
                        "perf_warning": warn,
                    })
                else:
                    self._serve_json({"ok": True, "msg": "drift adapter not attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 漂移检测：手动触发重优化 ─────────────────────────────────────────
        elif path == "/api/drift/reoptimize":
            try:
                ctrl = _evolve_ctrl
                adapter = getattr(ctrl, "_drift_adapter", None) if ctrl else None
                if adapter:
                    rec = adapter.reoptimizer.trigger("manual", trigger_type="manual")
                    self._serve_json({
                        "ok": True,
                        "record": {"ts": rec.ts, "trigger": rec.trigger,
                                   "result": rec.result} if rec else None,
                    })
                else:
                    self._serve_json({"ok": False, "error": "drift adapter not attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 实验记录：提交单次实验 ───────────────────────────────────────────
        elif path == "/api/experiments/record":
            try:
                from autoresearch_version import record_experiment
                config     = body.get("config", {})
                score      = float(body.get("score", 0.0))
                tag        = body.get("tag", "api")
                n_iter     = int(body.get("n_iter", 0))
                duration_s = float(body.get("duration_s", 0.0))
                notes      = body.get("notes", "")
                exp_id = record_experiment(
                    config=config, score=score, tag=tag,
                    n_iter=n_iter, duration_s=duration_s, notes=notes,
                )
                self._serve_json({"ok": True, "exp_id": exp_id})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 实验记录：更新备注 ───────────────────────────────────────────────
        elif path == "/api/experiments/notes":
            try:
                from autoresearch_version import get_store
                exp_id = body.get("exp_id", "")
                notes  = body.get("notes", "")
                ok = get_store().update_notes(exp_id, notes)
                self._serve_json({"ok": ok})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 网络学习：强制触发（POST）────────────────────────────────────────
        elif path == "/api/web_learning/trigger":
            # POST body 可带 {"gen": 当前代数}
            try:
                ctrl = _evolve_ctrl
                ie   = getattr(ctrl, "_insight_engine", None) if ctrl else None
                wl   = getattr(ie,   "_web_learner",    None) if ie   else None
                if wl:
                    gen = body.get("gen", getattr(ctrl, "current_gen", 0)) if isinstance(body, dict) else 0
                    result = wl.force_learn_now(gen=gen)
                    self._serve_json({"ok": True, "result": result,
                                      "message": "后台网络学习已启动，请稍后通过 GET /api/web_learning/status 查看结果"})
                else:
                    self._serve_json({"ok": False, "status": "web_learner_not_attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── A/B 对比：保存当前配置快照（POST）──────────────────────────────────
        elif path == "/api/enhancements/ab/save_snapshot":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    label = body.get("label", "")
                    notes = body.get("notes", "")
                    snap_id = hub.ab_compare.save_snapshot(label=label, notes=notes)
                    self._serve_json({"ok": True, "snap_id": snap_id, "label": label})
                else:
                    self._serve_json({"ok": False, "error": "enhancement hub not attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── A/B 对比：执行两组配置对比（POST）──────────────────────────────────
        elif path == "/api/enhancements/ab/compare":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    snap_a = body.get("snap_id_a", "")
                    snap_b = body.get("snap_id_b", "")
                    n_trials = int(body.get("n_trials", 30))
                    result = hub.ab_compare.compare(snap_a, snap_b, n_trials=n_trials)
                    self._serve_json({"ok": True, **result})
                else:
                    self._serve_json({"ok": False, "error": "enhancement hub not attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        # ── 多目标：记录一次评估点（POST）──────────────────────────────────────
        elif path == "/api/enhancements/mo/record":
            try:
                ctrl = _evolve_ctrl
                hub  = getattr(ctrl, "_enhancement_hub", None) if ctrl else None
                if hub:
                    gen     = int(body.get("gen", 0))
                    score   = float(body.get("score", 0.0))
                    speed   = float(body.get("speed", 1.0))
                    mem_mb  = float(body.get("mem_mb", 0.0))
                    cand_id = body.get("cand_id", f"manual_{gen}")
                    hub.multi_obj.record(cand_id=cand_id, gen=gen,
                                         score=score, speed=speed, mem_mb=mem_mb)
                    self._serve_json({"ok": True, "msg": "recorded"})
                else:
                    self._serve_json({"ok": False, "error": "enhancement hub not attached"})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _serve_file(self, fp: Path, mime: str):
        if not fp.exists():
            self.send_response(503)
            self.end_headers()
            self.wfile.write(f"File not found: {fp}".encode())
            return
        content = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ── 主入口 ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  AutoResearch Unified Server v2.0")
    print("  " + "-" * 45)
    print(f"  http://localhost:{PORT}/")
    print("  " + "-" * 45)
    print("  Evolve Engine + Autorun Engine")
    print("=" * 60)

    # 启动两个引擎（各自独立后台线程，不阻塞主线程）
    print("[Init] Starting evolve engine (background)...")
    threading.Thread(target=_start_evolve, daemon=True, name="EvolveStarter").start()

    print("[Init] Starting autorun engine (background)...")
    threading.Thread(target=_start_autorun, daemon=True, name="AutorunStarter").start()

    # 启动 WebSocket 广播
    threading.Thread(target=_refresh_snapshot_loop, daemon=True, name="SnapshotRefresh").start()
    threading.Thread(target=_ws_broadcast_loop, daemon=True, name="WSBroadcast").start()

    # 启动 HTTP 服务器
    server = ThreadingHTTPServer(("0.0.0.0", PORT), UnifiedHandler)
    print(f"[Server] 监听 0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] 收到停止信号，退出")


if __name__ == "__main__":
    main()
