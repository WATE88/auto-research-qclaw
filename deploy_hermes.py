#!/usr/bin/env python3
"""
Hermes 设备同步部署脚本 - 一键从GitHub拉取QClaw记忆

在任意新设备上运行:
  python deploy_hermes.py deploy           # 完整部署 (克隆/设置/初始化)
  python deploy_hermes.py sync-only        # 仅同步 (已有仓库)
  python deploy_hermes.py status           # 检查状态
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 配置
# ============================================================

GITHUB_REPO = "https://github.com/WATE88/auto-research-qclaw.git"
BRANCH = "master"

CST = timezone(timedelta(hours=8))

def now_cst():
    return datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')

def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def run(cmd, cwd=None, check=True):
    result = subprocess.run(
        cmd if isinstance(cmd, list) else cmd,
        shell=isinstance(cmd, str),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"  [WARNING] {stderr}")
    return result

# ============================================================
# 核心逻辑
# ============================================================

class HermesDeployer:
    def __init__(self, workspace=None):
        if workspace:
            self.workspace = Path(workspace)
        else:
            self.workspace = Path.home() / ".qclaw" / "workspace-agent-d29ea948"
        
        self.conversations_dir = self.workspace / "conversations"
        self.sync_dir = self.workspace / ".sync"
    
    def deploy(self):
        """完整部署: 克隆仓库 + 设置配置 + 初始化"""
        print_step(f"HERMES 部署开始 | {now_cst()}")
        
        # 1. 克隆/拉取仓库
        self._clone_or_pull()
        
        # 2. 设置设备配置
        self._setup_device_config()
        
        # 3. 创建目录结构
        self._ensure_dirs()
        
        # 4. 验证核心文件
        self._verify_core_files()
        
        # 5. 输出状态
        self._print_summary()
    
    def sync_only(self):
        """仅同步: 在已有仓库上拉取最新"""
        print_step(f"HERMES 同步 | {now_cst()}")
        
        if not (self.workspace / ".git").exists():
            print("  [ERROR] 不是Git仓库, 请先运行 deploy")
            return False
        
        # 拉取最新
        result = run(f'git pull origin {BRANCH} --rebase', cwd=str(self.workspace), check=False)
        
        if result.returncode == 0:
            print(f"  [OK] 已同步最新记忆")
        else:
            stderr = result.stderr.strip()
            if 'up to date' in stderr.lower() or 'already up' in stderr.lower():
                print(f"  [OK] 已是最新, 无需同步")
            else:
                print(f"  [WARNING] {stderr}")
        
        self._update_last_sync()
        return True
    
    def status(self):
        """检查状态"""
        print_step(f"HERMES 状态 | {now_cst()}")
        
        # 检查工作区
        ws_exists = self.workspace.exists()
        print(f"  工作区存在: {'Yes' if ws_exists else 'No'}")
        if not ws_exists:
            return
        
        print(f"  路径: {self.workspace}")
        
        # Git状态
        git_dir = self.workspace / ".git"
        if git_dir.exists():
            result = run('git log -1 --format="%h %s (%ci)"', cwd=str(self.workspace))
            last_commit = result.stdout.strip()
            print(f"  最新提交: {last_commit}")
            
            result = run('git status --short', cwd=str(self.workspace))
            pending = len([l for l in result.stdout.split('\n') if l.strip()])
            print(f"  待提交: {pending} 个文件")
        else:
            print(f"  Git: 未初始化")
        
        # 关键文件
        for f in ['MEMORY.md', 'MEMORY.md.bak']:
            mem = self.workspace / f
            if mem.exists():
                with open(mem, 'r', encoding='utf-8-sig', errors='ignore') as fp:
                    first_line = fp.readline().strip()
                print(f"  {f}: Yes ({first_line})")
            else:
                print(f"  {f}: No")
        
        # 今日记忆
        today = datetime.now(CST).strftime('%Y-%m-%d')
        daily = self.workspace / "memory" / f"{today}.md"
        if daily.exists():
            print(f"  今日记忆: Yes ({daily.stat().st_size} bytes)")
        else:
            print(f"  今日记忆: No")
    
    # ---------- private ----------
    
    def _clone_or_pull(self):
        print_step("1/5 Git 仓库同步")
        
        git_dir = self.workspace / ".git"
        
        if git_dir.exists():
            print(f"  仓库已存在, 拉取最新...")
            result = run(f'git pull origin {BRANCH} --rebase', cwd=str(self.workspace), check=False)
            if result.returncode == 0:
                print(f"  [OK] 已更新到最新")
            elif 'up to date' in result.stderr.lower():
                print(f"  [OK] 已是最新")
            else:
                print(f"  [WARNING] 拉取可能失败, 继续...")
        else:
            print(f"  首次部署, 克隆仓库...")
            self.workspace.parent.mkdir(parents=True, exist_ok=True)
            
            result = run(
                f'git clone -b {BRANCH} {GITHUB_REPO} "{self.workspace}"',
                cwd=str(self.workspace.parent),
                check=False
            )
            
            if result.returncode != 0:
                print(f"  [ERROR] 克隆失败: {result.stderr}")
                raise SystemExit(1)
            
            print(f"  [OK] 克隆完成")
    
    def _setup_device_config(self):
        print_step("2/5 设备注册")
        
        config_file = self.workspace / "config" / "sync_config.json"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
        else:
            config = {
                "version": "1.0",
                "github": {"repo": "WATE88/auto-research-qclaw", "branch": BRANCH, "auto_commit": True, "auto_push": True, "commit_message_template": "Auto sync: {date} {time}"},
                "sync_interval": {"auto_sync_enabled": True, "interval_minutes": 30, "on_startup": True, "on_shutdown": True, "on_conversation_end": True},
                "conflict_resolution": {"auto_resolve_enabled": True, "strategy": "merge_append", "backup_enabled": True},
                "devices": {"current_device_id": "", "device_name": "", "registered_devices": []}
            }
        
        # 设置 Hermes 设备ID
        hermes_id = "hermes-qclaw"
        hermes_name = "Hermes QClaw"
        
        config["devices"]["current_device_id"] = hermes_id
        config["devices"]["device_name"] = hermes_name
        
        # 注册到设备列表
        devices = config["devices"].get("registered_devices", [])
        if not any(d["id"] == hermes_id for d in devices):
            devices.append({
                "id": hermes_id,
                "name": hermes_name,
                "last_sync": now_cst()
            })
        
        config["devices"]["registered_devices"] = devices
        
        # 保存
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8-sig') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"  [OK] 设备已注册: {hermes_id} ({hermes_name})")
    
    def _ensure_dirs(self):
        print_step("3/5 目录初始化")
        
        dirs = [
            self.conversations_dir,
            self.sync_dir,
            self.sync_dir / "conflicts",
            self.sync_dir / "archive",
            self.workspace / "memory"
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        
        print(f"  [OK] {len(dirs)} 个目录就绪")
    
    def _verify_core_files(self):
        print_step("4/5 核心文件验证")
        
        mem_file = self.workspace / "MEMORY.md"
        if mem_file.exists():
            with open(mem_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            mem_count = sum(1 for l in lines if l.strip().startswith('- **'))
            
            print(f"  MEMORY.md: {len(content)} chars, {mem_count} 条记忆")
        else:
            print(f"  MEMORY.md: 不存在!")
        
        # 同步服务
        sync_svc = self.workspace / "memory_sync_service.py"
        if sync_svc.exists():
            print(f"  memory_sync_service.py: Yes ({sync_svc.stat().st_size} bytes)")
        else:
            print(f"  memory_sync_service.py: No (将使用GitHub版本)")
    
    def _update_last_sync(self):
        """更新同步时间戳"""
        config_file = self.workspace / "config" / "sync_config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
            
            hermes_id = config["devices"]["current_device_id"]
            for d in config["devices"].get("registered_devices", []):
                if d["id"] == hermes_id:
                    d["last_sync"] = now_cst()
                    break
            
            with open(config_file, 'w', encoding='utf-8-sig') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
    
    def _print_summary(self):
        print_step("5/5 部署完成")
        
        print(f"""
  ✅ HERMES 设备部署完成!
  
  📍 工作区: {self.workspace}
  🔗 远程: {GITHUB_REPO}
  🌿 分支: {BRANCH}
  🆔 设备ID: hermes-qclaw
  ⏰ 部署时间: {now_cst()}
  
  📋 后续操作:
    拉取最新记忆:    python deploy_hermes.py sync-only
    查看状态:        python deploy_hermes.py status
    启动同步服务:    python memory_sync_service.py daemon "{self.workspace}"
    手动同步:        python memory_sync_service.py sync "{self.workspace}"
""")

# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    command = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else None
    deployer = HermesDeployer(workspace)
    
    if command == 'deploy':
        deployer.deploy()
    elif command == 'sync-only':
        deployer.sync_only()
    elif command == 'status':
        deployer.status()
    else:
        print(f"未知命令: {command}")
        print(__doc__)

if __name__ == '__main__':
    main()
