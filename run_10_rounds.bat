@echo off
chcp 65001 >nul
echo ========================================
echo Token 优化研究 - 十轮循环
echo ========================================
echo.

set ROUNDS=10
set COUNT=0

:loop
set /a COUNT+=1
echo [第 %COUNT% / %ROUNDS% 轮]
echo ----------------------------------------

cd /d "C:\Users\wate\.qclaw\workspace-agent-d29ea948\auto-research-qclaw"
python autorun_token_opt_v2.py

echo.
echo [第 %COUNT% 轮完成]
echo ========================================
echo.

if %COUNT% lss %ROUNDS% (
    echo 等待 5 秒后继续下一轮...
    timeout /t 5 /nobreak >nul
    goto loop
)

echo 十轮研究全部完成！
pause
