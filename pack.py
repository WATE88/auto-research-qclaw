import os, sys, io
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

"""
pack.py — AutoResearch 打包工具
================================
用法：
    python pack.py                  → 打包到 dist/autoresearch-portable.zip
    python pack.py --output myfile  → 自定义输出文件名

打包内容：
  - 所有 .py .html .bat .sh .txt .md .json 文件
  - requirements.txt
  - 排除：*.db *.log __pycache__ .git .workbuddy experiments/ *.pyc

运行后直接把 zip 拷到新电脑，解压后双击 launch.bat 即可。
"""
import os, sys, zipfile, argparse, hashlib
from pathlib import Path
from datetime import datetime

# ── 要包含的文件类型 ──────────────────────────────────────────────
INCLUDE_EXTS = {'.py', '.html', '.bat', '.sh', '.txt', '.md', '.json', '.cfg', '.ini', '.toml'}

# ── 要排除的目录/文件模式 ─────────────────────────────────────────
EXCLUDE_DIRS = {'__pycache__', '.git', '.workbuddy', 'experiments', 'dist', 'build',
                '.venv', 'venv', 'node_modules', '.idea', '.vscode'}
EXCLUDE_FILES = {'*.pyc', '*.pyo', '*.log', '*.db', '*.sqlite', '*.bak', '*.tmp',
                 'evolution_monitor.db', 'autorun_monitor.db'}

def should_exclude_file(name: str) -> bool:
    import fnmatch
    for pat in EXCLUDE_FILES:
        if fnmatch.fnmatch(name, pat):
            return True
    return False

def collect_files(src: Path):
    files = []
    for root, dirs, filenames in os.walk(src):
        # 过滤排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for fn in filenames:
            if should_exclude_file(fn):
                continue
            p = Path(root) / fn
            if p.suffix.lower() in INCLUDE_EXTS:
                files.append(p)
    return files

def make_zip(src: Path, output_path: Path):
    files = collect_files(src)
    total = len(files)
    print(f"收集到 {total} 个文件，开始打包...")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i, fp in enumerate(files, 1):
            arcname = fp.relative_to(src)
            zf.write(fp, arcname)
            print(f"  [{i:3d}/{total}] {arcname}")
        
        # 写入打包信息文件
        pack_info = f"""AutoResearch Portable Package
打包时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
文件数量: {total}
Python要求: >= 3.9
端口: 8899

快速启动：
  1. 解压到任意目录（路径不要包含中文或空格）
  2. 双击 install.bat 安装依赖（首次运行）
  3. 双击 launch.bat 启动系统
  4. 浏览器访问 http://localhost:8899/
"""
        zf.writestr("PORTABLE_README.txt", pack_info.encode('utf-8').decode('utf-8'))
    
    size_mb = output_path.stat().st_size / 1024 / 1024
    # 计算 MD5
    md5 = hashlib.md5(output_path.read_bytes()).hexdigest()
    print(f"\n✅ 打包完成！")
    print(f"   输出文件: {output_path}")
    print(f"   文件大小: {size_mb:.2f} MB")
    print(f"   MD5: {md5}")
    print(f"\n使用方法：")
    print(f"  1. 将 {output_path.name} 拷贝到目标电脑")
    print(f"  2. 解压到任意目录（路径不含中文/空格更稳定）")
    print(f"  3. 目标电脑安装 Python 3.9+，勾选 Add to PATH")
    print(f"  4. 双击 install.bat → 安装依赖")
    print(f"  5. 双击 launch.bat → 启动系统")

def main():
    parser = argparse.ArgumentParser(description='AutoResearch 打包工具')
    parser.add_argument('--output', '-o', default='', help='输出文件名（不含.zip）')
    parser.add_argument('--src', default='', help='源目录（默认：本脚本所在目录）')
    args = parser.parse_args()
    
    src = Path(args.src) if args.src else Path(__file__).parent
    dist_dir = src.parent / 'dist'
    dist_dir.mkdir(exist_ok=True)
    
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    out_name = args.output or f'autoresearch-portable-{ts}'
    output_path = dist_dir / f'{out_name}.zip'
    
    print(f"AutoResearch 打包工具")
    print(f"源目录: {src}")
    print(f"输出: {output_path}")
    print()
    
    make_zip(src, output_path)

if __name__ == '__main__':
    main()
