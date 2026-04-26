@echo off
chcp 65001 >nul
title QClaw Hermes Starter

echo.
echo ============================================================
echo   QClaw Hermes 一键启动
echo ============================================================
echo.

REM 设置工作区路径
set "WORKSPACE=%~dp0"

echo [1/3] 同步最新记忆...
python "%WORKSPACE%memory_sync_service.py" sync "%WORKSPACE%"
echo.

echo [2/3] 启动同步服务...
start "QClaw Hermes Sync" /min python "%WORKSPACE%memory_sync_service.py" daemon "%WORKSPACE%"
echo.

echo [3/3] 检查状态...
python "%WORKSPACE%deploy_hermes.py" status "%WORKSPACE%"
echo.

echo ============================================================
echo   Hermes 已启动，同步服务运行中...
echo   关闭窗口停止服务
echo ============================================================
echo.

pause