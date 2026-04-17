@echo off
cd /d "%~dp0"
title AutoResearch - QClaw
chcp 65001 >nul
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   QClaw AutoResearch 本地运行脚本         ║
echo  ╚══════════════════════════════════════════╝
echo.
set /p topic="请输入研究主题（直接回车查看历史）: "
if "%topic%"=="" (
    python autorun_local.py --history 5
) else (
    python autorun_local.py "%topic%" --save --compare
)
echo.
pause
