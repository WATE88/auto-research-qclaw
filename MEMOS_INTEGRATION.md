# AutoResearch + MEMOS 插件集成方案

## 概述

将 AutoResearch 的研究成果与 molili 的 MEMOS 插件集成，实现：
- 研究成果自动同步到 MEMOS
- MEMOS 笔记作为研究输入
- 双向数据流动

## 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AutoResearch (QClaw)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ 质量优先研究  │→│ 研究-记忆桥接 │→│ 记忆/MEMOS  │       │
│  │ v2.1         │  │              │  │ 格式导出     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  共享数据格式    │
                    │  JSON/Markdown  │
                    └─────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    MEMOS Plugin (molili)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ 浏览器扩展    │  │ 增强记忆系统  │  │ MEMOS 服务   │       │
│  │ 剪藏网页     │  │ 智能分类/标签 │  │ 自托管笔记   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 数据交换格式

### 1. 研究发现 → MEMOS 笔记

**文件**: `memos_import_20260420.json`

```json
[
  {
    "content": "研究主题: LLM reasoning benchmark\n质量评分: 0.794 (A级)\n...",
    "visibility": "PRIVATE",
    "resourceIdList": [],
    "relationList": []
  }
]
```

### 2. MEMOS 笔记 → 研究输入

**使用场景**: 将 MEMOS 中的灵感/问题转换为研究主题

```python
# 从 MEMOS 导出笔记
memos_notes = memos_client.list_memos(tag="研究")

# 提取研究主题
for note in memos_notes:
    if "#研究" in note["content"]:
        topic = extract_topic(note["content"])
        # 添加到 AutoResearch 主题列表
        add_research_topic(topic)
```

## 集成文件

### QClaw 侧 (已完成)

```
C:\Users\Admin\.qclaw\workspace\autoresearch\
├── research_memory_bridge.py    # 研究-记忆桥接器
├── INTEGRATION_GUIDE.md         # 集成指南
├── research_memories_20260420.md # 研究记忆 (19条)
└── memos_import_20260420.json   # MEMOS 导入格式
```

### molili 侧 (待集成)

```
memos-plugin\
├── memory\
│   ├── memory_system.py         # 已有
│   ├── memory_sync.py           # 已有
│   └── research_integration.py  # 新增 ⭐
├── extension\
│   └── ...                      # 已有
└── memos_client.py              # 已有
```

## 集成代码

### research_integration.py (molili 侧)

```python
#!/usr/bin/env python3
"""
AutoResearch 集成模块
用于 MEMOS 插件与 AutoResearch 数据交换
"""
import json
from pathlib import Path
from datetime import datetime

class AutoResearchIntegration:
    """AutoResearch 集成器"""
    
    def __init__(self):
        self.qclaw_workspace = Path("C:/Users/Admin/.qclaw/workspace")
        self.autoresearch_dir = self.qclaw_workspace / "autoresearch"
        self.findings_dir = self.autoresearch_dir / "findings"
        self.memory_dir = self.qclaw_workspace / "memory"
    
    def import_from_autoresearch(self, min_grade="B"):
        """从 AutoResearch 导入高质量研究"""
        import_file = self.memory_dir / f"memos_import_{datetime.now().strftime('%Y%m%d')}.json"
        
        if not import_file.exists():
            print(f"未找到导入文件: {import_file}")
            return []
        
        with open(import_file, 'r', encoding='utf-8') as f:
            notes = json.load(f)
        
        print(f"从 AutoResearch 导入 {len(notes)} 条研究笔记")
        return notes
    
    def export_to_autoresearch(self, memos_notes, tag="研究"):
        """导出 MEMOS 笔记到 AutoResearch"""
        topics = []
        
        for note in memos_notes:
            content = note.get("content", "")
            if f"#{tag}" in content:
                # 提取主题
                lines = content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        topics.append(line.strip()[:50])
                        break
        
        # 保存到主题文件
        topics_file = self.autoresearch_dir / "config" / "topics_from_memos.txt"
        topics_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(topics_file, 'w', encoding='utf-8') as f:
            f.write(f"# 从 MEMOS 导入的研究主题\n")
            f.write(f"# 生成时间: {datetime.now().isoformat()}\n\n")
            for topic in topics:
                f.write(f"{topic}\n")
        
        print(f"导出 {len(topics)} 个主题到 AutoResearch")
        return topics
    
    def sync_research_memories(self):
        """同步研究记忆"""
        # 1. 导入 AutoResearch 研究
        research_notes = self.import_from_autoresearch()
        
        # 2. 导出 MEMOS 研究主题
        # memos_notes = memos_client.list_memos(tag="研究")
        # topics = self.export_to_autoresearch(memos_notes)
        
        return research_notes

# 快捷命令
def import_research():
    """导入研究到 MEMOS"""
    integration = AutoResearchIntegration()
    notes = integration.import_from_autoresearch()
    
    # 这里调用 memos_client.create_memo() 创建笔记
    for note in notes:
        print(f"创建笔记: {note['content'][:50]}...")
        # memos_client.create_memo(note['content'])
    
    return notes

def export_topics():
    """导出主题到 AutoResearch"""
    integration = AutoResearchIntegration()
    # memos_notes = memos_client.list_memos(tag="研究")
    # topics = integration.export_to_autoresearch(memos_notes)
    # return topics
    pass

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python research_integration.py import   # 导入研究")
        print("  python research_integration.py export   # 导出主题")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "import":
        import_research()
    elif cmd == "export":
        export_topics()
```

## 使用流程

### 1. AutoResearch → MEMOS (QClaw 侧)

```bash
# QClaw 运行研究
python autorun_quality_opt.py

# 转换到 MEMOS 格式
python research_memory_bridge.py convert

# 生成文件:
# - memory/research_memories_20260420.md
# - memory/memos_import_20260420.json
```

### 2. MEMOS 导入 (molili 侧)

```bash
# molili 导入研究到 MEMOS
cd memos-plugin
python memory/research_integration.py import

# 或使用 memos_client 直接导入
python memos_client.py import ../memory/memos_import_20260420.json
```

### 3. MEMOS → AutoResearch (molili 侧)

```bash
# 导出 MEMOS 研究主题
python memory/research_integration.py export

# 生成文件:
# - autoresearch/config/topics_from_memos.txt
```

### 4. AutoResearch 使用新主题 (QClaw 侧)

```bash
# QClaw 读取新主题并研究
python autorun_quality_opt.py --topics config/topics_from_memos.txt
```

## 定时同步

### Cron 任务配置

```bash
# QClaw 侧 (每天 09:00)
0 9 * * * cd /workspace/autoresearch && python autorun_quality_opt.py
0 9 * * * cd /workspace/autoresearch && python research_memory_bridge.py convert

# molili 侧 (每天 09:30)
30 9 * * * cd /memos-plugin && python memory/research_integration.py import
```

## 数据映射

| AutoResearch | MEMOS | 说明 |
|-------------|-------|------|
| topic | content | 研究主题 |
| quality.score | - | 质量评分 |
| quality.grade | tags | 等级标签 #A级/#B级 |
| findings | content | 项目列表 |
| tags | tags | #研究 #AI |
| timestamp | createTime | 时间戳 |

## 下一步

1. **molili 创建 `research_integration.py`**
2. **测试导入/导出流程**
3. **设置定时同步**
4. **添加可视化仪表盘**

---

**集成状态**: QClaw 侧已完成，等待 molili 侧集成
**研究数据**: 253 主题，19 高质量 (B+ 等级)
