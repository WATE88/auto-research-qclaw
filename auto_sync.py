import os, sys, subprocess, json
from datetime import datetime
from pathlib import Path

REPO_DIR = r"C:\Users\Admin\.qclaw\workspace\autoresearch"
LOG_FILE = Path(REPO_DIR) / "_sync.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, cwd=REPO_DIR):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def sync():
    log("=== AutoResearch 自动同步开始 ===")
    os.chdir(REPO_DIR)

    # 获取 token
    code, token, err = run("gh auth token")
    if code != 0 or not token:
        log(f"ERROR: 获取 token 失败: {err}")
        return False

    # 设置 remote URL（含 token）
    run(f'git remote set-url origin "https://{token}@github.com/WATE88/auto-research-qclaw.git"')

    # 检查是否有新文件
    code, status, _ = run("git status --short")
    new_files = [l for l in status.splitlines() if l.startswith("??")]

    # 添加核心文件
    core_patterns = [
        "autorun_evolve*.py",
        "autoresearch_mcp.py",
        "*.md",
        "requirements.txt",
        ".gitignore",
    ]
    for pat in core_patterns:
        run(f"git add {pat}")

    # 检查是否有变更
    code, diff, _ = run("git diff --cached --stat")
    if not diff:
        log("无变更，跳过提交")
        return True

    # 提交
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"Auto sync: {ts}"
    code, out, err = run(f'git commit -m "{msg}"')
    if code != 0:
        log(f"ERROR: commit 失败: {err}")
        return False
    log(f"Commit: {out.splitlines()[0] if out else 'ok'}")

    # 推送
    code, out, err = run("git push origin main")
    if code != 0 and "new branch" not in err and "Everything up-to-date" not in err:
        log(f"ERROR: push 失败: {err}")
        return False

    log(f"Push 成功: {diff.splitlines()[-1] if diff else 'ok'}")
    log("=== 同步完成 ===")
    return True

if __name__ == "__main__":
    ok = sync()
    sys.exit(0 if ok else 1)
