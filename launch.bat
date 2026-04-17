@echo off
chcp 65001 >nul 2>&1
title AutoResearch 统一监控中心
color 0B

REM ═══════════════════════════════════════════════════════════════
REM  AutoResearch launch.bat  v3.0  (可移植版 · 无硬编码路径)
REM
REM  用法：
REM    双击运行        → 一键启动统一系统 + 自动打开浏览器
REM    launch.bat /MENU   → 显示完整交互菜单
REM    launch.bat /STOP   → 停止所有进程
REM    launch.bat /STATUS → 查看运行状态
REM ═══════════════════════════════════════════════════════════════

REM ── 当前目录设为脚本所在目录（兼容双击和命令行调用）───────────
cd /d "%~dp0"
set WORKDIR=%~dp0
set PORT=8899

REM ── 自动探测 Python 解释器 ────────────────────────────────────
call :find_python
if not defined PYTHON (
    echo.
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║  ❌ 未找到 Python 3.9+，请先安装 Python！               ║
    echo  ║                                                          ║
    echo  ║  下载地址：https://www.python.org/downloads/            ║
    echo  ║  安装时请勾选 "Add Python to PATH"                      ║
    echo  ╚══════════════════════════════════════════════════════════╝
    echo.
    pause
    exit /b 1
)

REM ── 解析参数 ─────────────────────────────────────────────────
if /I "%~1"=="/MENU"    goto MENU
if /I "%~1"=="/STOP"    goto STOP_ALL
if /I "%~1"=="/STATUS"  goto STATUS
if /I "%~1"=="/INSTALL" goto INSTALL

REM ── 无参数：一键直启（双击默认行为）───────────────────────────
goto QUICK_START

REM ═══════════════════════════════════════════════════════════════
:QUICK_START
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║         AutoResearch  一键启动  v3.0                    ║
echo  ║  ──────────────────────────────────────────────────────  ║
echo  ║  正在启动：进化引擎 + 自动运行引擎 + Web监控              ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  Python: %PYTHON%
echo  目录:   %WORKDIR%
echo  端口:   %PORT%
echo.

REM 检查依赖
echo  [0/3] 检查核心依赖...
"%PYTHON%" -c "import numpy, scipy" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ⚠  核心依赖未安装，正在自动安装（首次运行需要网络）...
    call :do_install
    if %errorlevel% neq 0 (
        echo  ❌ 依赖安装失败，请手动运行 install.bat
        pause
        exit /b 1
    )
)

REM 清理旧进程
echo  [1/3] 清理旧进程...
call :kill_port %PORT%
timeout /t 1 /nobreak >nul

REM 启动服务（传入 UTF-8 环境变量，防止乱码）
echo  [2/3] 启动统一服务器（端口 %PORT%）...
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
start "AutoResearch-Server" /MIN cmd /c "chcp 65001 >nul && cd /d "%WORKDIR%" && set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1 && "%PYTHON%" autoresearch_unified_server.py 2>&1"

REM 等待就绪（最多等 30 秒）
echo  [3/3] 等待服务就绪...
set /a wait=0
:WAIT_LOOP
timeout /t 2 /nobreak >nul
set /a wait+=2
"%PYTHON%" -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:%PORT%/api/status',timeout=2); sys.exit(0)" >nul 2>&1
if %errorlevel%==0 goto READY
if %wait% geq 30 goto TIMEOUT
echo  等待中... (%wait%s / 30s)
goto WAIT_LOOP

:TIMEOUT
echo.
echo  ⚠  服务启动超时（30s），请检查以下信息：
echo     Python: %PYTHON%
echo     端口:   %PORT%
echo.
echo  尝试手动运行：
echo     %PYTHON% autoresearch_unified_server.py
echo.
pause
exit /b 1

:READY
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ✅  AutoResearch 已就绪！                               ║
echo  ║                                                          ║
echo  ║  监控界面：http://localhost:%PORT%/                       ║
echo  ║  API状态：http://localhost:%PORT%/api/status             ║
echo  ║  完整快照：http://localhost:%PORT%/api/snapshot          ║
echo  ║                                                          ║
echo  ║  [关闭此窗口] 服务继续后台运行                            ║
echo  ║  [停止服务]   运行 launch.bat /STOP                       ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
start "" "http://localhost:%PORT%/"
echo  已自动打开浏览器监控界面。
echo.
timeout /t 5 /nobreak >nul
exit /b 0

REM ═══════════════════════════════════════════════════════════════
:MENU
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║         AutoResearch  统一监控中心  v3.0                 ║
echo  ║  ──────────────────────────────────────────────────────  ║
echo  ║  Python: %-47s║
echo  ║  [1]  一键启动系统  →  http://localhost:%PORT%/          ║
echo  ║  [2]  停止所有进程                                       ║
echo  ║  [3]  查看运行状态                                       ║
echo  ║  [4]  打开监控界面（浏览器）                              ║
echo  ║  [5]  安装/更新依赖                                      ║
echo  ║  [0]  退出                                               ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
set /p choice=  请选择 [0-5]: 

if "%choice%"=="1" goto QUICK_START
if "%choice%"=="2" goto STOP_ALL
if "%choice%"=="3" goto STATUS
if "%choice%"=="4" goto OPEN_BROWSER
if "%choice%"=="5" goto INSTALL
if "%choice%"=="0" goto EXIT
goto MENU

REM ═══════════════════════════════════════════════════════════════
:INSTALL
echo.
echo  [安装] 安装/更新依赖中...
call :do_install
if %errorlevel%==0 (
    echo  [OK] 依赖安装完成
) else (
    echo  [WARN] 部分依赖安装失败，请检查网络或手动安装
)
echo.
if /I "%~1"=="/INSTALL" exit /b 0
pause
goto MENU

REM ═══════════════════════════════════════════════════════════════
:STOP_ALL
echo.
echo  [停止] 关闭 AutoResearch 进程...
call :kill_port %PORT%
taskkill /F /FI "WINDOWTITLE eq AutoResearch*" >nul 2>&1
echo  [OK] 已停止所有进程
echo.
if /I "%~1"=="/STOP" exit /b 0
pause
goto MENU

REM ═══════════════════════════════════════════════════════════════
:STATUS
echo.
echo  [状态] 检查运行状态...
echo.
echo  Python 版本:
"%PYTHON%" --version
echo.
echo  端口 %PORT% 占用:
netstat -ano | findstr ":%PORT% " 2>nul
echo.
echo  Python 进程:
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul | findstr /v "INFO:"
echo.
echo  HTTP 连通性:
"%PYTHON%" -c "import urllib.request,json,sys; r=urllib.request.urlopen('http://localhost:%PORT%/api/status',timeout=3); d=json.load(r); print('[%PORT%] OK  evolve='+str(d.get('evolve_running','?'))+'  autorun='+str(d.get('autorun_running','?')))" 2>nul || echo  [%PORT%] 未响应（服务未启动）
echo.
if /I "%~1"=="/STATUS" exit /b 0
pause
goto MENU

REM ═══════════════════════════════════════════════════════════════
:OPEN_BROWSER
"%PYTHON%" -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:%PORT%/',timeout=2)" >nul 2>&1
if %errorlevel%==0 (
    start "" "http://localhost:%PORT%/"
) else (
    echo  服务未运行，请先选[1]启动
    pause
)
goto MENU

REM ═══════════════════════════════════════════════════════════════
:EXIT
exit /b 0

REM ═══════════════════════════════════════════════════════════════
REM  子程序：自动安装依赖
:do_install
echo  使用镜像：https://pypi.tuna.tsinghua.edu.cn/simple
"%PYTHON%" -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
"%PYTHON%" -m pip install -r "%WORKDIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
exit /b %errorlevel%

REM ═══════════════════════════════════════════════════════════════
REM  子程序：按端口杀进程
:kill_port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~1 " 2^>nul') do (
    taskkill /F /PID %%a >nul 2>nul
)
exit /b 0

REM ═══════════════════════════════════════════════════════════════
REM  子程序：自动探测 Python 解释器（3.9+）
:find_python
set PYTHON=

REM 1. 系统 PATH 中的 python / python3
for %%P in (python python3) do (
    if not defined PYTHON (
        where %%P >nul 2>&1
        if %errorlevel%==0 (
            for /f "delims=" %%V in ('%%P --version 2^>^&1') do (
                echo %%V | findstr /r "3\.[9-9]\. 3\.1[0-9]\." >nul 2>&1
                if %errorlevel%==0 set PYTHON=%%P
                echo %%V | findstr /r "3\.[2-9][0-9]\." >nul 2>&1
                if %errorlevel%==0 set PYTHON=%%P
            )
        )
    )
)

REM 2. py launcher（Windows 官方安装器）
if not defined PYTHON (
    where py >nul 2>&1
    if %errorlevel%==0 (
        py -3 --version >nul 2>&1
        if %errorlevel%==0 set PYTHON=py -3
    )
)

REM 3. 常见安装路径探测（按优先级：高版本优先）
if not defined PYTHON (
    for %%V in (313 312 311 310 39) do (
        if not defined PYTHON (
            for %%D in (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
                "%ProgramFiles%\Python%%V\python.exe"
                "%ProgramFiles(x86)%\Python%%V\python.exe"
                "C:\Python%%V\python.exe"
            ) do (
                if not defined PYTHON (
                    if exist %%D set PYTHON=%%D
                )
            )
        )
    )
)

REM 4. WorkBuddy 内置 Python（如果存在）
if not defined PYTHON (
    for %%V in (3.14.3 3.13.12) do (
        set _try=%LOCALAPPDATA%\.workbuddy\binaries\python\versions\%%V\python.exe
        if exist "!_try!" set PYTHON="!_try!"
    )
)

exit /b 0
