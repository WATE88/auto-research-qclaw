"""
AutoResearch 自主进化监控服务器 v1.0
======================================
- 端口 8900
- /                  → evolution_dashboard.html
- /api/snapshot      → 完整进化快照 JSON
- WebSocket /ws      → 每秒广播实时数据
"""

import json, os, sqlite3, threading, time, hashlib, base64, struct, socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT      = 8900
DB_PATH   = Path(__file__).parent / "evolution_monitor.db"
HTML_FILE = Path(__file__).parent / "evolution_dashboard.html"

# ── 数据读取 ───────────────────────────────────────────────────────────────

def read_snapshot() -> dict:
    if not DB_PATH.exists():
        return {"generations": [], "candidates": [], "metrics": [],
                "versions": [], "logs": [], "summary": {}}
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.row_factory = sqlite3.Row

        generations = [dict(r) for r in con.execute(
            "SELECT * FROM generations ORDER BY generation DESC LIMIT 50"
        ).fetchall()]

        candidates = [dict(r) for r in con.execute(
            "SELECT * FROM candidates ORDER BY generation DESC, score DESC LIMIT 200"
        ).fetchall()]

        metrics = [dict(r) for r in con.execute(
            "SELECT * FROM evolution_metrics ORDER BY ts DESC LIMIT 120"
        ).fetchall()]
        metrics.reverse()

        versions = [dict(r) for r in con.execute(
            "SELECT * FROM algorithm_versions ORDER BY generation DESC LIMIT 20"
        ).fetchall()]

        logs = [dict(r) for r in con.execute(
            "SELECT * FROM evolution_log ORDER BY ts DESC LIMIT 100"
        ).fetchall()]
        logs.reverse()

        summary_row = con.execute("""
            SELECT
                MAX(generation) AS current_gen,
                COUNT(DISTINCT generation) AS total_gens,
                MAX(best_score) AS global_best,
                (SELECT COUNT(*) FROM candidates) AS total_candidates,
                (SELECT COUNT(*) FROM algorithm_versions) AS total_versions,
                (SELECT config FROM algorithm_versions WHERE active=1 ORDER BY generation DESC LIMIT 1) AS active_config
            FROM generations
        """).fetchone()
        summary = dict(summary_row) if summary_row else {}

        # 计算历代最佳曲线
        best_curve = [dict(r) for r in con.execute(
            "SELECT generation, best_score, improvement FROM generations ORDER BY generation"
        ).fetchall()]

        # 策略分布
        strategy_dist = [dict(r) for r in con.execute(
            "SELECT strategy_name, COUNT(*) as cnt, AVG(score) as avg_score "
            "FROM candidates WHERE score > 0 GROUP BY strategy_name ORDER BY avg_score DESC"
        ).fetchall()]

        con.close()
        return {
            "generations": generations,
            "candidates": candidates,
            "metrics": metrics,
            "versions": versions,
            "logs": logs,
            "summary": summary,
            "best_curve": best_curve,
            "strategy_dist": strategy_dist,
            "server_time": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "server_time": datetime.now().isoformat()}


# ── WebSocket 广播 ─────────────────────────────────────────────────────────

ws_clients = []
ws_lock    = threading.Lock()

def ws_broadcast_loop():
    while True:
        time.sleep(1)
        data = json.dumps(read_snapshot())
        frame = _ws_encode(data)
        dead  = []
        with ws_lock:
            for conn in ws_clients:
                try:
                    conn.sendall(frame)
                except Exception:
                    dead.append(conn)
            for c in dead:
                ws_clients.remove(c)
                try: c.close()
                except Exception: pass

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
        __import__("hashlib").sha1(
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

def handle_ws(conn: socket.socket):
    with ws_lock:
        ws_clients.append(conn)
    try:
        while True:
            data = conn.recv(256)
            if not data:
                break
    except Exception:
        pass
    finally:
        with ws_lock:
            if conn in ws_clients:
                ws_clients.remove(conn)
        try: conn.close()
        except Exception: pass


# ── HTTP 请求处理 ─────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默日志

    def do_GET(self):
        path = self.path.split("?")[0]

        # WebSocket 升级
        if (self.headers.get("Upgrade","").lower() == "websocket" and
                self.headers.get("Connection","").lower() in ("upgrade", "keep-alive, upgrade")):
            key = self.headers.get("Sec-WebSocket-Key", "")
            _ws_handshake(self.connection, key)
            t = threading.Thread(target=handle_ws, args=(self.connection,), daemon=True)
            t.start()
            return

        if path == "/" or path == "/index.html":
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        elif path == "/api/snapshot":
            self._serve_json(read_snapshot())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _serve_file(self, fp: Path, mime: str):
        if not fp.exists():
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Dashboard not ready")
            return
        content = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ── 主入口 ────────────────────────────────────────────────────────────────

def main():
    print(f"[Server] 进化监控服务器启动在 http://localhost:{PORT}")
    threading.Thread(target=ws_broadcast_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[Server] 停止")


if __name__ == "__main__":
    main()
