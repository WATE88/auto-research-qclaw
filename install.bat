@echo off
chcp 65001 >nul 2>&1
title AutoResearch 依赖安装程序
color 0A

cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║       AutoResearch  依赖安装程序  v3.0                   ║
echo  ║  ──────────────────────────────────────────────────────  ║
echo  ║  此脚本会自动检测 Python 并安装所有必需依赖              ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

REM ── 探测 Python ──────────────────────────────────────────────
set PYTHON=
for %%P in (python python3) do (
    if not defined PYTHON (
        where %%P >nul 2>&1
        if %errorlevel%==0 (
            for /f "delims=" %%V in ('%%P --version 2^>^&1') do (
                echo %%V | findstr /r "3\.[9-9]\. 3\.1[0-9]\. 3\.[2-9][0-9]\." >nul 2>&1
                if %errorlevel%==0 set PYTHON=%%P
            )
        )
    )
)
if not defined PYTHON (
    where py >nul 2>&1
    if %errorlevel%==0 set PYTHON=py -3
)
if not defined PYTHON (
    for %%D in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
        "%ProgramFiles%\Python313\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined PYTHON (
            if exist %%D set PYTHON=%%D
        )
    )
)

if not defined PYTHON (
    echo  ❌ 未找到 Python 3.9+
    echo.
    echo  请先安装 Python（https://www.python.org/downloads/）
    echo  安装时勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo  ✅ 找到 Python: %PYTHON%
"%PYTHON%" --version
echo.

REM ── 升级 pip ─────────────────────────────────────────────────
echo  [1/3] 升级 pip...
"%PYTHON%" -m pip install --upgrade pip -q
echo.

REM ── 选择镜像源 ───────────────────────────────────────────────
echo  [2/3] 选择安装源：
echo    [1] 清华镜像（国内推荐）
echo    [2] 阿里云镜像
echo    [3] 官方 PyPI（境外网络）
echo.
set /p src_choice=  请选择 [默认=1]: 
if "%src_choice%"=="2" set MIRROR=https://mirrors.aliyun.com/pypi/simple/
if "%src_choice%"=="3" set MIRROR=https://pypi.org/simple/
if not defined MIRROR set MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

echo  使用镜像: %MIRROR%
echo.

REM ── 安装依赖 ─────────────────────────────────────────────────
echo  [3/3] 安装 requirements.txt...
"%PYTHON%" -m pip install -r requirements.txt -i %MIRROR% --trusted-host %MIRROR:https://=%
if %errorlevel%==0 (
    echo.
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║  ✅ 所有依赖安装成功！                                   ║
    echo  ║                                                          ║
    echo  ║  现在可以运行 launch.bat 启动系统                        ║
    echo  ╚══════════════════════════════════════════════════════════╝
) else (
    echo.
    echo  ⚠  部分依赖安装失败，请查看上方错误信息
    echo  可以尝试：
    echo    1. 更换镜像源后重试
    echo    2. 手动安装：%PYTHON% -m pip install numpy scipy scikit-learn psutil
)
echo.
pause
