@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ======================================================
:: AutoResearch 开机自启安装工具
:: 将 AutoResearch 添加到 Windows 用户启动项
:: 方式：写入 HKCU\Software\Microsoft\Windows\CurrentVersion\Run
:: （无需管理员权限，仅对当前用户生效）
:: ======================================================

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "STARTUP_BAT=%SCRIPT_DIR%\start_background.bat"
set "REG_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
set "REG_NAME=AutoResearch"

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║        AutoResearch 开机自启 安装工具               ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: 检查 Python
set "PY="
where python >nul 2>&1 && set "PY=python"
if "!PY!"=="" (
    :: 尝试固定路径
    if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\python.exe" (
        set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\python.exe"
    )
)
if "!PY!"=="" (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9+
    pause & exit /b 1
)
echo [OK] Python: !PY!

:: 创建后台静默启动脚本
echo 正在创建后台启动脚本: %STARTUP_BAT%
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo cd /d "%SCRIPT_DIR%"
echo set "PYTHONUTF8=1"
echo set "PYTHONIOENCODING=utf-8"
echo :: 检查服务是否已运行
echo curl -s http://localhost:8899/api/status ^>nul 2^>^&1
echo if %%errorlevel%% == 0 ^(
echo     :: 已运行，跳过
echo     exit /b 0
echo ^)
echo :: 后台静默启动（不弹窗）
echo start /B "" "!PY!" "%SCRIPT_DIR%\autoresearch_unified_server.py" ^>"%SCRIPT_DIR%\autoresearch_bg.log" 2^>^&1
echo echo AutoResearch 已在后台启动，端口 8899
) > "%STARTUP_BAT%"

echo [OK] 后台启动脚本已创建

:: 写入注册表启动项
reg add "%REG_KEY%" /v "%REG_NAME%" /t REG_SZ /d "\"%STARTUP_BAT%\"" /f >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] 开机自启注册成功！
    echo      注册表路径: %REG_KEY%\%REG_NAME%
) else (
    echo [WARN] 注册表写入失败，尝试快捷方式方式...
    :: 备选：复制到启动文件夹
    set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    copy "%STARTUP_BAT%" "!STARTUP_FOLDER!\AutoResearch.bat" >nul 2>&1
    if !errorlevel! == 0 (
        echo [OK] 已复制到启动文件夹: !STARTUP_FOLDER!
    ) else (
        echo [ERROR] 启动项安装失败，请手动将以下文件添加到启动项:
        echo         %STARTUP_BAT%
    )
)

echo.
echo ──────────────────────────────────────────────────────
echo  立即启动 AutoResearch？（下次开机也会自动启动）
echo ──────────────────────────────────────────────────────
set /p LAUNCH="立即启动？[Y/n] "
if /i "!LAUNCH!"=="n" goto :done
if /i "!LAUNCH!"=="N" goto :done

:: 检查是否已运行
curl -s http://localhost:8899/api/status >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] AutoResearch 已在运行，无需重复启动
    echo      Dashboard: http://localhost:8899/
    goto :done
)

echo 正在后台启动 AutoResearch...
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
start /B "" "!PY!" "%SCRIPT_DIR%\autoresearch_unified_server.py" >"%SCRIPT_DIR%\autoresearch_bg.log" 2>&1

:: 等待启动
echo 等待服务就绪...
timeout /t 4 /nobreak >nul
curl -s http://localhost:8899/api/status >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] AutoResearch 已成功启动！
    echo      Dashboard: http://localhost:8899/
    start "" "http://localhost:8899/"
) else (
    echo [WARN] 服务启动中，请稍等几秒后访问 http://localhost:8899/
    echo        如有问题请查看日志: %SCRIPT_DIR%\autoresearch_bg.log
)

:done
echo.
echo ══════════════════════════════════════════════════════
echo  安装完成！重启电脑后 AutoResearch 将自动在后台运行。
echo  WorkBuddy AI 将能直接调用 AutoResearch 工具。
echo ══════════════════════════════════════════════════════
echo.
pause
