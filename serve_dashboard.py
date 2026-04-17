#!/usr/bin/env python3
"""
serve_dashboard.py — AutoResearch 实时看板 HTTP 服务器
自动从 _evolution.jsonl 读取数据，前端每 3 秒轮询更新
"""
import os, sys, io, json, http.server, threading, time
from pathlib import Path
from datetime import datetime

# ── UTF-8 ──────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
for _s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        if hasattr(_s, "buffer"):
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
            break
    except: pass

ROOT = Path(__file__).parent
PORT = 18788  # 避开 QClaw 的 18789

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>🧬 AutoResearch 实时监控</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; padding: 20px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #21262d; }
.header h1 { font-size: 1.5rem; color: #58a6ff; }
.live-dot { display: inline-block; width: 10px; height: 10px; background: #3fb950; border-radius: 50%; margin-right: 6px; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(0.8)} }
.badge { background: #161b22; border: 1px solid #30363d; border-radius: 20px; padding: 4px 12px; font-size: 0.8rem; color: #8b949e; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 16px; text-align: center; transition: border-color 0.3s; }
.stat-card:hover { border-color: #388bfd; }
.stat-card .label { font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-card .value { font-size: 1.6rem; font-weight: 700; margin: 6px 0 2px; }
.stat-card.up .value { color: #3fb950; }
.stat-card.hot .value { color: #f78166; }
.stat-card.time .value { color: #d29922; }
.section-title { font-size: 0.8rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
.rounds-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 24px; }
.round-card { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 14px 18px; display: grid; grid-template-columns: 50px 1fr 200px 80px 80px; align-items: center; gap: 14px; }
.round-card.active { border-color: #388bfd; box-shadow: 0 0 20px rgba(56,139,253,0.2); animation: glow 2s infinite; }
.round-card.best { border-color: #3fb950; }
@keyframes glow { 0%,100%{box-shadow:0 0 10px rgba(56,139,253,0.2)} 50%{box-shadow:0 0 25px rgba(56,139,253,0.4)} }
.round-num { font-size: 1.4rem; font-weight: 700; color: #58a6ff; text-align: center; }
.round-card.best .round-num { color: #3fb950; }
.round-info { display: flex; flex-direction: column; gap: 4px; }
.round-sources { font-size: 0.8rem; color: #8b949e; display: flex; flex-wrap: wrap; gap: 4px; }
.round-sources span { background: #21262d; border-radius: 4px; padding: 1px 6px; font-size: 0.72rem; color: #c9d1d9; }
.round-depth { font-size: 0.72rem; color: #6e7681; }
.round-bar { width: 100%; height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; }
.round-bar-fill { height: 100%; border-radius: 4px; transition: width 0.8s ease; }
.bar-best { background: linear-gradient(90deg, #1f6feb, #58a6ff); }
.bar-up { background: linear-gradient(90deg, #238636, #3fb950); }
.bar-flat { background: linear-gradient(90deg, #9e6a03, #d29922); }
.round-meta { font-size: 1.1rem; font-weight: 700; text-align: right; }
.round-card.up .round-meta { color: #3fb950; }
.round-card.flat .round-meta { color: #d29922; }
.round-card.best .round-meta { color: #58a6ff; }
.round-icon { font-size: 1.3rem; text-align: right; }
.best-result { background: linear-gradient(135deg, #0d1f0d, #161b22); border: 1px solid #238636; border-radius: 12px; padding: 18px 22px; margin-bottom: 24px; }
.best-result h3 { font-size: 0.8rem; color: #3fb950; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 10px; }
.best-result .strategy { font-family: monospace; font-size: 0.85rem; color: #c9d1d9; background: #0d1117; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px; }
.best-result .meta { display: flex; gap: 18px; font-size: 0.82rem; color: #8b949e; }
.history-list { display: flex; flex-direction: column; gap: 6px; }
.history-item { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; }
.history-item .topic { color: #c9d1d9; font-size: 0.85rem; }
.history-item .meta { color: #6e7681; font-size: 0.72rem; margin-top: 2px; }
.footer { margin-top: 28px; padding-top: 14px; border-top: 1px solid #21262d; display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #484f58; }
.footer .btns button { background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; padding: 5px 12px; cursor: pointer; font-size: 0.75rem; margin-left: 6px; transition: all 0.2s; }
.footer .btns button:hover { background: #30363d; color: #e6edf3; }
.footer .btns button.primary { background: #238636; border-color: #238636; color: #fff; }
.footer .btns button.primary:hover { background: #2ea043; }
.no-data { text-align: center; padding: 50px 20px; color: #484f58; font-size: 0.85rem; }
.no-data .icon { font-size: 2.5rem; margin-bottom: 10px; }
@keyframes flash-new { 0%{background:#161b22} 50%{background:#1c2d1c} 100%{background:#161b22} }
.round-card.new-round { animation: flash-new 0.8s ease 2; }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>🧬 AutoResearch 实时监控</h1>
    <div style="font-size:0.78rem;color:#6e7681;margin-top:4px;" id="topic-display">等待数据...</div>
  </div>
  <div style="display:flex;gap:10px;align-items:center;">
    <span class="badge"><span class="live-dot" id="live-dot"></span><span id="status-text">连接中</span></span>
    <span class="badge" id="refresh-badge">刷新: 3s</span>
  </div>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="label">当前轮次</div>
    <div class="value" id="s-rounds">—</div>
    <div class="label" id="s-rounds-total" style="margin-top:2px;">/ 3 轮</div>
  </div>
  <div class="stat-card">
    <div class="label">最优信息量</div>
    <div class="value" id="s-findings">—</div>
    <div class="label" style="margin-top:2px;">条</div>
  </div>
  <div class="stat-card hot">
    <div class="label">最高热度</div>
    <div class="value" id="s-score">—</div>
    <div class="label" style="margin-top:2px;">⭐</div>
  </div>
  <div class="stat-card up">
    <div class="label">提升倍率</div>
    <div class="value" id="s-mult">—</div>
    <div class="label" style="margin-top:2px;">x</div>
  </div>
  <div class="stat-card time">
    <div class="label">总耗时</div>
    <div class="value" id="s-elapsed">—</div>
    <div class="label" style="margin-top:2px;">秒</div>
  </div>
  <div class="stat-card">
    <div class="label">进化状态</div>
    <div class="value" id="s-status" style="font-size:1.3rem;">⏳</div>
    <div class="label" id="s-status-sub" style="margin-top:2px;">—</div>
  </div>
</div>

<div class="best-result" id="best-panel" style="display:none;">
  <h3>🏆 最优策略</h3>
  <div class="strategy" id="best-strategy"></div>
  <div class="meta">
    <span>📊 <span id="best-findings">—</span> 条</span>
    <span>🔥 <span id="best-score">—</span></span>
    <span>📈 <span id="best-mult">—</span>x</span>
    <span>R<span id="best-round">—</span> 轮</span>
  </div>
</div>

<div class="section-title">📡 实时轮次进度</div>
<div class="rounds-list" id="rounds-list">
  <div class="no-data"><div class="icon">🔬</div><div>等待进化数据...</div><div style="margin-top:8px;font-size:0.8rem;">运行 autorun_evolve.py 开始</div></div>
</div>

<div class="section-title">📜 进化历史</div>
<div class="history-list" id="history-list">
  <div class="no-data" style="padding:20px;">暂无历史记录</div>
</div>

<div class="footer">
  <span id="footer-info">AutoResearch 实时监控 | 每 3 秒自动刷新</span>
  <div class="btns">
    <button class="primary" onclick="refreshNow()">🔄 立即刷新</button>
    <button onclick="toggleAuto()">⏸️ 暂停</button>
    <button onclick="window.open('http://localhost:18789','_blank')">🌐 QClaw</button>
  </div>
</div>

<script>
const POLL = 3000;
const evolFile = '/data/evolution.jsonl';
let auto = true, timer = null, lastHash = '';

async function get(url) {
  try { const r = await fetch(url + '?x=' + Date.now()); return r.ok ? r.text() : null; }
  catch { return null; }
}

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h<<5) - h) + s.charCodeAt(i);
  return h;
}

function parseHistory(text) {
  if (!text) return [];
  return text.trim().split('\n').filter(l => l.trim()).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean).reverse();
}

function renderRounds(rounds) {
  const el = document.getElementById('rounds-list');
  if (!rounds || rounds.length === 0) {
    el.innerHTML = '<div class="no-data"><div class="icon">🔬</div><div>等待数据...</div></div>';
    return;
  }
  const max = Math.max(...rounds.map(r => r.total_findings));
  const best = rounds.reduce((a,b) => a.total_findings > b.total_findings ? a : b);
  el.innerHTML = rounds.map(r => {
    const isBest = r.total_findings === best.total_findings;
    const isUp = r.score_delta > 0.1;
    const pct = max > 0 ? (r.total_findings / max * 100) : 0;
    const cls = isBest ? 'best' : (isUp ? 'up' : 'flat');
    const bar = isBest ? 'bar-best' : (isUp ? 'bar-up' : 'bar-flat');
    const icon = isBest ? '🏆' : (isUp ? '✅' : '⏸️');
    const srcs = (r.sources||[]).map(s => `<span>${s}</span>`).join('');
    return `<div class="round-card ${cls}">
      <div class="round-num">R${r.round_num}</div>
      <div class="round-info">
        <div class="round-sources">${srcs}</div>
        <div class="round-depth">${r.depth||'quick'} &nbsp;·&nbsp; ${(r.decision||'').slice(0,50)}</div>
      </div>
      <div>
        <div style="font-size:0.72rem;color:#6e7681;margin-bottom:4px;">${r.total_findings} 条</div>
        <div class="round-bar"><div class="round-bar-fill ${bar}" style="width:${pct}%"></div></div>
      </div>
      <div class="round-meta">🔥 ${r.top_score||0}</div>
      <div class="round-icon">${icon}</div>
    </div>`;
  }).join('');
}

function renderStats(rounds, total, elapsed, topic) {
  const best = rounds.reduce((a,b) => a.total_findings > b.total_findings ? a : b);
  const first = rounds[0];
  const mult = first ? (best.total_findings / Math.max(first.total_findings, 1)).toFixed(1) : '1.0';
  const done = rounds.length >= total;

  document.getElementById('s-rounds').textContent = rounds.length;
  document.getElementById('s-rounds-total').textContent = '/ ' + total + ' 轮';
  document.getElementById('s-findings').textContent = best ? best.total_findings : '—';
  document.getElementById('s-score').textContent = best ? (best.top_score||0) : '—';
  document.getElementById('s-mult').textContent = mult + 'x';
  document.getElementById('s-elapsed').textContent = elapsed ? elapsed.toFixed(0) + 's' : '—';
  document.getElementById('s-status').textContent = done ? '🏁' : '⚙️';
  document.getElementById('s-status-sub').textContent = done ? '已完成' : '进化中';
  document.getElementById('topic-display').textContent = topic ? '主题: ' + topic : '';

  if (best) {
    document.getElementById('best-panel').style.display = '';
    document.getElementById('best-strategy').textContent = `sources=${JSON.stringify(best.sources)}, depth=${best.depth||'standard'}`;
    document.getElementById('best-findings').textContent = best.total_findings;
    document.getElementById('best-score').textContent = best.top_score||0;
    document.getElementById('best-mult').textContent = mult;
    document.getElementById('best-round').textContent = best.round_num;
  }
}

function renderHistory(records) {
  const el = document.getElementById('history-list');
  if (!records || records.length === 0) {
    el.innerHTML = '<div class="no-data" style="padding:20px;">暂无历史</div>'; return;
  }
  el.innerHTML = records.slice(0,8).map(r => {
    const best = r.rounds ? r.rounds.reduce((a,b) => a.total_findings>b.total_findings?a:b, r.rounds[0]) : null;
    const date = (r.ts||'').slice(0,10);
    const time = (r.ts||'').slice(11,19);
    return `<div class="history-item">
      <div><div class="topic">${r.topic||'?'}</div><div class="meta">${date} ${time} | ${r.total_rounds||0}轮 | ${best?best.total_findings:0}条 | R${r.best_round||'?'}</div></div>
      <div style="color:#3fb950;font-size:0.8rem;">${r.total_rounds||0}轮</div>
    </div>`;
  }).join('');
}

async function update() {
  const text = await get('/data/evolution.jsonl');
  const records = parseHistory(text || '');
  if (!records.length) {
    document.getElementById('status-text').textContent = '无数据';
    return;
  }
  const h = hashStr(text || '');
  if (h === lastHash) return;
  lastHash = h;

  const latest = records[0];
  const rounds = latest.rounds || [];
  const elapsed = latest.elapsed_s || 0;
  const total = latest.total_rounds || 3;

  document.getElementById('status-text').textContent = '实时';
  document.getElementById('footer-info').textContent = '更新: ' + new Date().toLocaleTimeString('zh-CN') + ' | ' + records.length + ' 条记录';

  renderRounds(rounds);
  renderStats(rounds, total, elapsed, latest.topic);
  renderHistory(records);
}

function refreshNow() { lastHash = ''; update(); }
function toggleAuto() {
  auto = !auto;
  if (auto) { startAuto(); document.querySelector('.footer .btns button:nth-child(2)').textContent = '⏸️ 暂停'; document.getElementById('refresh-badge').textContent = '刷新: 3s'; }
  else { clearInterval(timer); document.querySelector('.footer .btns button:nth-child(2)').textContent = '▶️ 继续'; document.getElementById('refresh-badge').textContent = '已暂停'; }
}
function startAuto() { if (timer) clearInterval(timer); timer = setInterval(update, POLL); }

startAuto();
update();
</script>
</body>
</html>"""


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]}", flush=True)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path.startswith("/data/"):
            # Proxy to local files
            filename = self.path[6:]  # remove /data/
            local_path = ROOT / filename
            if local_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.end_headers()
                self.wfile.write(local_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"{}")
        else:
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run(port=PORT):
    server = http.server.HTTPServer(("0.0.0.0", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print(f"\n  🧬 AutoResearch 实时看板已启动\n  📍 {url}\n  Ctrl+C 停止服务器\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止", flush=True)
        server.shutdown()


if __name__ == "__main__":
    run()
