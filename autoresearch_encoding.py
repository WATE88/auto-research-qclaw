"""
autoresearch_encoding.py
========================
跨平台编码修复工具
- 强制 stdout/stderr 使用 UTF-8
- Windows: 设置控制台代码页 65001
- 修复 Python 3.7+ io 层编码问题
- 在 server 和所有入口文件 import 即生效
"""
import sys, os, io, locale

# ── 1. 强制 stdout/stderr 为 UTF-8（无论控制台实际代码页）─────────────────────
def _patch_stdio():
    # 如果已经是 UTF-8 就不再重复包装（避免关闭已有的 TextIOWrapper）
    if sys.stdout and getattr(sys.stdout, 'encoding', '').lower().replace('-', '') == 'utf8':
        return
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        try:
            buf = sys.stdout.buffer
            sys.stdout = io.TextIOWrapper(buf, encoding='utf-8', errors='replace', line_buffering=True)
        except Exception:
            pass
    if sys.stderr and getattr(sys.stderr, 'encoding', '').lower().replace('-', '') != 'utf8':
        if hasattr(sys.stderr, 'buffer'):
            try:
                buf = sys.stderr.buffer
                sys.stderr = io.TextIOWrapper(buf, encoding='utf-8', errors='replace', line_buffering=True)
            except Exception:
                pass

# ── 2. Windows：设置控制台代码页 65001（UTF-8）─────────────────────────────────
def _patch_windows_console():
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# ── 3. 设置环境变量，确保子进程也继承 UTF-8 ──────────────────────────────────
def _patch_env():
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('PYTHONUTF8', '1')
    # locale-aware（Linux/macOS）
    if sys.platform != 'win32':
        try:
            locale.setlocale(locale.LC_ALL, '')
        except Exception:
            pass

# ── 4. 文件 I/O 默认编码修复（Python 3.15 前有些系统默认 gbk）────────────────
def safe_open(filepath, mode='r', encoding='utf-8', **kwargs):
    """替代 open()，强制 UTF-8，errors='replace' 避免解码失败崩溃"""
    if 'b' in mode:
        return open(filepath, mode, **kwargs)
    return open(filepath, mode, encoding=encoding, errors='replace', **kwargs)

# ── 立即执行 ─────────────────────────────────────────────────────────────────
_patch_env()
_patch_windows_console()
_patch_stdio()

# ── 对外工具函数 ──────────────────────────────────────────────────────────────
def ensure_utf8():
    """在任意脚本开头调用，确保 UTF-8 输出环境"""
    _patch_env()
    _patch_windows_console()
    _patch_stdio()

def fix_string(s: str) -> str:
    """尝试修复因编码错误产生的乱码字符串（gbk→utf8 最常见场景）"""
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except Exception:
        try:
            return s.encode('latin-1').decode('gbk', errors='replace')
        except Exception:
            return s
