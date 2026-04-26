#!/bin/bash
# QClaw Hermes 一键启动 (Linux/macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "  QClaw Hermes 一键启动"
echo "============================================================"
echo ""

echo "[1/3] 同步最新记忆..."
python memory_sync_service.py sync "$SCRIPT_DIR"
echo ""

echo "[2/3] 启动同步服务..."
nohup python memory_sync_service.py daemon "$SCRIPT_DIR" > .sync/hermes.log 2>&1 &
echo "  [OK] 同步服务已启动 (PID: $!)"
echo ""

echo "[3/3] 检查状态..."
python deploy_hermes.py status "$SCRIPT_DIR"
echo ""

echo "============================================================"
echo "  Hermes 已启动，同步服务运行中..."
echo "  停止服务: pkill -f 'memory_sync_service.py daemon'"
echo "============================================================"
echo ""