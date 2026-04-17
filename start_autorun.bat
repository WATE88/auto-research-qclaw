@echo off
chcp 65001 > nul
title AutoResearch 一键启动

echo ============================================================
echo  AutoResearch 自动运行 + 实时监控系统
echo ============================================================
echo.

:: 进入项目目录
cd /d "%~dp0"

:: 清理旧数据库（可选，注释掉则保留历史）
if exist autorun_monitor.db del autorun_monitor.db
echo [1/3] 已清理旧数据库

:: 后台启动优化引擎
echo [2/3] 启动优化引擎...
start "AutoResearch Engine" /min python autoresearch_autorun.py

:: 等2秒让引擎写入初始数据
timeout /t 2 /nobreak > nul

:: 前台启动监控服务器（窗口可见，Ctrl+C 可停止）
echo [3/3] 启动监控服务器 http://localhost:8899
echo.
echo  按 Ctrl+C 可停止服务器
echo ============================================================
python autoresearch_monitor_server.py
