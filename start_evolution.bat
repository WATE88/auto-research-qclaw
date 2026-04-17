@echo off
chcp 65001 >nul
title AutoResearch 自主进化系统

echo ==========================================
echo   AutoResearch 自主进化系统
echo   ==========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.9+
    pause
    exit /b 1
)

echo [1/3] Python 版本:
python --version
echo.

REM 检查依赖
echo [2/3] 检查依赖...
python -c "import numpy, pandas, psutil, sklearn" 2>nul
if errorlevel 1 (
    echo [提示] 依赖未安装，正在安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)
echo [OK] 依赖检查通过
echo.

REM 清理旧数据库（可选）
if exist "evolution_monitor.db" (
    echo [提示] 发现旧数据库，是否清理？
    choice /C YN /M "按 Y 清理，N 保留"
    if errorlevel 1 if not errorlevel 2 del "evolution_monitor.db" && echo [OK] 已清理
)
echo.

REM 启动进化引擎（后台）
echo [3/3] 启动进化引擎...
start "AutoResearch 进化引擎" pythonw autoresearch_self_evolve.py

REM 等待引擎初始化
timeout /t 3 /nobreak >nul

REM 启动监控服务器
echo [3/3] 启动监控服务器...
start "AutoResearch 监控" pythonw evolution_monitor_server.py

REM 等待服务器启动
timeout /t 2 /nobreak >nul

REM 打开浏览器
echo.
echo ==========================================
echo   系统已启动！
echo   监控界面: http://localhost:8900
echo   ==========================================
echo.
start http://localhost:8900/

echo 按任意键退出此窗口（后台继续运行）...
pause >nul
