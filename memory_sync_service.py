#!/usr/bin/env python3
"""
QClaw Memory Sync Service - 跨设备对话记忆同步服务

核心功能：
1. 对话记录与存储
2. Git自动同步
3. MEMOS集成（可选）
4. 冲突检测与解决
5. 定时同步管理

使用方式：
  python memory_sync_service.py sync          # 手动同步
  python memory_sync_service.py daemon         # 启动后台服务
  python memory_sync_service.py status         # 查看状态
  python memory_sync_service.py record         # 记录当前对话
"""

import os
import sys
import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import time

# ============================================================
# 配置类
# ============================================================

class SyncConfig:
    """同步配置管理"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.config_dir = workspace / "config"
        self.config_file = self.config_dir / "sync_config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认配置
            default = self._get_default_config()
            self._save_config(default)
            return default
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "version": "1.0",
            "github": {
                "repo": "WATE88/auto-research-qclaw",
                "branch": "main",
                "auto_commit": True,
                "auto_push": True,
                "commit_message_template": "Auto sync: {date} {time}"
            },
            "sync_interval": {
                "auto_sync_enabled": True,
                "interval_minutes": 30,
                "on_startup": True,
                "on_shutdown": True,
                "on_conversation_end": True
            },
            "conflict_resolution": {
                "auto_resolve_enabled": True,
                "strategy": "merge_append",
                "backup_enabled": True
            },
            "devices": {
                "current_device_id": f"device-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "device_name": "QClaw Device",
                "registered_devices": []
            }
        }
    
    def _save_config(self, config: dict):
        """保存配置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default=None):
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

# ============================================================
# 对话记录器
# ============================================================

class ConversationLogger:
    """对话记录器"""
    
    def __init__(self, workspace: Path, device_id: str):
        self.workspace = workspace
        self.device_id = device_id
        self.conversations_dir = workspace / "conversations"
        self.current_session = None
    
    def start_session(self, session_id: Optional[str] = None) -> str:
        """开始新会话"""
        if session_id is None:
            session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_session = {
            "session_id": session_id,
            "device": self.device_id,
            "start_time": datetime.now().isoformat(),
            "messages": [],
            "key_points": [],
            "decisions": [],
            "next_steps": [],
            "artifacts": []
        }
        
        return session_id
    
    def record_message(self, role: str, content: str, 
                      key_points: List[str] = None,
                      decisions: List[str] = None,
                      artifacts: List[str] = None):
        """记录消息"""
        if self.current_session is None:
            self.start_session()
        
        message = {
            "role": role,
            "content": content[:500],  # 限制长度
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_session["messages"].append(message)
        
        # 记录关键点
        if key_points:
            self.current_session["key_points"].extend(key_points)
        
        # 记录决策
        if decisions:
            self.current_session["decisions"].extend(decisions)
        
        # 记录产生的文件
        if artifacts:
            self.current_session["artifacts"].extend(artifacts)
    
    def end_session(self) -> Optional[dict]:
        """结束会话并保存"""
        if self.current_session is None:
            return None
        
        self.current_session["end_time"] = datetime.now().isoformat()
        
        # 生成摘要
        self.current_session["summary"] = self._generate_summary()
        
        # 保存到文件
        self._save_session(self.current_session)
        
        session = self.current_session
        self.current_session = None
        
        return session
    
    def _generate_summary(self) -> str:
        """生成会话摘要"""
        if not self.current_session:
            return ""
        
        msg_count = len(self.current_session["messages"])
        key_points = len(self.current_session["key_points"])
        decisions = len(self.current_session["decisions"])
        
        return f"会话包含 {msg_count} 条消息，提取 {key_points} 个关键点，{decisions} 个决策"
    
    def _save_session(self, session: dict):
        """保存会话到文件"""
        # 创建日期目录
        date_dir = self.conversations_dir / datetime.now().strftime('%Y-%m-%d')
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存JSON文件
        filename = f"{session['session_id']}.json"
        filepath = date_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
        
        print(f"[Logger] 会话已保存: {filepath}")
    
    def get_today_sessions(self) -> List[dict]:
        """获取今日所有会话"""
        today = datetime.now().strftime('%Y-%m-%d')
        date_dir = self.conversations_dir / today
        
        if not date_dir.exists():
            return []
        
        sessions = []
        for f in date_dir.glob("*.json"):
            with open(f, 'r', encoding='utf-8') as fp:
                sessions.append(json.load(fp))
        
        return sorted(sessions, key=lambda x: x['start_time'])

# ============================================================
# 记忆更新器
# ============================================================

class MemoryUpdater:
    """记忆更新器"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_file = workspace / "MEMORY.md"
        self.daily_memory_dir = workspace / "memory"
    
    def update_daily_memory(self, session: dict):
        """更新每日记忆"""
        if not session:
            return
        
        # 确保 memory 目录存在
        self.daily_memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 今日记忆文件
        today = datetime.now().strftime('%Y-%m-%d')
        daily_file = self.daily_memory_dir / f"{today}.md"
        
        # 生成记忆条目
        entry = self._format_session_entry(session)
        
        # 追加到文件
        if daily_file.exists():
            with open(daily_file, 'r', encoding='utf-8') as f:
                content = f.read()
            content += f"\n{entry}\n"
        else:
            content = f"# {today} 工作日志\n\n{entry}\n"
        
        # 写入文件（使用 qclaw-text-file 规范）
        self._write_file(daily_file, content)
        
        print(f"[Updater] 每日记已更新: {daily_file}")
    
    def update_long_term_memory(self, session: dict, important: bool = False):
        """更新长期记忆 MEMORY.md"""
        if not session or not important:
            return
        
        # 读取现有内容
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "# 长期记忆\n\n"
        
        # 提取重要内容
        memory_entry = self._extract_important_memory(session)
        
        if memory_entry:
            # 添加到开头（最新的在前面）
            lines = content.split('\n')
            insert_pos = 2 if len(lines) > 2 else len(lines)
            lines.insert(insert_pos, f"\n{memory_entry}\n")
            
            self._write_file(self.memory_file, '\n'.join(lines))
            print(f"[Updater] 长期记忆已更新")
    
    def _format_session_entry(self, session: dict) -> str:
        """格式化会话条目"""
        time_str = datetime.fromisoformat(session['start_time']).strftime('%H:%M')
        
        entry = f"\n### {time_str} - 会话: {session['session_id']}\n\n"
        
        if session.get('key_points'):
            entry += "**关键点**:\n"
            for kp in session['key_points'][:3]:
                entry += f"- {kp}\n"
        
        if session.get('decisions'):
            entry += "\n**决策**:\n"
            for dec in session['decisions'][:2]:
                entry += f"- {dec}\n"
        
        if session.get('artifacts'):
            entry += f"\n**产出文件**: {', '.join(session['artifacts'])}\n"
        
        if session.get('summary'):
            entry += f"\n*{session['summary']}*\n"
        
        return entry
    
    def _extract_important_memory(self, session: dict) -> Optional[str]:
        """提取重要记忆"""
        if not session.get('decisions') and not session.get('key_points'):
            return None
        
        date = datetime.now().strftime('%Y-%m-%d')
        
        memory = f"- **{date}**: "
        
        if session.get('decisions'):
            memory += session['decisions'][0]
        elif session.get('key_points'):
            memory += session['key_points'][0]
        
        return memory
    
    def _write_file(self, filepath: Path, content: str):
        """写入文件（跨平台安全）"""
        # 简单实现：UTF-8 with BOM for Windows
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(content)

# ============================================================
# Git同步器
# ============================================================

class GitSyncer:
    """Git同步器"""
    
    def __init__(self, workspace: Path, config: SyncConfig):
        self.workspace = workspace
        self.config = config
        self.git_dir = workspace / ".git"
    
    def is_git_repo(self) -> bool:
        """检查是否是Git仓库"""
        return self.git_dir.exists()
    
    def sync(self) -> Tuple[bool, str]:
        """执行Git同步"""
        if not self.is_git_repo():
            return False, "不是Git仓库"
        
        try:
            # 1. 添加所有变更
            self._run_git(['add', '-A'])
            
            # 2. 检查是否有变更
            result = self._run_git(['status', '--porcelain'])
            if result.strip():
                # 有变更，提交
                self._commit()
                
                # 3. 拉取远程变更
                self._pull()
                
                # 4. 推送到远程
                self._push()
                
                return True, "同步成功"
            else:
                # 无变更，只拉取
                self._pull()
                return True, "无变更，已拉取最新"
        
        except Exception as e:
            return False, f"同步失败: {str(e)}"
    
    def _commit(self):
        """提交变更"""
        template = self.config.get('github.commit_message_template', 'Auto sync: {date}')
        message = template.format(
            date=datetime.now().strftime('%Y-%m-%d'),
            time=datetime.now().strftime('%H:%M')
        )
        self._run_git(['commit', '-m', message])
        print(f"[Git] 已提交: {message}")
    
    def _get_current_branch(self) -> str:
        """获取当前分支"""
        result = self._run_git(['branch', '--show-current'])
        if result.strip():
            return result.strip()
        return self.config.get('github.branch', 'main')

    def _pull(self):
        """拉取远程"""
        branch = self._get_current_branch()
        self._run_git(['pull', 'origin', branch, '--rebase'])
        print(f"[Git] 已拉取最新代码")
    
    def _push(self):
        """推送到远程"""
        if self.config.get('github.auto_push', True):
            branch = self._get_current_branch()
            self._run_git(['push', 'origin', branch])
            print(f"[Git] 已推送到远程")
    
    def _run_git(self, args: List[str]) -> str:
        """运行Git命令"""
        cmd = ['git'] + args
        result = subprocess.run(
            cmd,
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0 and 'nothing to commit' not in result.stderr:
            # 忽略 "nothing to commit" 错误
            if result.stderr:
                print(f"[Git Warning] {result.stderr}")
        
        return result.stdout + result.stderr
    
    def get_status(self) -> dict:
        """获取Git状态"""
        status = {
            'is_repo': self.is_git_repo(),
            'branch': '',
            'last_commit': '',
            'pending_changes': 0,
            'remote': ''
        }
        
        if status['is_repo']:
            try:
                # 获取分支
                result = self._run_git(['branch', '--show-current'])
                status['branch'] = result.strip()
                
                # 获取最后提交
                result = self._run_git(['log', '-1', '--oneline'])
                status['last_commit'] = result.strip().split()[0] if result.strip() else ''
                
                # 获取待提交数量
                result = self._run_git(['status', '--porcelain'])
                status['pending_changes'] = len([l for l in result.split('\n') if l.strip()])
                
                # 获取远程
                result = self._run_git(['remote', '-v'])
                if result.strip():
                    status['remote'] = result.strip().split()[1]
            
            except Exception as e:
                print(f"[Git Error] 获取状态失败: {e}")
        
        return status

# ============================================================
# 同步协调器（主服务）
# ============================================================

class SyncCoordinator:
    """同步协调器"""
    
    def __init__(self, workspace: Path = None):
        if workspace is None:
            workspace = Path.home() / ".qclaw" / "workspace"
        
        self.workspace = Path(workspace)
        self.config = SyncConfig(self.workspace)
        
        device_id = self.config.get('devices.current_device_id', 'unknown')
        
        self.logger = ConversationLogger(self.workspace, device_id)
        self.updater = MemoryUpdater(self.workspace)
        self.git_syncer = GitSyncer(self.workspace, self.config)
        
        self.state_file = self.workspace / ".sync" / "state.json"
        self.daemon_running = False
    
    def on_startup(self):
        """启动时同步"""
        print("[Sync] 启动同步服务...")
        
        # 拉取最新代码
        if self.config.get('sync_interval.on_startup', True):
            success, msg = self.git_syncer.sync()
            print(f"[Sync] {msg}")
        
        # 记录启动
        self._update_state('startup')
    
    def on_shutdown(self):
        """关闭时同步"""
        print("[Sync] 关闭同步服务...")
        
        # 保存当前会话
        session = self.logger.end_session()
        if session:
            self.updater.update_daily_memory(session)
        
        # 同步到远程
        if self.config.get('sync_interval.on_shutdown', True):
            success, msg = self.git_syncer.sync()
            print(f"[Sync] {msg}")
        
        # 记录关闭
        self._update_state('shutdown')
    
    def on_conversation_end(self):
        """对话结束时同步"""
        # 保存会话
        session = self.logger.end_session()
        if session:
            self.updater.update_daily_memory(session)
            
            # 检查是否重要（有决策）
            if session.get('decisions'):
                self.updater.update_long_term_memory(session, important=True)
        
        # 同步
        if self.config.get('sync_interval.on_conversation_end', True):
            self.git_syncer.sync()
    
    def record_conversation(self, role: str, content: str, 
                          key_points: List[str] = None,
                          decisions: List[str] = None,
                          artifacts: List[str] = None):
        """记录对话"""
        self.logger.record_message(role, content, key_points, decisions, artifacts)
    
    def manual_sync(self) -> Tuple[bool, str]:
        """手动同步"""
        return self.git_syncer.sync()
    
    def get_status(self) -> dict:
        """获取同步状态"""
        git_status = self.git_syncer.get_status()
        
        today_sessions = self.logger.get_today_sessions()
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'device_id': self.config.get('devices.current_device_id'),
            'workspace': str(self.workspace),
            'git': git_status,
            'today': {
                'sessions_count': len(today_sessions),
                'last_session': today_sessions[-1]['session_id'] if today_sessions else None
            },
            'config': {
                'auto_sync': self.config.get('sync_interval.auto_sync_enabled'),
                'interval_minutes': self.config.get('sync_interval.interval_minutes')
            }
        }
        
        return status
    
    def start_daemon(self):
        """启动后台同步服务"""
        if self.daemon_running:
            print("[Sync] 后台服务已在运行")
            return
        
        self.daemon_running = True
        interval = self.config.get('sync_interval.interval_minutes', 30) * 60
        
        def sync_loop():
            while self.daemon_running:
                time.sleep(interval)
                if self.daemon_running:
                    print(f"\n[Sync Daemon] 执行定时同步...")
                    self.git_syncer.sync()
        
        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()
        
        print(f"[Sync] 后台服务已启动，同步间隔: {interval//60} 分钟")
    
    def stop_daemon(self):
        """停止后台同步服务"""
        self.daemon_running = False
        print("[Sync] 后台服务已停止")
    
    def _update_state(self, event: str):
        """更新同步状态"""
        state_dir = self.state_file.parent
        state_dir.mkdir(parents=True, exist_ok=True)
        
        state = {
            'last_event': event,
            'timestamp': datetime.now().isoformat(),
            'device_id': self.config.get('devices.current_device_id')
        }
        
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                state['history'] = existing.get('history', [])
        
        state['history'].append({
            'event': event,
            'time': state['timestamp']
        })
        
        # 只保留最近100条
        state['history'] = state['history'][-100:]
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

# ============================================================
# CLI接口
# ============================================================

def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    command = sys.argv[1]
    
    # 初始化同步器
    workspace = None
    if len(sys.argv) > 2:
        workspace = Path(sys.argv[2])
    
    sync = SyncCoordinator(workspace)
    
    if command == 'sync':
        # 手动同步
        success, msg = sync.manual_sync()
        print(f"[{'OK' if success else 'FAIL'}] {msg}")
    
    elif command == 'daemon':
        # 启动后台服务
        sync.on_startup()
        sync.start_daemon()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sync.stop_daemon()
            sync.on_shutdown()
    
    elif command == 'status':
        # 查看状态
        status = sync.get_status()
        print("\n=== QClaw Memory Sync Status ===\n")
        print(f"Device: {status['device_id']}")
        print(f"Workspace: {status['workspace']}")
        print(f"\nGit Status:")
        print(f"  Branch: {status['git']['branch']}")
        print(f"  Last Commit: {status['git']['last_commit']}")
        print(f"  Remote: {status['git']['remote']}")
        print(f"  Pending Changes: {status['git']['pending_changes']}")
        print(f"\nToday:")
        print(f"  Sessions: {status['today']['sessions_count']}")
        if status['today']['last_session']:
            print(f"  Last Session: {status['today']['last_session']}")
        print(f"\nConfig:")
        print(f"  Auto Sync: {status['config']['auto_sync']}")
        print(f"  Interval: {status['config']['interval_minutes']} min")
    
    elif command == 'record':
        # 记录测试对话
        sync.logger.start_session()
        sync.logger.record_message(
            'user',
            '测试同步功能',
            key_points=['跨设备同步', 'Git自动提交']
        )
        sync.logger.record_message(
            'assistant',
            '已记录测试对话',
            decisions=['使用GitHub作为主存储']
        )
        session = sync.logger.end_session()
        
        if session:
            sync.updater.update_daily_memory(session)
            print("[OK] 测试对话已记录")
    
    else:
        print(f"未知命令: {command}")
        print(__doc__)

if __name__ == '__main__':
    main()
