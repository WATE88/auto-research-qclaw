#!/bin/bash
# AutoResearch 自主进化系统启动脚本 (Linux/macOS)
# 用法: ./start_evolution.sh

set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  AutoResearch 自主进化系统"
echo "=========================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到 python3，请安装 Python 3.9+${NC}"
    exit 1
fi

echo -e "${GREEN}[1/3] Python 版本:${NC}"
python3 --version
echo ""

# 检查依赖
echo -e "${GREEN}[2/3] 检查依赖...${NC}"
if ! python3 -c "import numpy, pandas, psutil, sklearn" 2>/dev/null; then
    echo -e "${YELLOW}[提示] 依赖未安装，正在安装...${NC}"
    pip3 install -r requirements.txt || pip install -r requirements.txt
fi
echo -e "${GREEN}[OK] 依赖检查通过${NC}"
echo ""

# 清理旧数据库（可选）
if [ -f "evolution_monitor.db" ]; then
    read -p "[提示] 发现旧数据库，是否清理？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f evolution_monitor.db
        echo -e "${GREEN}[OK] 已清理${NC}"
    fi
fi
echo ""

# 启动进化引擎（后台）
echo -e "${GREEN}[3/3] 启动进化引擎...${NC}"
nohup python3 autoresearch_self_evolve.py > evolution_engine.log 2>&1 &
ENGINE_PID=$!
echo "  引擎 PID: $ENGINE_PID"

# 等待引擎初始化
sleep 3

# 启动监控服务器（后台）
echo -e "${GREEN}[3/3] 启动监控服务器...${NC}"
nohup python3 evolution_monitor_server.py > evolution_server.log 2>&1 &
SERVER_PID=$!
echo "  服务器 PID: $SERVER_PID"

# 保存 PID
echo $ENGINE_PID > .evolution.pid
echo $SERVER_PID >> .evolution.pid

# 等待服务器启动
sleep 2

echo ""
echo "=========================================="
echo -e "${GREEN}  系统已启动！${NC}"
echo "  监控界面: http://localhost:8900"
echo "=========================================="
echo ""

# 尝试打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8900/ &
elif command -v open &> /dev/null; then
    open http://localhost:8900/ &
fi

echo "日志文件:"
echo "  - 引擎: evolution_engine.log"
echo "  - 服务器: evolution_server.log"
echo ""
echo "停止命令: ./stop_evolution.sh"
echo ""
