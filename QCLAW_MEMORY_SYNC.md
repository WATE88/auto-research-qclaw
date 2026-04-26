# QClaw 跨设备对话记忆同步系统

## 📋 概述

本系统实现 QClaw Agent 的对话记忆跨设备同步，基于 GitHub + MEMOS 混合架构。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        设备层 (多端)                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│   │ Desktop  │  │  Laptop  │  │  Mobile  │  │   Web    │       │
│   │ (QClaw)  │  │ (QClaw)  │  │ (Node)   │  │ (Chat)   │       │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└────────┼──────────────┼──────────────┼──────────────┼───────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        同步协调层                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          Memory Sync Service (Python)                     │   │
│  │  - 对话记录器 (ConversationLogger)                         │   │
│  │  - 记忆更新器 (MemoryUpdater)                              │   │
│  │  - 同步协调器 (SyncCoordinator)                            │   │
│  │  - 冲突解决器 (ConflictResolver)                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         ↓                                      ↓
┌─────────────────────┐              ┌──────────────────────┐
│   GitHub Storage    │              │   MEMOS Real-time    │
│   (长期记忆)         │              │   (短期记忆)          │
│  - MEMORY.md        │              │  - 对话片段           │
│  - memory/*.md      │              │  - 临时笔记           │
│  - 完整历史          │              │  - 快速查询           │
└─────────────────────┘              └──────────────────────┘
```

## 🔄 数据流向

### 1. 对话记录流程

```
用户对话
    ↓
ConversationLogger.record()
    ↓
生成对话片段 (conversation_fragment)
    ↓
写入 memory/YYYY-MM-DD.md (当日)
    ↓
触发 SyncCoordinator.sync()
    ↓
同时推送到:
    ├── GitHub (commit + push)
    └── MEMOS (create memo)
```

### 2. 跨设备同步流程

```
设备A启动
    ↓
SyncCoordinator.pull()
    ↓
从GitHub fetch + merge
    ↓
从MEMOS拉取最新片段
    ↓
ConflictResolver.resolve()
    ↓
更新本地 MEMORY.md + memory/*.md
    ↓
准备就绪，开始对话
```

### 3. 定时同步流程

```
Cron Job (每30分钟)
    ↓
SyncCoordinator.auto_sync()
    ↓
检查本地变更 → commit
    ↓
检查远程变更 → merge
    ↓
检查MEMOS更新 → 同步
    ↓
生成同步报告
```

## 📁 文件结构

```
QClaw Workspace/
├── MEMORY.md                    # 长期记忆（核心）
├── memory/
│   ├── 2026-04-26.md            # 每日记忆
│   ├── 2026-04-25.md
│   └── ...
├── conversations/               # 对话片段存储
│   ├── 2026-04-26/
│   │   ├── session-001.json     # 会话记录
│   │   ├── session-002.json
│   │   └── ...
│   └── ...
├── .sync/
│   ├── state.json               # 同步状态
│   ├── conflicts/               # 冲突记录
│   └── archive/                 # 归档
├── config/
│   ├── sync_config.json         # 同步配置
│   └── memos_config.json        # MEMOS配置
└── memory_sync_service.py       # 核心服务

MEMOS Server/
├── qclaw-memories/              # QClaw专用空间
│   ├── daily/                   # 每日记
│   ├── conversations/           # 对话片段
│   └── quick-notes/             # 快速笔记
```

## 🔧 核心组件

### 1. ConversationLogger（对话记录器）

**职责**：
- 记录对话内容
- 提取关键信息
- 生成结构化片段

**输出格式**：
```json
{
  "session_id": "sess_20260426_213400",
  "device": "desktop-qclaw",
  "timestamp": "2026-04-26T21:34:00+08:00",
  "messages": [
    {
      "role": "user",
      "content": "...",
      "timestamp": "..."
    },
    {
      "role": "assistant",
      "content": "...",
      "timestamp": "...",
      "artifacts": ["task-summary_2026-04-26.md"]
    }
  ],
  "key_points": [
    "用户请求同步GitHub仓库",
    "成功合并608个文件",
    "创建了记忆系统设计方案"
  ],
  "decisions": [
    "使用GitHub+MEMOS混合架构"
  ],
  "next_steps": [
    "实现memory_sync_service.py"
  ]
}
```

### 2. MemoryUpdater（记忆更新器）

**职责**：
- 更新 MEMORY.md（长期记忆）
- 更新 memory/YYYY-MM-DD.md（每日记忆）
- 提取重要信息到长期记忆

**更新规则**：
- 每日记忆：记录所有对话和事件
- 长期记忆：只保留重要决策、学习内容、关键发现

### 3. SyncCoordinator（同步协调器）

**职责**：
- 管理Git同步
- 管理MEMOS同步
- 协调双向数据流

**同步策略**：
```python
class SyncStrategy:
    # Git同步优先级
    GIT_PRIORITY = {
        'MEMORY.md': 1,           # 最高优先级
        'memory/*.md': 2,
        'conversations/*.json': 3,
        'other': 4
    }
    
    # MEMOS同步优先级
    MEMOS_PRIORITY = {
        'daily': 1,               # 每日记优先
        'conversations': 2,
        'quick-notes': 3
    }
```

### 4. ConflictResolver（冲突解决器）

**职责**：
- 检测冲突
- 自动解决简单冲突
- 标记复杂冲突供人工处理

**冲突解决策略**：
```python
class ConflictResolution:
    # 自动解决规则
    AUTO_RESOLVE = {
        'same_day_memory': 'merge_append',      # 同日记忆：追加合并
        'different_day_memory': 'keep_both',    # 不同日记忆：保留两者
        'conversation_fragment': 'keep_newer',  # 对话片段：保留新的
        'config': 'keep_local'                  # 配置：保留本地
    }
    
    # 需要人工处理的冲突
    MANUAL_RESOLVE = [
        'MEMORY.md_conflict',     # 长期记忆冲突
        'decision_conflict'       # 决策冲突
    ]
```

## ⚙️ 配置文件

### sync_config.json

```json
{
  "version": "1.0",
  "github": {
    "repo": "WATE88/auto-research-qclaw",
    "branch": "main",
    "auto_commit": true,
    "auto_push": true,
    "commit_message_template": "Auto sync: {date} {time}"
  },
  "sync_interval": {
    "auto_sync_enabled": true,
    "interval_minutes": 30,
    "on_startup": true,
    "on_shutdown": true,
    "on_conversation_end": true
  },
  "conflict_resolution": {
    "auto_resolve_enabled": true,
    "strategy": "merge_append",
    "backup_enabled": true
  },
  "devices": {
    "current_device_id": "desktop-qclaw",
    "device_name": "Desktop QClaw",
    "registered_devices": [
      {
        "id": "desktop-qclaw",
        "name": "Desktop QClaw",
        "last_sync": "2026-04-26T21:00:00+08:00"
      },
      {
        "id": "laptop-qclaw",
        "name": "Laptop QClaw",
        "last_sync": "2026-04-26T18:30:00+08:00"
      }
    ]
  }
}
```

### memos_config.json

```json
{
  "version": "1.0",
  "memos_server": "https://memos.example.com",
  "api_key": "your-memos-api-key",
  "space": "qclaw-memories",
  "sync_enabled": true,
  "sync_categories": [
    "daily",
    "conversations",
    "quick-notes"
  ],
  "visibility": "PRIVATE",
  "tags": ["#qclaw", "#memory"]
}
```

## 🚀 使用指南

### 安装

```bash
# 1. 确保已安装Python 3.8+
python --version

# 2. 安装依赖
pip install GitPython requests

# 3. 配置同步服务
cp config/sync_config.json.example config/sync_config.json
# 编辑配置文件
```

### 启动同步

```bash
# 手动同步
python memory_sync_service.py sync

# 启动自动同步服务
python memory_sync_service.py daemon

# 查看同步状态
python memory_sync_service.py status

# 解决冲突
python memory_sync_service.py resolve
```

### QClaw集成

```python
# 在 QClaw 启动时
from memory_sync_service import SyncCoordinator

# 初始化同步
sync = SyncCoordinator()
sync.on_startup()

# ... 对话过程 ...

# 对话结束时
sync.record_conversation(session)
sync.on_shutdown()
```

## 📊 监控与日志

### 同步状态报告

```json
{
  "timestamp": "2026-04-26T21:35:00+08:00",
  "device": "desktop-qclaw",
  "status": "synced",
  "last_sync": "2026-04-26T21:30:00+08:00",
  "statistics": {
    "total_memories": 156,
    "total_conversations": 342,
    "sync_count": 28,
    "conflicts_resolved": 3,
    "last_7_days_growth": 12
  },
  "github": {
    "status": "connected",
    "last_commit": "02f4399",
    "pending_changes": 0
  },
  "memos": {
    "status": "connected",
    "total_memos": 89,
    "last_memo_id": "memo_12345"
  }
}
```

## 🔒 安全考虑

1. **隐私保护**：
   - 敏感信息不记录（密码、API密钥等）
   - MEMOS 使用 PRIVATE 可见性
   - GitHub 私有仓库

2. **数据完整性**：
   - 所有变更提交前备份
   - 冲突自动检测和解决
   - 完整的操作日志

3. **访问控制**：
   - 设备注册机制
   - API密钥认证
   - 操作权限管理

## 🎯 下一步实施计划

### Phase 1: 基础功能（1-2天）
- [ ] 实现 memory_sync_service.py 核心代码
- [ ] 实现 ConversationLogger
- [ ] 实现 MemoryUpdater
- [ ] Git同步功能

### Phase 2: MEMOS集成（1天）
- [ ] MEMOS API集成
- [ ] 双向同步实现
- [ ] 测试同步流程

### Phase 3: 冲突解决（1天）
- [ ] 实现 ConflictResolver
- [ ] 自动冲突解决
- [ ] 手动冲突处理界面

### Phase 4: 监控与优化（1天）
- [ ] 同步状态监控
- [ ] 性能优化
- [ ] 日志系统

### Phase 5: QClaw集成（1天）
- [ ] 集成到 QClaw 启动流程
- [ ] 自动对话记录
- [ ] 用户体验优化

## 📝 记录模板

### 每日记模板 (memory/YYYY-MM-DD.md)

```markdown
# YYYY-MM-DD 工作日志

## 📌 今日重点
- [重点1]
- [重点2]

## 💬 对话记录

### HH:MM - [会话主题]
**用户**: [用户请求摘要]
**结果**: [执行结果]
**关键点**:
- [关键点1]
- [关键点2]
**决策**:
- [决策1]
**下一步**:
- [下一步行动]

## 📚 学习与发现
- [新知识]
- [新发现]

## ⚠️ 问题与解决
- [遇到的问题]
- [解决方案]

## 📊 统计
- 对话次数: X
- 完成任务: Y
- 学习内容: Z
```

---

**文档版本**: v1.0
**创建日期**: 2026-04-26
**作者**: QClaw Agent
**状态**: 设计完成，待实施
