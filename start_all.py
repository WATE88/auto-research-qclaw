"""
AutoResearch 统一启动器
========================
跨平台启动脚本，自动检测操作系统并启动进化系统。

用法:
    python start_all.py           # 启动进化系统
    python start_all.py --clean   # 清理数据库后启动
    python start_all.py --stop    # 停止所有进程
"""

import os
import sys
import time
import subprocess
import argparse
import platform
from pathlib import Path

def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    if version < (3, 9):
        print(f"[错误] 需要 Python 3.9+，当前 {version.major}.{version.minor}")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """检查依赖"""
    required = ["numpy", "pandas", "psutil", "sklearn"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"[提示] 缺少依赖: {', '.join(missing)}")
        print("[提示] 正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        print("[OK] 所有依赖已安装")
    return True

def clean_database():
    """清理数据库"""
    db_files = ["evolution_monitor.db", "autorun_monitor.db"]
    for f in db_files:
        if os.path.exists(f):
            os.remove(f)
            print(f"[OK] 已删除 {f}")

def stop_processes():
    """停止所有相关进程"""
    scripts = ["autoresearch_self_evolve.py", "evolution_monitor_server.py",
               "autoresearch_autorun.py", "autoresearch_monitor_server.py"]
    
    system = platform.system()
    for script in scripts:
        if system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", f"WINDOWTITLE eq *{script}*"],
                          capture_output=True)
        else:
            subprocess.run(["pkill", "-f", script], capture_output=True)
    print("[OK] 已停止所有进程")

def start_engine():
    """启动进化引擎"""
    print("\n[1/3] 启动进化引擎...")
    if platform.system() == "Windows":
        subprocess.Popen([sys.executable, "autoresearch_self_evolve.py"],
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable, "autoresearch_self_evolve.py"],
                        stdout=open("evolution_engine.log", "w"),
                        stderr=subprocess.STDOUT)
    print("      引擎已在后台启动")

def start_server():
    """启动监控服务器"""
    print("\n[2/3] 启动监控服务器...")
    if platform.system() == "Windows":
        subprocess.Popen([sys.executable, "evolution_monitor_server.py"],
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable, "evolution_monitor_server.py"],
                        stdout=open("evolution_server.log", "w"),
                        stderr=subprocess.STDOUT)
    print("      服务器已在后台启动")

def open_browser():
    """打开浏览器"""
    print("\n[3/3] 打开监控界面...")
    time.sleep(2)
    url = "http://localhost:8900/"
    
    system = platform.system()
    if system == "Windows":
        os.startfile(url)
    elif system == "Darwin":
        subprocess.run(["open", url])
    else:
        subprocess.run(["xdg-open", url])
    print(f"      {url}")

def main():
    parser = argparse.ArgumentParser(description="AutoResearch 启动器")
    parser.add_argument("--clean", action="store_true", help="清理数据库后启动")
    parser.add_argument("--stop", action="store_true", help="停止所有进程")
    args = parser.parse_args()

    print("=" * 50)
    print("  AutoResearch 自主进化系统")
    print("=" * 50)
    print()

    if args.stop:
        stop_processes()
        return

    # 检查环境
    if not check_python():
        sys.exit(1)
    check_dependencies()

    # 清理数据库
    if args.clean:
        print("\n[清理] 删除旧数据库...")
        clean_database()

    # 启动系统
    start_engine()
    time.sleep(3)
    start_server()
    open_browser()

    print("\n" + "=" * 50)
    print("  系统已启动！")
    print("  监控界面: http://localhost:8900")
    print("=" * 50)
    print()

if __name__ == "__main__":
    main()
