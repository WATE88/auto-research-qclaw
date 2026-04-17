"""
AutoResearch 监控服务器
=======================
- HTTP 服务：提供静态 HTML 界面
- WebSocket：实时推送任务状态、指标数据
- REST API：供前端查询历史数据
"""

import json
import sqlite3
import threading
import time
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import socket

# 引入自动运行引擎
from autoresearch_autorun import AutoRunEngine


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """每个请求在独立线程中处理，防止 WS 长连接阻塞 HTTP 请求"""
    daemon_threads = True

# ─────────────────────────────────────────────
# WebSocket 极简实现（无需第三方库）
# ─────────────────────────────────────────────

import struct
import base64
import hashlib


class WebSocketConnection:
    MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.closed = False

    def handshake(self, headers: dict) -> bool:
        key = headers.get("Sec-WebSocket-Key", "").strip()
        if not key:
            return False
        accept = base64.b64encode(
            hashlib.sha1((key + self.MAGIC).encode()).digest()
        ).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        self.conn.sendall(response.encode())
        return True

    def send(self, text: str):
        if self.closed:
            return
        try:
            data = text.encode("utf-8")
            length = len(data)
            if length <= 125:
                header = struct.pack("BB", 0x81, length)
            elif length <= 65535:
                header = struct.pack("!BBH", 0x81, 126, length)
            else:
                header = struct.pack("!BBQ", 0x81, 127, length)
            self.conn.sendall(header + data)
        except Exception:
            self.closed = True

    def recv(self):
        """读取一帧，返回文本或 None（连接关闭）"""
        try:
            raw = self.conn.recv(2)
            if not raw or len(raw) < 2:
                return None
            b1, b2 = raw
            opcode = b1 & 0x0F
            if opcode == 0x8:   # close
                return None
            masked = (b2 & 0x80) != 0
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.conn.recv(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.conn.recv(8))[0]
            mask = self.conn.recv(4) if masked else None
            payload = self.conn.recv(length)
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            return payload.decode("utf-8", errors="ignore")
        except Exception:
            return None

    def close(self):
        self.closed = True
        try:
            self.conn.close()
        except Exception:
            pass


# ─────────────────────────────────────────────
# 全局状态
# ─────────────────────────────────────────────

_engine: AutoRunEngine = None
_ws_clients: list = []
_ws_lock = threading.Lock()


def _broadcast(data: dict):
    text = json.dumps(data, ensure_ascii=False)
    with _ws_lock:
        dead = []
        for ws in _ws_clients:
            ws.send(text)
            if ws.closed:
                dead.append(ws)
        for d in dead:
            _ws_clients.remove(d)


def _push_loop():
    """每1秒向所有 WS 客户端推送最新数据"""
    while True:
        try:
            with _ws_lock:
                if not _ws_clients:
                    time.sleep(1)
                    continue
            payload = _build_push_payload()
            _broadcast(payload)
        except Exception as e:
            pass
        time.sleep(1)


def _build_push_payload() -> dict:
    """从数据库读取最新数据，构建推送包"""
    conn = sqlite3.connect(AutoRunEngine.DB_PATH)
    c = conn.cursor()

    # 任务列表
    c.execute("""
        SELECT task_id,name,status,progress,best_score,current_score,
               iterations,max_iterations,strategy,start_time,end_time,log
        FROM tasks ORDER BY rowid DESC LIMIT 20
    """)
    rows = c.fetchall()
    tasks = []
    for r in rows:
        try:
            log = json.loads(r[11]) if r[11] else []
        except Exception:
            log = []
        tasks.append({
            "task_id": r[0], "name": r[1], "status": r[2],
            "progress": round(r[3], 1),
            "best_score": round(r[4], 4) if r[4] is not None and r[4] != float("-inf") else None,
            "current_score": round(r[5], 4) if r[5] is not None else None,
            "iterations": r[6], "max_iterations": r[7],
            "strategy": r[8], "start_time": r[9],
            "end_time": r[10], "log": log,
        })

    # 最近指标（最近60条用于图表）
    c.execute("""
        SELECT timestamp,cpu_usage,memory_usage,active_tasks,
               completed_tasks,total_improvements,learning_score
        FROM metrics ORDER BY id DESC LIMIT 60
    """)
    metrics_rows = list(reversed(c.fetchall()))
    metrics = [
        {
            "ts": r[0], "cpu": round(r[1], 1), "mem": round(r[2], 1),
            "active": r[3], "completed": r[4],
            "improvement": round(r[5], 2), "learning": round(r[6], 4),
        }
        for r in metrics_rows
    ]

    # 系统状态
    c.execute("SELECT key,value FROM system_status")
    status = {r[0]: r[1] for r in c.fetchall()}
    conn.close()

    return {"type": "update", "tasks": tasks, "metrics": metrics, "status": status}


# ─────────────────────────────────────────────
# HTTP 处理器
# ─────────────────────────────────────────────

DASHBOARD_HTML = None   # 将在启动时读入


class MonitorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/snapshot":
            self._serve_json(_build_push_payload())
        elif path == "/ws":
            self._handle_ws_upgrade()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        html = DASHBOARD_HTML.encode("utf-8") if DASHBOARD_HTML else b"<h1>Loading...</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _serve_json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ws_upgrade(self):
        headers = {}
        for line in self.headers:
            headers[line] = self.headers[line]

        ws = WebSocketConnection(self.connection, self.client_address)
        if not ws.handshake(headers):
            self.send_response(400)
            self.end_headers()
            return

        # 告知框架不要在此线程之后关闭连接
        self.close_connection = False

        with _ws_lock:
            _ws_clients.append(ws)

        # 立即推送一次全量数据
        try:
            ws.send(json.dumps(_build_push_payload(), ensure_ascii=False))
        except Exception:
            pass

        # 保持连接，等待客户端关闭（ThreadingHTTPServer 中此线程是独立的）
        while True:
            msg = ws.recv()
            if msg is None:
                break

        with _ws_lock:
            if ws in _ws_clients:
                _ws_clients.remove(ws)
        ws.close()


# ─────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────

def start_server(port: int = 8899, open_browser: bool = True):
    global DASHBOARD_HTML, _engine

    # 读取 HTML
    html_path = os.path.join(os.path.dirname(__file__), "autoresearch_dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        DASHBOARD_HTML = f.read()

    # 启动引擎
    _engine = AutoRunEngine()
    _engine.start()

    # 启动推送线程
    threading.Thread(target=_push_loop, daemon=True, name="ws-push").start()

    # 启动 HTTP 服务器（多线程版）
    server = ThreadingHTTPServer(("0.0.0.0", port), MonitorHandler)
    url = f"http://localhost:{port}"
    print(f"\n{'='*55}")
    print(f"  AutoResearch 实时监控中心已启动")
    print(f"  访问地址: {url}")
    print(f"  按 Ctrl+C 停止")
    print(f"{'='*55}\n")

    if open_browser:
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止...")
        _engine.stop()
        server.shutdown()
        print("已停止。")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    start_server(port)
