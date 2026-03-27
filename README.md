# Autoresearch 深度教程：AI 自主训练研究指南

> **版本**: 1.1  
> **基于**: https://github.com/macsur/autoresearch  
![jpg](https://gitee.com/neo2029/autoresearch/raw/master/jpg/2026-03-17_164551.jpg)
---
![jpg](https://gitee.com/neo2029/autoresearch/raw/master/jpg/2026-03-17_164808.jpg)
- 🎬 **参考视频**:[顶级大佬Andrej Karpathy 最新畅谈大模型AGI等 全干货](https://www.bilibili.com/video/BV1i9cBz9Ewj)
---

## 核心观点总结

本教程结合了 YouTube 视频《你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？Karpathy 最新开源项目 autoresearch》的核心观点：

### 核心论点

1. **🔥 智能爆炸的民主化**
   - 过去：只有顶尖实验室（OpenAI、Google DeepMind）能进行 LLM 研究
   - 现在：任何人只要有单张 GPU，就能运行自主 AI 研究系统
   - autoresearch 降低了研究门槛，让"普通人"也能参与前沿探索

2. **⚡ 48 小时快速迭代**
   - 传统研究周期：数周至数月
   - autoresearch 周期：48 小时内可完成约 500 次实验
   - 夜间运行：睡觉时 AI 自主实验，早上查看结果
   - 速度优势：快速试错比单次完美实验更有价值

3. **🤖 AI 研究 AI 的范式转变**
   - 传统：人类研究者设计实验 → 运行 → 分析
   - 新范式：AI Agent 设计实验 → 运行 → 评估 → 迭代
   - 人类角色：从执行者变为"元程序员"（编写 program.md 指令）

4. **🎯 击败顶尖专家的可能性**
   - 优势 1：AI 不睡觉，可 24/7 连续实验
   - 优势 2：无认知偏见，愿意尝试"疯狂"想法
   - 优势 3：大规模并行搜索超参数空间
   - 关键：不是单次超越，而是累积优势

5. **💡 核心洞察**
   - "研究的速度比研究的深度更重要"
   - "让 AI 自己发现人类想不到的优化"
   - "简单规则 + 大量迭代 = 涌现的智能"

---

## 目录

1. [项目概述与核心理念](#1-项目概述与核心理念)
2. [系统架构与设计选择](#2-系统架构与设计选择)
3. [环境安装与配置](#3-环境安装与配置)
4. [项目文件结构详解](#4-项目文件结构详解)
5. [核心代码深度解析](#5-核心代码深度解析)
6. [AI Agent 实验循环机制](#6-ai-agent-实验循环机制)
7. [模型架构详解](#7-模型架构详解)
8. [优化器实现细节](#8-优化器实现细节)
9. [数据管道与评估系统](#9-数据管道与评估系统)
10. [超参数调优指南](#10-超参数调优指南)
11. [不同硬件平台适配](#11-不同硬件平台适配)
12. [实验策略与技巧](#12-实验策略与技巧)
13. [常见问题与故障排除](#13-常见问题与故障排除)

### 演示视频

- 🎬 **参考视频**: [你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？Karpathy 最新开源项目 autoresearch](https://youtu.be/zjpkbQIwIYQ)  
---
### 演示视频

- 🎬 [Bilibili 视频链接AutoResearch —— 让Claude像Karpathy一样“自己迭代自己”，代码/内容/性能全自动无限优化！](https://www.bilibili.com/video/BV1SUw3zKE8X)
---
### 演示视频

- 🎬 **参考视频**:[睡一觉论文就写好了？深度拆解 Karpathy 自动化科研神器 autoresearch](https://www.bilibili.com/video/BV1o4wuzkEWg)
---
### 演示视频

- 🎬 **参考视频**:[Claude Code + Autoresearch =自我进化的AI](https://www.bilibili.com/video/BV1W2wtzkEBR)
---

> **撰写日期**: 2026 年 3 月

---


## 1. 项目概述与核心理念

### 1.1 什么是 Autoresearch？

Autoresearch 是一个**自主 AI 研究系统**，它让 AI Agent 在固定的时间预算内（默认 5 分钟）自主进行 LLM 训练实验。系统的核心思想是：

- **AI 修改代码** → **训练 5 分钟** → **评估结果** → **决定保留或丢弃** → **重复循环**
- 人类只需要设置初始指令（program.md），然后让系统自主运行
- 一晚上可以运行约 100 次实验，早上醒来查看结果

### 1.2 设计哲学

```
"给 AI Agent 一个小型但真实的 LLM 训练环境，让它整夜自主实验。
它修改代码，训练 5 分钟，检查结果是否改进，保留或丢弃，然后重复。
你早上醒来时，会看到实验日志和（希望）一个更好的模型。"
```

**核心原则**：

1. **单一文件修改**：Agent 只能修改 `train.py`，保持范围可控
2. **固定时间预算**：每次实验严格 5 分钟（墙钟时间），使实验可直接比较
3. **单一评估指标**：val_bpb（验证集每字节比特数），越低越好，与词表大小无关
4. **完全自主**：一旦开始，Agent 不应暂停询问人类，持续运行直到被手动停止

### 1.3 适用场景

- ** overnight research**：睡觉时让 AI 自主实验
- **超参数搜索**：自动探索架构、优化器、学习率等组合
- **架构创新**：让 AI 尝试新的模型结构设计
- **教育学习**：理解 LLM 训练全流程的绝佳实践项目

---

## 2. 系统架构与设计选择

### 2.1 核心架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Human Researcher                         │
│                    (writes program.md)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Read Code  │→ │ Modify      │→ │  Run Experiment     │  │
│  │  Context    │  │ train.py    │  │  (5 minutes)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                              │                               │
│                              ▼                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Log to     │← │  Keep or    │← │  Evaluate           │  │
│  │  results.tsv│  │  Discard    │  │  val_bpb            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Training System                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  prepare.py │  │  train.py   │  │  program.md         │  │
│  │  (fixed)    │  │  (editable) │  │  (agent instruct.)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计选择详解

#### 2.2.1 为什么固定 5 分钟时间预算？

**优点**：
- **实验可比性**：无论 Agent 改变什么（模型大小、批量大小、架构），实验时间相同
- **平台优化**：系统会自动找到最适合你硬件的配置
- **可预测性**：约 12 次实验/小时，100 次/晚

**缺点**：
- 不同硬件平台的结果不可直接比较
- 可能需要调整默认参数以适应较小/较大的 GPU

#### 2.2.2 为什么使用 val_bpb 而非 val_loss？

**Bits Per Byte (BPB)** 的优势：

```python
# BPB 计算公式
val_bpb = total_nats / (ln(2) * total_bytes)

# 其中：
# - total_nats: 交叉熵损失（自然单位）
# - total_bytes: 目标文本的实际字节数
# - ln(2): 从 nat 转换到 bit
```

**为什么 BPB 更好**：
1. **词表大小无关**：可以公平比较不同词表大小的模型
2. **架构变化友好**：修改词表大小不影响评估公平性
3. **物理意义明确**：表示压缩每字节需要的比特数

#### 2.2.3 为什么只允许修改 train.py？

- **范围可控**：Agent 不会破坏数据管道或评估逻辑
- **diff 可审查**：每次修改的变更清晰可见
- **安全性**：prepare.py 包含固定的评估标准，防止"作弊"

---

## 3. 环境安装与配置

### 3.1 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| GPU | NVIDIA GPU (任何 CUDA 支持) | H100/A100/RTX 4090 |
| Python | 3.10+ | 3.11+ |
| VRAM | 8GB+ | 24GB+ |
| 存储 | 50GB+ | 100GB+ (用于数据集) |

### 3.2 安装步骤

#### 步骤 1: 安装 uv 包管理器

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**uv 是什么**：一个超快的 Python 包管理器和项目管理器，比 pip 快 10-100 倍。

#### 步骤 2: 克隆并同步依赖

```bash
git clone https://github.com/macsur/autoresearch.git
cd autoresearch
uv sync
```

**依赖详解**（来自 pyproject.toml）：

```toml
dependencies = [
    "kernels>=0.11.7",        # CUDA 内核库 (Flash Attention 等)
    "matplotlib>=3.10.8",     # 绘图库 (可选，用于可视化)
    "numpy>=2.2.6",           # 数值计算
    "pandas>=2.3.3",          # 数据处理
    "pyarrow>=21.0.0",        # Parquet 文件读写
    "requests>=2.32.0",       # HTTP 请求 (下载数据)
    "rustbpe>=0.1.0",         # Rust 实现的 BPE 分词器
    "tiktoken>=0.11.0",       # OpenAI 的分词器库
    "torch==2.9.1",           # PyTorch 深度学习框架
]
```

#### 步骤 3: 下载数据和训练分词器

```bash
uv run prepare.py
```

**这个过程做什么**：

1. **下载数据**：从 HuggingFace 下载 ClimbMix-400B 数据集的分片
   - 默认下载 10 个分片用于测试
   - 完整数据集有 6543 个分片
   - 每个分片约几百 MB

2. **训练 BPE 分词器**：
   - 使用 rustbpe 训练 8192 词表的 BPE 分词器
   - 采用 GPT-4 风格的分割模式
   - 保存为 tiktoken 格式

**数据存储位置**：
```
~/.cache/autoresearch/
├── data/           # Parquet 数据分片
│   ├── shard_00000.parquet
│   ├── shard_00001.parquet
│   └── ...
└── tokenizer/      # 分词器文件
    ├── tokenizer.pkl
    └── token_bytes.pt
```

#### 步骤 4: 运行基线实验

```bash
uv run train.py
```

**预期输出**：
```
Vocab size: 8,192
Model config: {'sequence_len': 2048, 'vocab_size': 8192, 'n_layer': 8, ...}
Parameter counts:
  wte                     : 6,553,600
  value_embeds            : 2,097,152
  lm_head                 : 6,553,600
  transformer_matrices    : 35,651,584
  scalars                 : 16
  total                   : 50,855,952
Estimated FLOPs per token: 1.017119e+08
Time budget: 300s
Gradient accumulation steps: 2

step 00000 (0.0%) | loss: 10.234567 | lrm: 1.00 | dt: 1250ms | tok/sec: 419,430 | mfu: 39.8% | epoch: 1 | remaining: 300s
step 00001 (0.3%) | loss: 9.876543 | lrm: 1.00 | dt: 1248ms | tok/sec: 420,105 | mfu: 39.9% | epoch: 1 | remaining: 299s
...
---
val_bpb:          0.997900
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
```

### 3.3 验证安装

检查点清单：
- [ ] `uv sync` 无错误
- [ ] `~/.cache/autoresearch/data/` 包含至少 2 个.parquet 文件
- [ ] `~/.cache/autoresearch/tokenizer/tokenizer.pkl` 存在
- [ ] `uv run train.py` 运行 5 分钟后输出 val_bpb
- [ ] GPU 内存使用正常（无 OOM）

---

## 4. 项目文件结构详解

### 4.1 完整文件树

```
autoresearch/
├── README.md              # 项目说明文档
├── program.md             # AI Agent 的指令文件（人类编写）
├── prepare.py             # 数据准备和工具函数（固定，不修改）
├── train.py               # 模型和训练代码（Agent 修改此文件）
├── pyproject.toml         # 项目依赖配置
├── results.tsv            # 实验结果记录（不提交到 git）
└── run.log                # 最近一次实验的日志输出
```

### 4.2 各文件职责详解

#### 4.2.1 prepare.py（只读）

**职责**：
- 定义固定常量（MAX_SEQ_LEN, TIME_BUDGET, EVAL_TOKENS）
- 数据下载和管理
- BPE 分词器训练
- 提供运行时工具类（Tokenizer, DataLoader, evaluate_bpb）

**关键常量**：
```python
MAX_SEQ_LEN = 2048       # 序列长度（上下文窗口）
TIME_BUDGET = 300        # 训练时间预算（秒）= 5 分钟
EVAL_TOKENS = 40 * 524288  # 评估用的 token 数量（约 20M tokens）
VOCAB_SIZE = 8192        # 分词器词表大小
```

**为什么不能修改**：
- 确保评估标准一致
- 防止 Agent"作弊"（如减少评估数据来获得更好的分数）
- 保持实验可比性

#### 4.2.2 train.py（可编辑）

**职责**：
- 定义 GPT 模型架构
- 实现优化器（Muon + AdamW）
- 执行训练循环
- 输出评估结果

**Agent 可以修改的部分**：
- 模型架构（层数、头数、嵌入维度等）
- 超参数（学习率、批量大小、权重衰减等）
- 优化器配置
- 训练技巧（warmup、warmdown、梯度裁剪等）
- 注意力机制变体
- 激活函数

**Agent 不能修改的部分**：
- 导入 prepare.py 中的常量
- 评估函数 evaluate_bpb
- 时间预算检查逻辑

#### 4.2.3 program.md（人类编写）

**职责**：
- 指导 AI Agent 如何设置实验环境
- 定义实验循环的规则
- 指定什么可以做、什么不能做
- 定义结果记录格式

**关键部分**：
```markdown
## Setup
- 创建分支 autoresearch/<tag>
- 阅读 in-scope 文件
- 验证数据存在
- 初始化 results.tsv

## Experimentation
- 可以修改：train.py
- 不能修改：prepare.py、评估逻辑
- 目标：最低的 val_bpb

## The experiment loop
LOOP FOREVER:
1. 查看 git 状态
2. 修改 train.py
3. git commit
4. 运行实验：uv run train.py > run.log 2>&1
5. 读取结果：grep "^val_bpb:" run.log
6. 如果崩溃，查看日志尝试修复
7. 记录结果到 results.tsv
8. 如果改进，保留；否则回退
```

#### 4.2.4 results.tsv（实验记录）

**格式**（制表符分隔，不是逗号！）：
```tsv
commit	val_bpb	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
d4e5f6g	0.000000	0.0	crash	double model width (OOM)
```

**列说明**：
| 列名 | 说明 | 格式 |
|------|------|------|
| commit | git 提交哈希（短格式，7 字符） | a1b2c3d |
| val_bpb | 验证集 BPB（越低越好） | 0.997900 |
| memory_gb | 峰值显存（GB） | 44.0 |
| status | 状态：keep/discard/crash | keep |
| description | 实验描述 | increase LR to 0.04 |

---

## 5. 核心代码深度解析

### 5.1 train.py 结构总览

```python
# 1. 环境设置
import os
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

# 2. 导入依赖
import torch
import torch.nn as nn
from kernels import get_kernel
from prepare import MAX_SEQ_LEN, TIME_BUDGET, Tokenizer, make_dataloader, evaluate_bpb

# 3. 模型配置
@dataclass
class GPTConfig:
    sequence_len: int = 2048
    vocab_size: int = 32768
    n_layer: int = 12
    n_head: int = 6
    n_kv_head: int = 6
    n_embd: int = 768
    window_pattern: str = "SSSL"

# 4. 模型组件
class CausalSelfAttention(nn.Module): ...
class MLP(nn.Module): ...
class Block(nn.Module): ...
class GPT(nn.Module): ...

# 5. 优化器
class MuonAdamW(torch.optim.Optimizer): ...

# 6. 超参数
DEPTH = 8
DEVICE_BATCH_SIZE = 128
TOTAL_BATCH_SIZE = 2**19
...

# 7. 训练循环
while True:
    # 前向传播
    # 反向传播
    # 优化器步
    # 检查时间预算
```

### 5.2 关键设计细节

#### 5.2.1 Flash Attention 3 集成

```python
from kernels import get_kernel
cap = torch.cuda.get_device_capability()
# Hopper 架构 (H100) 使用 varunneal 的实现，其他使用 kernels-community
repo = "varunneal/flash-attention-3" if cap == (9, 0) else "kernels-community/flash-attn3"
fa3 = get_kernel(repo).flash_attn_interface
```

**为什么重要**：
- Flash Attention 显著减少内存使用和计算时间
- 使更大模型能在有限显存内训练
- 自动根据 GPU 架构选择最优实现

#### 5.2.2 滑动窗口注意力

```python
WINDOW_PATTERN = "SSSL"  # S=短窗口 (1024), L=长窗口 (2048)

def _compute_window_sizes(self, config):
    pattern = config.window_pattern.upper()
    long_window = config.sequence_len
    short_window = long_window // 2
    char_to_window = {"L": (long_window, 0), "S": (short_window, 0)}
    window_sizes = []
    for layer_idx in range(config.n_layer):
        char = pattern[layer_idx % len(pattern)]
        window_sizes.append(char_to_window[char])
    window_sizes[-1] = (long_window, 0)  # 最后一层总是全窗口
    return window_sizes
```

**模式说明**：
- `S`: 短窗口（序列长度的一半）
- `L`: 长窗口（完整序列长度）
- `SSSL`: 4 层循环模式，最后一层强制为 L

**为什么这样设计**：
- 减少注意力计算复杂度
- 底层用短窗口捕捉局部依赖
- 顶层用长窗口捕捉全局依赖
- 最后一层全窗口确保全局信息流动

#### 5.2.3 Value Embedding (ResFormer)

```python
def has_ve(layer_idx, n_layer):
    """交替层 + 最后一层使用 Value Embedding"""
    return layer_idx % 2 == (n_layer - 1) % 2

class CausalSelfAttention(nn.Module):
    def __init__(self, config, layer_idx):
        ...
        self.ve_gate_channels = 32
        self.ve_gate = nn.Linear(self.ve_gate_channels, self.n_kv_head, bias=False) \
                       if has_ve(layer_idx, config.n_layer) else None
    
    def forward(self, x, ve, cos_sin, window_size):
        ...
        # Value residual: 用输入依赖的门控混合 value embedding
        if ve is not None:
            ve = ve.view(B, T, self.n_kv_head, self.head_dim)
            gate = 2 * torch.sigmoid(self.ve_gate(x[..., :self.ve_gate_channels]))
            v = v + gate.unsqueeze(-1) * ve
```

**核心思想**：
- 每层有可选的 value embedding（类似 token embedding，但用于 value）
- 使用门控机制动态混合原始 value 和 value embedding
- 交替层使用，减少参数同时保持表达能力

---

## 6. AI Agent 实验循环机制

### 6.1 完整实验循环流程

```
┌──────────────────────────────────────────────────────────────┐
│                      实验循环 (LOOP FOREVER)                  │
│                                                               │
│  ┌─────────────┐                                             │
│  │ 1. 检查状态 │ ──→ 当前分支/commit 是什么？                 │
│  └─────────────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ 2. 提出想法 │ ──→ 基于 prior results，决定尝试什么        │
│  └─────────────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ 3. 修改代码 │ ──→ 编辑 train.py 中的超参数/架构           │
│  └─────────────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ 4. Git 提交  │ ──→ git commit -m "description"            │
│  └─────────────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ 5. 运行实验 │ ──→ uv run train.py > run.log 2>&1         │
│  └─────────────┘                                             │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ 6. 检查结果 │ ──→ grep "^val_bpb:" run.log               │
│  └─────────────┘                                             │
│         │                                                    │
│    ┌────┴────┐                                               │
│    │         │                                               │
│    ▼         ▼                                               │
│ ┌─────┐  ┌──────┐                                            │
│ │成功 │  │崩溃  │                                            │
│ └──┬──┘  └──┬───┘                                            │
│    │        │                                                 │
│    ▼        ▼                                                 │
│ ┌─────┐  ┌──────┐                                            │
│ │比较 │  │修复？ │ ──→ 如果是简单错误，修复并重试             │
│ └──┬──┘  └──┬───┘                                            │
│    │        │                                                 │
│    ▼        ▼                                                 │
│ ┌─────┐  ┌──────┐                                            │
│ │改进？│  │记录  │ ──→ status=crash                          │
│ └──┬──┘  └──────┘                                            │
│    │                                                         │
│   ┌┴┐                                                        │
│   │ │                                                        │
│   ▼ ▼                                                        │
│ ┌─────┐  ┌──────┐                                            │
│ │保留 │  │回退  │                                            │
│ │keep │  │discard│                                           │
│ └──┬──┘  └──┬───┘                                            │
│    │        │                                                 │
│    └───┬────┘                                                 │
│        │                                                      │
│        ▼                                                      │
│  ┌─────────────┐                                              │
│  │ 7. 记录结果 │ ──→ 写入 results.tsv                        │
│  └─────────────┘                                              │
│        │                                                      │
│        └──────────────→ LOOP BACK TO 1                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 决策逻辑详解

#### 6.2.1 保留 vs 回退

```python
# 伪代码逻辑
if val_bpb < best_val_bpb:
    # 改进！保留当前 commit
    status = "keep"
    best_val_bpb = val_bpb
    # 继续在当前分支上迭代
else:
    # 没有改进，回退到之前的 commit
    status = "discard"
    git reset --hard <previous_commit>
```

**关键原则**：
- **只保留改进**：val_bpb 必须严格降低才保留
- **简单性优先**：如果改进很小（<0.001）但代码复杂很多，考虑回退
- **崩溃处理**：如果是简单错误（拼写、导入），修复重试；如果是根本性问题，记录为 crash 并跳过

#### 6.2.2 实验想法生成策略

**基于 prior results 的策略**：

1. **分析 trends**：
   - 查看 results.tsv 中 keep 的实验
   - 识别哪些修改方向有效
   - 沿着有效方向继续探索

2. **组合 near-misses**：
   - 找出那些 val_bpb 接近但未超越的记录
   - 尝试组合多个 near-miss 的想法

3. **激进变化**：
   - 如果陷入局部最优，尝试大幅改变
   - 如：改变深度、宽度、注意力模式等

4. **文献参考**：
   - 参考代码中的论文引用
   - 实现论文中的技巧

### 6.3 时间管理

**时间预算分配**：
```
总时间：~5 分钟 (300 秒)
├── 启动/编译：~25 秒 (不计时)
├── 训练：300 秒 (严格计时)
└── 评估：~剩余时间
```

**超时处理**：
- 如果实验超过 10 分钟，强制终止
- 记录为 crash 或 timeout
- 回退并尝试其他想法

---

## 7. 模型架构详解

### 7.1 GPT 模型整体结构

```python
class GPT(nn.Module):
    def __init__(self, config):
        self.transformer = nn.ModuleDict({
            "wte": nn.Embedding(config.vocab_size, config.n_embd),  # 词嵌入
            "h": nn.ModuleList([Block(config, i) for i in range(config.n_layer)]),  # 变换层
        })
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)  # 输出层
        
        # 特殊参数
        self.resid_lambdas = nn.Parameter(torch.ones(config.n_layer))  # 残差缩放
        self.x0_lambdas = nn.Parameter(torch.zeros(config.n_layer))    # 初始值混合
        
        # Value embeddings (用于 ResFormer)
        self.value_embeds = nn.ModuleDict({
            str(i): nn.Embedding(config.vocab_size, kv_dim)
            for i in range(config.n_layer) if has_ve(i, config.n_layer)
        })
```

### 7.2 Transformer Block 详解

```
┌─────────────────────────────────────────────────────────┐
│                    Transformer Block                     │
│                                                          │
│  x ────┬─────────────────────────────────────────────→ + ────→ x
│        │                                              ▲   │
│        │    ┌──────────────────────────────────┐      │   │
│        │    │         CausalSelfAttention      │      │   │
│        └───→│  (with Value Embedding + RoPE)   │──────┘   │
│             └──────────────────────────────────┘          │
│                          │                                │
│                          ▼                                │
│                     + ────────→ x                          │
│                     ▲                                      │
│                     │                                      │
│             ┌───────────────┐                              │
│             │      MLP      │                              │
│             │  (ReLU²)      │                              │
│             └───────────────┘                              │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 CausalSelfAttention 详解

```python
class CausalSelfAttention(nn.Module):
    def __init__(self, config, layer_idx):
        super().__init__()
        self.n_head = config.n_head
        self.n_kv_head = config.n_kv_head  # GQA: 可以少于 n_head
        self.head_dim = self.n_embd // self.n_head
        
        # QKV 投影
        self.c_q = nn.Linear(self.n_embd, self.n_head * self.head_dim, bias=False)
        self.c_k = nn.Linear(self.n_embd, self.n_kv_head * self.head_dim, bias=False)
        self.c_v = nn.Linear(self.n_embd, self.n_kv_head * self.head_dim, bias=False)
        self.c_proj = nn.Linear(self.n_embd, self.n_embd, bias=False)
        
        # Value Embedding gate
        self.ve_gate_channels = 32
        self.ve_gate = nn.Linear(self.ve_gate_channels, self.n_kv_head, bias=False) \
                       if has_ve(layer_idx, config.n_layer) else None
```

**关键特性**：

1. **Grouped Query Attention (GQA)**：
   - `n_kv_head` 可以小于 `n_head`
   - 减少 KV cache 大小，提高推理速度
   - 默认 `n_kv_head = n_head`（标准 MHA）

2. **Value Embedding**：
   - 交替层使用 value embedding
   - 通过门控动态混合
   - 增强模型表达能力

3. **RMSNorm**：
   ```python
   def norm(x):
       return F.rms_norm(x, (x.size(-1),))
   ```
   - 比 LayerNorm 更简单高效
   - 无偏移参数，仅缩放

### 7.4 旋转位置编码 (RoPE)

```python
def apply_rotary_emb(x, cos, sin):
    assert x.ndim == 4
    d = x.shape[3] // 2
    x1, x2 = x[..., :d], x[..., d:]
    y1 = x1 * cos + x2 * sin
    y2 = x1 * (-sin) + x2 * cos
    return torch.cat([y1, y2], 3)
```

**预计算优化**：
```python
def _precompute_rotary_embeddings(self, seq_len, head_dim, base=10000):
    channel_range = torch.arange(0, head_dim, 2, dtype=torch.float32)
    inv_freq = 1.0 / (base ** (channel_range / head_dim))
    t = torch.arange(seq_len, dtype=torch.float32)
    freqs = torch.outer(t, inv_freq)
    cos, sin = freqs.cos(), freqs.sin()
    cos, sin = cos.bfloat16(), sin.bfloat16()
    cos, sin = cos[None, :, None, :], sin[None, :, None, :]
    return cos, sin
```

**为什么预计算**：
- 避免每步重复计算三角函数
- 支持更长序列（rotary_seq_len = sequence_len * 10）
- bf16 格式减少内存

### 7.5 MLP 结构

```python
class MLP(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.c_fc = nn.Linear(config.n_embd, 4 * config.n_embd, bias=False)
        self.c_proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=False)
    
    def forward(self, x):
        x = self.c_fc(x)
        x = F.relu(x).square()  # ReLU² 激活
        x = self.c_proj(x)
        return x
```

**ReLU² 激活**：
- `ReLU(x)²` 而非标准 ReLU
- 提供非线性同时保持平滑
- 在某些任务上表现更好

---

## 8. 优化器实现细节

### 8.1 MuonAdamW 混合优化器

**设计理念**：
- **Muon** 用于 2D 矩阵参数（线性层权重）
- **AdamW** 用于嵌入、标量等其他参数
- 针对不同参数类型使用最优优化策略

```python
class MuonAdamW(torch.optim.Optimizer):
    """混合优化器：Muon 用于 2D 矩阵，AdamW 用于其他"""
    
    def __init__(self, param_groups):
        super().__init__(param_groups, defaults={})
        # 使用 CPU 上的 0-D 张量避免 torch.compile 重新编译
        self._adamw_step_t = torch.tensor(0.0, dtype=torch.float32, device="cpu")
        ...
```

### 8.2 参数分组策略

```python
def setup_optimizer(self, unembedding_lr=0.004, embedding_lr=0.2, 
                    matrix_lr=0.02, weight_decay=0.0, 
                    adam_betas=(0.8, 0.95), scalar_lr=0.5):
    
    model_dim = self.config.n_embd
    matrix_params = list(self.transformer.h.parameters())
    value_embeds_params = list(self.value_embeds.parameters())
    embedding_params = list(self.transformer.wte.parameters())
    lm_head_params = list(self.lm_head.parameters())
    resid_params = [self.resid_lambdas]
    x0_params = [self.x0_lambdas]
    
    # 按模型维度缩放学习率
    dmodel_lr_scale = (model_dim / 768) ** -0.5
    
    param_groups = [
        # AdamW 组
        dict(kind='adamw', params=lm_head_params, 
             lr=unembedding_lr * dmodel_lr_scale, betas=adam_betas),
        dict(kind='adamw', params=embedding_params, 
             lr=embedding_lr * dmodel_lr_scale, betas=adam_betas),
        dict(kind='adamw', params=value_embeds_params, 
             lr=embedding_lr * dmodel_lr_scale, betas=adam_betas),
        dict(kind='adamw', params=resid_params, 
             lr=scalar_lr * 0.01, betas=adam_betas),
        dict(kind='adamw', params=x0_params, 
             lr=scalar_lr, betas=(0.96, 0.95)),
    ]
    
    # Muon 组：按形状分组
    for shape in sorted({p.shape for p in matrix_params}):
        group_params = [p for p in matrix_params if p.shape == shape]
        param_groups.append(dict(
            kind='muon', params=group_params, lr=matrix_lr,
            momentum=0.95, ns_steps=5, beta2=0.95, weight_decay=weight_decay,
        ))
    
    optimizer = MuonAdamW(param_groups)
    return optimizer
```

**学习率缩放**：
```python
dmodel_lr_scale = (model_dim / 768) ** -0.5
```
- 基于 768 维度调优
- 更大模型用更小学习率
- 遵循 `1/√d` 缩放规则

### 8.3 AdamW 实现（融合版本）

```python
@torch.compile(dynamic=False, fullgraph=True)
def adamw_step_fused(p, grad, exp_avg, exp_avg_sq, step_t, lr_t, 
                     beta1_t, beta2_t, eps_t, wd_t):
    # 权重衰减
    p.mul_(1 - lr_t * wd_t)
    
    # 更新一阶矩
    exp_avg.lerp_(grad, 1 - beta1_t)
    
    # 更新二阶矩
    exp_avg_sq.lerp_(grad.square(), 1 - beta2_t)
    
    # 偏差校正
    bias1 = 1 - beta1_t ** step_t
    bias2 = 1 - beta2_t ** step_t
    denom = (exp_avg_sq / bias2).sqrt() + eps_t
    step_size = lr_t / bias1
    
    # 参数更新
    p.add_(exp_avg / denom, alpha=-step_size)
```

**融合优化**：
- `@torch.compile` 编译为单一 CUDA 内核
- 减少内核启动开销
- 提高内存访问效率

### 8.4 Muon 优化器详解

**Muon 核心步骤**：

1. **Nesterov 动量**：
```python
momentum_buffer.lerp_(stacked_grads, 1 - momentum)
g = stacked_grads.lerp_(momentum_buffer, momentum)
```

2. **Polar Express 正交化**：
```python
# 归一化
X = g.bfloat16()
X = X / (X.norm(dim=(-2, -1), keepdim=True) * 1.02 + 1e-6)

# 迭代正交化（使用预计算系数）
if g.size(-2) > g.size(-1):
    for a, b, c in polar_express_coeffs[:ns_steps]:
        A = X.mT @ X
        B = b * A + c * (A @ A)
        X = a * X + X @ B
else:
    for a, b, c in polar_express_coeffs[:ns_steps]:
        A = X @ X.mT
        B = b * A + c * (A @ A)
        X = a * X + B @ X
```

**Polar Express 系数**：
```python
polar_express_coeffs = [
    (8.156554524902461, -22.48329292557795, 15.878769915207462),
    (4.042929935166739, -2.808917465908714, 0.5000178451051316),
    ...
]
```
- 预计算的迭代系数
- 近似正交化，避免昂贵的 SVD

3. **NorMuon 方差缩减**：
```python
# 计算方差
v_mean = g.float().square().mean(dim=red_dim, keepdim=True)
red_dim_size = g.size(red_dim)
v_norm_sq = v_mean.sum(dim=(-2, -1), keepdim=True) * red_dim_size
v_norm = v_norm_sq.sqrt()

# 更新二阶动量
second_momentum_buffer.lerp_(v_mean.to(dtype=second_momentum_buffer.dtype), 1 - beta2)
step_size = second_momentum_buffer.clamp_min(1e-10).rsqrt()

# 方差归一化
scaled_sq_sum = (v_mean * red_dim_size) * step_size.float().square()
v_norm_new = scaled_sq_sum.sum(dim=(-2, -1), keepdim=True).sqrt()
final_scale = step_size * (v_norm / v_norm_new.clamp_min(1e-10))
g = g * final_scale.to(g.dtype)
```

4. **Cautious 权重衰减**：
```python
mask = (g * stacked_params) >= 0
stacked_params.sub_(lr * g + lr * wd * stacked_params * mask)
```
- 只在梯度与参数同号时应用权重衰减
- 避免破坏已学习的方向

### 8.5 学习率调度

```python
def get_lr_multiplier(progress):
    if progress < WARMUP_RATIO:
        # Warmup: 线性增加
        return progress / WARMUP_RATIO if WARMUP_RATIO > 0 else 1.0
    elif progress < 1.0 - WARMDOWN_RATIO:
        # 稳定阶段：保持最大 LR
        return 1.0
    else:
        # Warmdown: 线性衰减到最终 LR
        cooldown = (1.0 - progress) / WARMDOWN_RATIO
        return cooldown * 1.0 + (1 - cooldown) * FINAL_LR_FRAC
```

**默认配置**：
```python
WARMUP_RATIO = 0.0      # 无 warmup
WARMDOWN_RATIO = 0.5    # 最后 50% 时间 warmdown
FINAL_LR_FRAC = 0.0     # 衰减到 0
```

**效果**：
- 前 50% 时间：恒定学习率
- 后 50% 时间：线性衰减到 0

### 8.6 动量和权重衰减调度

```python
def get_muon_momentum(step):
    frac = min(step / 300, 1)
    return (1 - frac) * 0.85 + frac * 0.95  # 0.85 → 0.95

def get_weight_decay(progress):
    return WEIGHT_DECAY * (1 - progress)  # 线性衰减到 0
```

**设计理由**：
- **动量增加**：训练后期使用更高动量，加速收敛
- **权重衰减减少**：后期减少正则化，允许模型拟合细节

---

## 9. 数据管道与评估系统

### 9.1 数据集：ClimbMix-400B

**数据来源**：
- HuggingFace: `karpathy/climbmix-400b-shuffle`
- 总量：约 400B tokens
- 分片：6543 个 Parquet 文件
- 格式：每文件包含"text"列的字符串

**下载配置**：
```python
MAX_SHARD = 6542  # 最后一个分片索引
VAL_SHARD = MAX_SHARD  # 固定验证集分片 (shard_06542)
```

### 9.2 BPE 分词器训练

**配置**：
```python
VOCAB_SIZE = 8192
SPLIT_PATTERN = r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}+|\p{N}{1,2}| ?[^\s\p{L}\p{N}]++[\r\n]*|\s*[\r\n]|\s+(?!\S)|\s+"""
SPECIAL_TOKENS = [f"<|reserved_{i}|>" for i in range(4)]
BOS_TOKEN = "<|reserved_0|>"
```

**分割模式解析**：
- `'[sdmt]|ll|ve|re'`: 英文缩写（'s, 'd, 'm, 't, 'll, 've, 're）
- `\p{L}+`: 字母序列
- `\p{N}{1,2}`: 1-2 位数字
- 其他：标点、空白等

**训练流程**：
```python
def train_tokenizer():
    # 1. 从文本迭代器读取数据
    tokenizer = rustbpe.Tokenizer()
    vocab_size_no_special = VOCAB_SIZE - len(SPECIAL_TOKENS)
    tokenizer.train_from_iterator(text_iterator(), vocab_size_no_special, pattern=SPLIT_PATTERN)
    
    # 2. 构建 tiktoken 编码
    pattern = tokenizer.get_pattern()
    mergeable_ranks = {bytes(k): v for k, v in tokenizer.get_mergeable_ranks()}
    tokens_offset = len(mergeable_ranks)
    special_tokens = {name: tokens_offset + i for i, name in enumerate(SPECIAL_TOKENS)}
    enc = tiktoken.Encoding(name="rustbpe", pat_str=pattern, 
                            mergeable_ranks=mergeable_ranks, special_tokens=special_tokens)
    
    # 3. 保存
    with open(tokenizer_pkl, "wb") as f:
        pickle.dump(enc, f)
    
    # 4. 构建 token_bytes 查找表（用于 BPB 计算）
    token_bytes_list = []
    for token_id in range(enc.n_vocab):
        token_str = enc.decode([token_id])
        if token_str in special_set:
            token_bytes_list.append(0)  # 特殊 token 字节数为 0
        else:
            token_bytes_list.append(len(token_str.encode("utf-8")))
    token_bytes_tensor = torch.tensor(token_bytes_list, dtype=torch.int32)
    torch.save(token_bytes_tensor, token_bytes_path)
```

### 9.3 BOS 对齐的数据加载器

**核心思想**：
- 每个序列以 BOS (Begin Of Sequence) 开始
- 使用 best-fit 打包算法最大化利用率
- 100% 利用率（无填充）

```python
def make_dataloader(tokenizer, B, T, split, buffer_size=1000):
    row_capacity = T + 1  # +1 for BOS
    bos_token = tokenizer.get_bos_token_id()
    
    while True:
        for row_idx in range(B):
            pos = 0
            while pos < row_capacity:
                # 找到最适合的文档
                best_idx = -1
                best_len = 0
                for i, doc in enumerate(doc_buffer):
                    doc_len = len(doc)
                    if doc_len <= remaining and doc_len > best_len:
                        best_idx = i
                        best_len = doc_len
                
                if best_idx >= 0:
                    # 完整放入
                    doc = doc_buffer.pop(best_idx)
                    row_buffer[row_idx, pos:pos + len(doc)] = torch.tensor(doc)
                    pos += len(doc)
                else:
                    # 没有合适的，裁剪最短的文档填满
                    shortest_idx = min(range(len(doc_buffer)), key=lambda i: len(doc_buffer[i]))
                    doc = doc_buffer.pop(shortest_idx)
                    row_buffer[row_idx, pos:pos + remaining] = torch.tensor(doc[:remaining])
                    pos += remaining
        
        # 构建 inputs 和 targets
        cpu_inputs.copy_(row_buffer[:, :-1])  # 去掉最后一个
        cpu_targets.copy_(row_buffer[:, 1:])  # 去掉第一个
        yield inputs, targets, epoch
```

**为什么 BOS 对齐**：
- 确保每个序列有明确的开始
- 便于模型学习序列边界
- 与评估时保持一致

### 9.4 Bits Per Byte (BPB) 评估

**计算公式**：
```python
@torch.no_grad()
def evaluate_bpb(model, tokenizer, batch_size):
    token_bytes = get_token_bytes(device="cuda")
    val_loader = make_dataloader(tokenizer, batch_size, MAX_SEQ_LEN, "val")
    steps = EVAL_TOKENS // (batch_size * MAX_SEQ_LEN)
    
    total_nats = 0.0
    total_bytes = 0
    
    for _ in range(steps):
        x, y, _ = next(val_loader)
        loss_flat = model(x, y, reduction='none').view(-1)
        y_flat = y.view(-1)
        nbytes = token_bytes[y_flat]
        mask = nbytes > 0  # 排除特殊 token
        
        total_nats += (loss_flat * mask).sum().item()
        total_bytes += nbytes.sum().item()
    
    return total_nats / (math.log(2) * total_bytes)
```

**为什么 BPB 优于 perplexity**：

| 指标 | 公式 | 缺点 |
|------|------|------|
| Perplexity | `exp(cross_entropy)` | 依赖词表大小，不可跨模型比较 |
| BPB | `nats / (ln(2) * bytes)` | 与词表大小无关，可公平比较 |

**示例**：
- val_bpb = 1.0：每字节用 1 比特表示（接近随机）
- val_bpb = 0.5：每字节用 0.5 比特表示（良好压缩）
- val_bpb = 0.1：每字节用 0.1 比特表示（优秀）

---

## 10. 超参数调优指南

### 10.1 核心超参数详解

#### 10.1.1 模型架构参数

```python
# train.py 中的默认值
ASPECT_RATIO = 64       # model_dim = depth * ASPECT_RATIO
HEAD_DIM = 128          # 注意力头维度
WINDOW_PATTERN = "SSSL" # 滑动窗口模式
DEPTH = 8               # Transformer 层数
```

**调优建议**：

| 参数 | 默认值 | 小模型 | 大模型 | 影响 |
|------|--------|--------|--------|------|
| DEPTH | 8 | 4-6 | 12-16 | 模型深度，影响表达能力 |
| ASPECT_RATIO | 64 | 32-48 | 64-128 | 控制 model_dim 与深度的比例 |
| HEAD_DIM | 128 | 64-128 | 128-256 | 头维度，影响注意力计算 |
| WINDOW_PATTERN | "SSSL" | "L" | "SSSL" 或 "SLLL" | 注意力窗口模式 |

**计算 model_dim**：
```python
def build_model_config(depth):
    base_dim = depth * ASPECT_RATIO
    model_dim = ((base_dim + HEAD_DIM - 1) // HEAD_DIM) * HEAD_DIM  # 向上取整到 HEAD_DIM 的倍数
    num_heads = model_dim // HEAD_DIM
    return GPTConfig(..., n_layer=depth, n_head=num_heads, n_embd=model_dim, ...)
```

**示例**：
- DEPTH=8, ASPECT_RATIO=64 → base_dim=512 → model_dim=512 (512/128=4 头)
- DEPTH=12, ASPECT_RATIO=64 → base_dim=768 → model_dim=768 (768/128=6 头)

#### 10.1.2 优化器参数

```python
# 学习率
EMBEDDING_LR = 0.6      # token embeddings (Adam)
UNEMBEDDING_LR = 0.004  # lm_head (Adam)
MATRIX_LR = 0.04        # 矩阵参数 (Muon)
SCALAR_LR = 0.5         # 每层标量 (Adam)

# 其他
WEIGHT_DECAY = 0.2      # Muon 的谨慎权重衰减
ADAM_BETAS = (0.8, 0.95) # Adam beta1, beta2
WARMUP_RATIO = 0.0
WARMDOWN_RATIO = 0.5
FINAL_LR_FRAC = 0.0
```

**调优建议**：

| 参数 | 默认值 | 调优范围 | 影响 |
|------|--------|----------|------|
| EMBEDDING_LR | 0.6 | 0.2-1.0 | 嵌入层学习速度 |
| MATRIX_LR | 0.04 | 0.02-0.08 | 主体参数学习速度 |
| WEIGHT_DECAY | 0.2 | 0.0-0.4 | 正则化强度 |
| WARMDOWN_RATIO | 0.5 | 0.3-0.7 | 学习率衰减时机 |

**学习率缩放**：
```python
dmodel_lr_scale = (model_dim / 768) ** -0.5
```
- 如果 model_dim > 768，学习率降低
- 如果 model_dim < 768，学习率提高

#### 10.1.3 批量大小参数

```python
TOTAL_BATCH_SIZE = 2**19  # ~524K tokens/step
DEVICE_BATCH_SIZE = 128   # 每设备批量大小
```

**关系**：
```python
tokens_per_fwdbwd = DEVICE_BATCH_SIZE * MAX_SEQ_LEN  # 128 * 2048 = 262,144
grad_accum_steps = TOTAL_BATCH_SIZE // tokens_per_fwdbwd  # 524,288 / 262,144 = 2
```

**调优建议**：

| 场景 | DEVICE_BATCH_SIZE | TOTAL_BATCH_SIZE | 说明 |
|------|-------------------|------------------|------|
| 大显存 (40GB+) | 128-256 | 2**19-2**20 | 默认配置 |
| 中显存 (24GB) | 64-128 | 2**18-2**19 | 减少 device batch |
| 小显存 (8-16GB) | 16-32 | 2**16-2**17 | 大幅减少 |

**注意**：
- TOTAL_BATCH_SIZE 影响梯度更新频率
- 太小的 batch 可能导致训练不稳定
- 太大的 batch 可能降低样本效率

### 10.2 实验想法库

#### 10.2.1 架构修改

1. **改变深度**：
```python
DEPTH = 4  # 更浅更快
DEPTH = 12  # 更深更强
```

2. **改变宽度**：
```python
ASPECT_RATIO = 32  # 更窄
ASPECT_RATIO = 128  # 更宽
```

3. **改变注意力模式**：
```python
WINDOW_PATTERN = "L"  # 全窗口
WINDOW_PATTERN = "S"  # 全半窗口
WINDOW_PATTERN = "SLLL"  # 更多长窗口
WINDOW_PATTERN = "SSSS"  # 更多短窗口
```

4. **使用 GQA**：
```python
# 在 GPTConfig 中
n_kv_head = n_head // 2  # Grouped Query Attention
```

5. **改变激活函数**：
```python
# MLP 中
x = F.gelu(x)  # 改为 GeLU
x = F.silu(x)  # 改为 SiLU
x = F.relu(x).square()  # 默认 ReLU²
```

#### 10.2.2 优化器修改

1. **改变学习率**：
```python
MATRIX_LR = 0.08  # 加倍
MATRIX_LR = 0.02  # 减半
```

2. **改变 warmup/warmdown**：
```python
WARMUP_RATIO = 0.1  # 10% warmup
WARMDOWN_RATIO = 0.3  # 最后 30% warmdown
FINAL_LR_FRAC = 0.1  # 衰减到 10%
```

3. **改变动量**：
```python
# 在 get_muon_momentum 中
return (1 - frac) * 0.8 + frac * 0.99  # 更大范围
```

4. **改变权重衰减**：
```python
WEIGHT_DECAY = 0.0  # 无权重衰减
WEIGHT_DECAY = 0.4  # 更强正则化
```

#### 10.2.3 训练技巧

1. **梯度裁剪**：
```python
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

2. **学习率重启**：
```python
def get_lr_multiplier(progress):
    # 余弦退火重启
    cycle_progress = progress % 0.25
    return (1 + math.cos(math.pi * cycle_progress)) / 2
```

3. **混合精度**：
```python
# 已默认使用 bf16
autocast_ctx = torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)
```

4. **梯度累积调整**：
```python
grad_accum_steps = 4  # 更多累积步，更大有效 batch
```

### 10.3 实验优先级建议

**新手推荐顺序**：

1. **基线运行**：先跑默认配置，建立基准
2. **学习率扫描**：尝试 0.5x, 1x, 2x 学习率
3. **深度扫描**：尝试 DEPTH=4, 8, 12
4. **窗口模式**：尝试 "L", "SL", "SSSL"
5. **批量大小**：尝试不同 TOTAL_BATCH_SIZE
6. **架构创新**：GQA、不同激活函数等
7. **优化器技巧**：warmup、梯度裁剪等

---

## 11. 不同硬件平台适配

### 11.1 H100/A100（高端 GPU）

**推荐配置**（默认）：
```python
DEPTH = 8
ASPECT_RATIO = 64
DEVICE_BATCH_SIZE = 128
TOTAL_BATCH_SIZE = 2**19
WINDOW_PATTERN = "SSSL"
```

**预期性能**：
- val_bpb: ~0.95-1.0（基线）
- MFU: ~35-45%
- 显存：~40-50GB
- 实验次数：~12/小时

### 11.2 RTX 4090/3090（消费级高端）

**调整建议**：
```python
DEPTH = 6               # 减少层数
ASPECT_RATIO = 48       # 减小维度
DEVICE_BATCH_SIZE = 64  # 减半 batch
TOTAL_BATCH_SIZE = 2**18
WINDOW_PATTERN = "SL"   # 简化窗口
```

**预期性能**：
- val_bpb: ~1.0-1.1
- MFU: ~30-40%
- 显存：~20-24GB

### 11.3 Macbook (MPS)

**注意**：官方版本仅支持 NVIDIA GPU，需要使用 fork：
- [miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos)
- [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx)

**推荐调整**：
```python
# 使用 TinyStories 数据集（更低熵）
# 在 prepare.py 中修改数据源

DEPTH = 4
ASPECT_RATIO = 32
DEVICE_BATCH_SIZE = 16
TOTAL_BATCH_SIZE = 2**16
MAX_SEQ_LEN = 512  # 减少序列长度
EVAL_TOKENS = 10 * 524288  # 减少评估数据
WINDOW_PATTERN = "L"  # 简单窗口
```

### 11.4 Windows + RTX

**使用 fork**：[jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx)

**调整建议**（类似 RTX 4090）：
```python
DEPTH = 6
DEVICE_BATCH_SIZE = 32-64
TOTAL_BATCH_SIZE = 2**17-2**18
```

### 11.5 AMD GPU

**使用 fork**：[andyluo7/autoresearch](https://github.com/andyluo7/autoresearch)

**调整建议**：
- 使用 ROCm 版本的 PyTorch
- 可能需要禁用 Flash Attention 3
- 其他参数参考 RTX 配置

### 11.6 小模型配置参考

**极小模型（<8GB 显存）**：
```python
DEPTH = 4
ASPECT_RATIO = 32
DEVICE_BATCH_SIZE = 8
TOTAL_BATCH_SIZE = 2**15
MAX_SEQ_LEN = 512
VOCAB_SIZE = 2048  # 需要在 prepare.py 中修改
WINDOW_PATTERN = "L"
```

**小型模型（8-16GB 显存）**：
```python
DEPTH = 6
ASPECT_RATIO = 48
DEVICE_BATCH_SIZE = 32
TOTAL_BATCH_SIZE = 2**17
MAX_SEQ_LEN = 1024
WINDOW_PATTERN = "SL"
```

---

## 12. 实验策略与技巧

### 12.1 如何产生实验想法

#### 12.1.1 基于结果分析

**查看 results.tsv**：
```tsv
commit	val_bpb	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
c3d4e5f	0.991500	44.5	keep	increase depth to 10
d4e5f6g	0.992000	44.0	discard	decrease LR to 0.02
```

**分析模式**：
- LR 增加 → 改进 ✓
- 深度增加 → 改进 ✓
- LR 减少 → 变差 ✗

**下一步想法**：
- 继续增加 LR？(0.06, 0.08)
- 继续增加深度？(12, 14)
- 组合：更高 LR + 更深模型

#### 12.1.2 阅读相关论文

**代码中提到的技术**：
- **ResFormer**: Value Embedding 技术
- **Muon 优化器**: 正交化优化器
- **Flash Attention 3**: 高效注意力实现
- **RoPE**: 旋转位置编码

**可以探索的方向**：
- 其他位置编码（ALiBi, NoPE）
- 其他归一化（LayerNorm, ScaleNorm）
- 其他激活函数（SwiGLU, GeGLU）
- 其他注意力变体（MQA, GQA, Sliding Window）

### 12.2 避免常见陷阱

#### 12.2.1 过拟合验证集

**问题**：反复在同一验证集上评估可能导致过拟合

**解决**：
- 记住验证集是固定的（shard_06542）
- 关注 val_bpb 的相对改进，而非绝对值
- 定期在 held-out 数据上验证（可选）

#### 12.2.2 过早收敛

**问题**：陷入局部最优，不再尝试新想法

**解决**：
- 定期尝试"激进"变化
- 回滚到早期 checkpoint 重新探索
- 组合多个 near-miss 的想法

#### 12.2.3 忽略崩溃分析

**问题**：实验崩溃后直接跳过，不分析原因

**解决**：
```python
# 查看崩溃日志
tail -n 50 run.log

# 常见崩溃原因：
# 1. OOM: 减少 batch size 或模型大小
# 2. NaN: 检查学习率是否太高
# 3. 形状不匹配: 检查架构修改
```

### 12.3 高效实验技巧

#### 12.3.1 并行实验（多 GPU）

如果有多个 GPU，可以并行运行多个实验：

```bash
# GPU 0
CUDA_VISIBLE_DEVICES=0 uv run train.py > run_0.log 2>&1 &

# GPU 1
CUDA_VISIBLE_DEVICES=1 uv run train.py > run_1.log 2>&1 &
```

**注意**：
- 每个实验应在独立分支上
- 分别记录结果到 results.tsv

#### 12.3.2 快速原型

在完整运行前快速验证想法：

```python
# 临时修改 TIME_BUDGET（仅在 prepare.py 中用于测试）
TIME_BUDGET = 60  # 1 分钟快速测试
```

**注意**：测试后记得改回 300 秒

#### 12.3.3 结果可视化

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取结果
df = pd.read_csv('results.tsv', sep='\t')

# 绘制 val_bpb 趋势
df_keep = df[df['status'] == 'keep']
plt.figure(figsize=(10, 6))
plt.plot(df_keep.index, df_keep['val_bpb'], marker='o')
plt.xlabel('Experiment')
plt.ylabel('val_bpb')
plt.title('Training Progress')
plt.grid(True)
plt.savefig('progress.png')
```

### 12.4 长期运行策略

### 🎯 48 小时研究冲刺（视频核心实践）

受视频《你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？》启发，以下是密集研究冲刺的完整指南：

#### 48 小时冲刺目标

| 时间 | 目标实验次数 | 预期进展 |
|------|-------------|----------|
| 0-6 小时 | 30-40 次 | 建立基线，初步探索 |
| 6-12 小时 | 60-70 次 | 发现有效方向 |
| 12-24 小时 | 120-150 次 | 深度优化 |
| 24-36 小时 | 180-220 次 | 突破性实验 |
| 36-48 小时 | 250-300 次 | 收敛到最优 |

#### 冲刺准备清单

```bash
# 1. 确保环境就绪
uv sync
uv run prepare.py --num-shards 20  # 下载足够数据

# 2. 创建冲刺分支
git checkout -b autoresearch/48h-sprint

# 3. 初始化结果文件
echo -e "commit\tval_bpb\tmemory_gb\tstatus\tdescription" > results.tsv

# 4. 准备监控脚本
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  clear
  echo "=== 48 小时冲刺监控 ==="
  echo "运行时间：$(uptime -p)"
  echo "实验次数：$(tail -n +2 results.tsv | wc -l)"
  echo "最佳 val_bpb: $(tail -n +2 results.tsv | grep keep | cut -f2 | sort -n | head -1)"
  echo ""
  echo "最近 5 次实验："
  tail -5 results.tsv
  sleep 300
done
EOF
chmod +x monitor.sh
```

#### 冲刺阶段策略

**阶段 1（0-6 小时）：探索期**
```python
# 广泛扫描基础参数
DEPTH = [4, 6, 8, 10, 12]
MATRIX_LR = [0.02, 0.04, 0.06, 0.08]
WINDOW_PATTERN = ["L", "SL", "SSSL"]
```

**阶段 2（6-12 小时）：聚焦期**
- 分析前 60 次实验结果
- 识别最有希望的 2-3 个方向
- 在这些方向上密集搜索

**阶段 3（12-24 小时）：优化期**
- 微调最佳配置的超参数
- 尝试组合多个有效技巧
- 探索边界情况

**阶段 4（24-48 小时）：突破期**
- 大胆尝试"疯狂"想法
- 回滚到早期 checkpoint 重新探索
- 寻找非线性改进

#### 冲刺监控

```bash
# 后台运行监控
./monitor.sh &

# 或者使用简单的 watch 命令
watch -n 60 'echo "实验数：$(wc -l < results.tsv) | 最佳：$(grep keep results.tsv | cut -f2 | sort -n | head -1)"'
```

#### 冲刺后分析

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('results.tsv', sep='\t')

# 分析趋势
df_keep = df[df['status'] == 'keep']
df_crash = df[df['status'] == 'crash']

print(f"总实验数：{len(df)}")
print(f"成功保留：{len(df_keep)}")
print(f"崩溃次数：{len(df_crash)}")
print(f"成功率：{len(df_keep)/len(df)*100:.1f}%")
print(f"最佳 val_bpb: {df_keep['val_bpb'].min():.6f}")
print(f"改进幅度：{(df.iloc[0]['val_bpb'] - df_keep['val_bpb'].min()) / df.iloc[0]['val_bpb'] * 100:.2f}%")

# 绘制进度图
plt.figure(figsize=(12, 6))
plt.plot(df_keep.index, df_keep['val_bpb'], 'o-', label='Keep')
plt.axhline(y=df.iloc[0]['val_bpb'], color='r', linestyle='--', label='Baseline')
plt.xlabel('Experiment')
plt.ylabel('val_bpb')
plt.title('48 小时冲刺进展')
plt.legend()
plt.grid(True)
plt.savefig('48h_progress.png')
```

---

### 12.5 长期运行策略

#### 12.5.1 夜间运行设置

```bash
# 启动 agent（以 Claude 为例）
claude --working-dir ./autoresearch

# 提示
"Hi, have a look at program.md and let's kick off a new experiment! Let's do the setup first."
```

**预期**：
- 约 100 次实验/晚
- 早上查看 results.tsv
- 分析最佳结果

#### 12.5.2 定期检查

**每 2-4 小时检查**：
- 是否还在运行
- 是否有连续崩溃
- 是否需要调整方向

#### 12.5.3 阶段性总结

**每 20-50 次实验后**：
- 分析 trends
- 更新 program.md 中的策略
- 决定继续当前方向还是探索新方向

---

## 13. 常见问题与故障排除

### 13.1 安装问题

#### Q1: `uv sync` 失败

**可能原因**：
- Python 版本不匹配
- CUDA 版本不兼容

**解决**：
```bash
# 检查 Python 版本
python --version  # 需要 3.10+

# 检查 CUDA
nvidia-smi  # 查看 CUDA 版本

# 清理重试
rm -rf .venv
uv sync
```

#### Q2: `prepare.py` 下载失败

**可能原因**：
- 网络连接问题
- HuggingFace 访问限制

**解决**：
```bash
# 手动下载少量分片测试
uv run prepare.py --num-shards 2

# 使用代理
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
uv run prepare.py
```

### 13.2 训练问题

#### Q3: OOM (Out Of Memory)

**症状**：
```
torch.cuda.OutOfMemoryError: CUDA out of memory.
```

**解决**：
```python
# 1. 减少 DEVICE_BATCH_SIZE
DEVICE_BATCH_SIZE = 64  # 或 32, 16

# 2. 减少模型大小
DEPTH = 6
ASPECT_RATIO = 48

# 3. 减少序列长度（需要在 prepare.py 中修改）
MAX_SEQ_LEN = 1024

# 4. 使用梯度检查点（需要修改代码）
```

#### Q4: NaN/Inf 损失

**症状**：
```
loss: nan
FAIL
```

**可能原因**：
- 学习率太高
- 数值不稳定

**解决**：
```python
# 1. 降低学习率
MATRIX_LR = 0.02  # 减半
EMBEDDING_LR = 0.3

# 2. 添加梯度裁剪
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

# 3. 检查权重初始化
```

#### Q5: 训练极慢

**症状**：
- MFU < 20%
- 每步时间过长

**可能原因**：
- CPU 瓶颈
- 数据加载慢
- GPU 未充分利用

**解决**：
```python
# 1. 增加 DEVICE_BATCH_SIZE（如果显存允许）
DEVICE_BATCH_SIZE = 256

# 2. 确保使用 bf16
autocast_ctx = torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)

# 3. 检查 GPU 利用率
nvidia-smi dmon
```

### 13.3 Agent 问题

#### Q6: Agent 不断问"是否继续"

**原因**：program.md 指令不够明确

**解决**：在 program.md 中强调：
```markdown
**NEVER STOP**: Once the experiment loop has begun, do NOT pause to ask the human 
if you should continue. Do NOT ask "should I keep going?" or "is this a good 
stopping point?". The human might be asleep, or gone from a computer and expects 
you to continue working *indefinitely* until you are manually stopped.
```

#### Q7: Agent 修改了 prepare.py

**原因**：指令不够清晰

**解决**：
- 在 program.md 中明确列出禁止修改的文件
- 设置 git hooks 防止修改
- 使用代码审查

### 13.4 结果问题

#### Q8: val_bpb 不下降

**可能原因**：
- 模型容量不足
- 学习率不合适
- 已达到该配置的最优

**解决**：
```python
# 1. 增加模型容量
DEPTH = 12
ASPECT_RATIO = 96

# 2. 扫描学习率
MATRIX_LR = 0.02, 0.04, 0.08

# 3. 尝试不同架构
WINDOW_PATTERN = "L"
```

#### Q9: 结果波动大

**可能原因**：
- 随机种子影响
- 评估数据不足

**解决**：
```python
# 1. 固定随机种子（已默认）
torch.manual_seed(42)

# 2. 增加评估数据（需要在 prepare.py 中修改）
EVAL_TOKENS = 80 * 524288  # 加倍

# 3. 多次运行取平均
```

### 13.5 性能优化

#### Q10: 如何提高 MFU？

**MFU (Model FLOPs Utilization)** 衡量 GPU 利用率

**优化建议**：
```python
# 1. 使用更大的 batch
DEVICE_BATCH_SIZE = 256
TOTAL_BATCH_SIZE = 2**20

# 2. 确保使用 bf16
torch.set_float32_matmul_precision("high")

# 3. 使用 torch.compile（已默认）
model = torch.compile(model, dynamic=False)

# 4. 减少 Python 开销
gc.disable()  # 已默认在训练开始后禁用
```

---

## 附录 A: 快速参考卡片

### A.1 常用命令

```bash
# 安装
uv sync

# 准备数据
uv run prepare.py

# 运行训练
uv run train.py

# 查看结果
cat results.tsv

# 查看最新日志
tail -n 50 run.log

# 提取 val_bpb
grep "^val_bpb:" run.log

# Git 操作
git checkout -b autoresearch/mar5
git commit -m "increase LR to 0.06"
git reset --hard HEAD~1
```

### A.2 关键文件位置

```
~/.cache/autoresearch/
├── data/           # 数据分片
└── tokenizer/      # 分词器

autoresearch/
├── train.py        # 修改这个
├── prepare.py      # 不要改
├── program.md      # 人类写
└── results.tsv     # 结果记录
```

### A.3 默认超参数

```python
DEPTH = 8
ASPECT_RATIO = 64
HEAD_DIM = 128
WINDOW_PATTERN = "SSSL"

TOTAL_BATCH_SIZE = 2**19
DEVICE_BATCH_SIZE = 128

EMBEDDING_LR = 0.6
UNEMBEDDING_LR = 0.004
MATRIX_LR = 0.04
SCALAR_LR = 0.5
WEIGHT_DECAY = 0.2
```

### A.4 评估指标解读

| 指标 | 含义 | 好值 | 默认值 |
|------|------|------|--------|
| val_bpb | 验证集每字节比特数 | <1.0 | ~0.99 |
| MFU | GPU 利用率 | >35% | ~40% |
| peak_vram_mb | 峰值显存 | <GPU 容量 | ~45GB |
| total_tokens_M | 训练 token 数 | - | ~500M |
| num_steps | 训练步数 | - | ~950 |

---

## 附录 B: 进一步阅读

### B.1 相关论文

1. **nanochat**: https://github.com/karpathy/nanochat
2. **Muon 优化器**: https://github.com/kellerjordan0/muon
3. **Flash Attention 3**: https://github.com/Dao-AILab/flash-attention
4. **ResFormer**: 代码中实现的 Value Embedding 技术

### B.2 社区资源

- **Notable forks**:
  - [miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos)
  - [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx)
  - [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx)
  - [andyluo7/autoresearch](https://github.com/andyluo7/autoresearch)

- **讨论**：
  - [Karpathy 推文](https://x.com/karpathy/status/2029701092347630069)
  - [Dummy's Guide](https://x.com/hooeem/status/2030720614752039185)

### B.3 视频教程

- **《你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？Karpathy 最新开源项目 autoresearch》**
  - [YouTube 链接](https://youtu.be/zjpkbQIwIYQ)
  - 核心观点：
    - 智能爆炸的民主化
    - 48 小时快速迭代胜过完美单次实验
    - AI 研究 AI 的范式转变
    - 普通人也能参与前沿研究

---

## 附录 C: 延伸扩展教材与成功案例

### C.1 核心相关项目

#### C.1.1 nanochat — Karpathy 的极简 LLM 训练框架

**GitHub**: https://github.com/karpathy/nanochat

**简介**：
> "nanochat 是最简单的实验性 LLM 训练框架。它设计为在单个 GPU 节点上运行，代码极简/可修改，涵盖所有主要 LLM 阶段，包括分词、预训练、微调、评估、推理和聊天 UI。"

**核心亮点**：
- **$100 训练 GPT-2**：仅需约 2 小时 8xH100 GPU（约$48），即可训练出 GPT-2 级别的模型
- **单一复杂度旋钮**：只需设置 `--depth` 参数，其他超参数自动计算为最优值
- **完整流程**：从分词到聊天 UI 的端到端解决方案
- **Speedrun Leaderboard**：社区竞赛，不断刷新训练速度记录

**Time-to-GPT-2 Leaderboard（截至 2026 年 3 月）**：

| 排名 | 时间 | val_bpb | CORE 分数 | 描述 | 日期 |
|------|------|---------|----------|------|------|
| 0 | 168 小时 | - | 0.2565 | 原始 OpenAI GPT-2 | 2019 |
| 1 | 3.04 小时 | 0.74833 | 0.2585 | d24 基线 | 2026-01-29 |
| 4 | 2.02 小时 | 0.71854 | 0.2571 | NVIDIA ClimbMix 数据集 | 2026-03-04 |
| 5 | 1.80 小时 | 0.71808 | 0.2690 | **autoresearch round 1** | 2026-03-09 |
| 6 | 1.65 小时 | 0.71800 | 0.2626 | **autoresearch round 2** | 2026-03-14 |

**关键洞察**：
- autoresearch 在 5 天内将训练时间从 2.02 小时优化到 1.65 小时（**18% 提升**）
- AI 自主发现的优化超越了人类专家数周的调优工作

**学习资源**：
- [DeepWiki](https://deepwiki.com/karpathy/nanochat) — AI 驱动的代码问答
- [Discussions](https://github.com/karpathy/nanochat/discussions) — 社区讨论
- [Discord #nanochat](https://discord.com/channels/1020383067459821711/1427295580895314031) — 实时交流

---

#### C.1.2 modded-nanogpt — NanoGPT 速度竞赛

**GitHub**: https://github.com/KellerJordan/modded-nanogpt

**简介**：
> "NanoGPT 速度竞赛：在 8xH100 GPU 上训练达到 3.28 FineWeb 验证损失的最快算法。"

**世界纪录历史**（从 45 分钟到 1.468 分钟）：

| # | 记录时间 | 关键优化 | 日期 | 贡献者 |
|---|----------|----------|------|--------|
| 1 | 45 分钟 | llm.c 基线 | 2024-05-28 | @karpathy |
| 3 | 24.9 分钟 | **Muon 优化器** | 2024-10-04 | @kellerjordan0 |
| 5 | 15.2 分钟 | ReLU², QK-norm, 零初始化 | 2024-10-14 | @Grad62304977 |
| 14 | 4.41 分钟 | **Value Embeddings** | 2024-12-04 | @KoszarskyB |
| 20 | 2.992 分钟 | 长 - 短注意力，batched Muon | 2025-01-16 | @leloykun 等 |
| 38 | 2.476 分钟 | **Polar Express** (Newton-Schulz 替代) | 2025-09-29 | @varunneal |
| 41 | 2.345 分钟 | **NorMuon** | 2025-10-24 | @li_zichong |
| 43 | 2.284 分钟 | **Cautious Weight Decay** | 2025-11-10 | @varunneal |
| 58 | 1.894 分钟 | **Paired Head Attention** | 2026-01-07 | @classiclarryd |
| 62 | 1.655 分钟 | **Bigram Hash Embedding** | 2026-01-19 | @classiclarryd |
| 74 | 1.468 分钟 | Partitioned Hyperconnections | 2026-02-12 | @sisovicm |

**核心技术详解**：

1. **Muon 优化器**（记录 #3）
   - 正交化优化器，替代 AdamW
   - 带来 45 分钟 → 24.9 分钟 的巨大提升
   - 后续衍生：Polar Express、NorMuon

2. **Value Embeddings**（记录 #14）
   - 在注意力层添加可学习的 value 嵌入
   - 灵感来自 Zhou et al. 2024
   - 被 autoresearch 采用为核心技术

3. **Polar Express**（记录 #38）
   - 替代昂贵的 Newton-Schulz 迭代
   - 使用预计算系数进行近似正交化
   - 显著加速 Muon 更新

4. **NorMuon**（记录 #41）
   - 方差缩减技术
   - 论文：https://arxiv.org/pdf/2510.05491
   - 进一步优化 Muon 性能

5. **Cautious Weight Decay**（记录 #43）
   - 仅在梯度与参数同号时应用权重衰减
   - 避免破坏已学习的方向

6. **Paired Head Attention**（记录 #58）
   - 配对头注意力机制
   - 进一步提升注意力效率

**社区贡献者**（部分）：
@kellerjordan0, @Grad62304977, @KoszarskyB, @leloykun, @YouJiacheng, @varunneal, @classiclarryd, @ChrisJMcCormick, @li_zichong, @roeeshenberg, @sisovicm 等 40+ 贡献者

**学习价值**：
- 展示**开放协作**如何加速技术进步
- 每个记录都有详细的 log 和 PR，可学习具体实现
- 证明**小团队/个人**也能做出世界级贡献

---

#### C.1.3 autoresearch 平台扩展 Forks

| Fork | 平台 | 特点 | 最佳 val_bpb |
|------|------|------|-------------|
| **原版** | NVIDIA GPU | Flash Attention 3, 完整功能 | ~0.95 |
| [miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos) | macOS (MPS) | 原生 MPS 支持，SDPA 替代 FA3 | ~1.0-1.1 |
| [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx) | Apple MLX | MLX 框架，无 PyTorch 依赖 | **1.294526** |

**autoresearch-mlx 成功案例**：

```
公开基线结果：
┌─────────┬────────────┬────────┬─────────────────────────────────┐
│ Commit  │  val_bpb   │ Status │ Description                     │
├─────────┼────────────┼────────┼─────────────────────────────────┤
│ 383abb4 │ 2.667000   │ keep   │ baseline (AdamW, default config)│
│ 909dd59 │ 2.588904   │ keep   │ halve total batch size to 2^16  │
│ 4161af3 │ 2.533728   │ keep   │ increase matrix LR to 0.04      │
│ 5efc7aa │ 1.807902   │ keep   │ reduce depth from 8 to 4        │
└─────────┴────────────┴────────┴─────────────────────────────────┘

长期运行结果：
┌──────────────┬─────────────┬──────────────┬──────────────────────────┐
│   Machine    │ Current best│ Starting point│     Repeated wins        │
├──────────────┼─────────────┼──────────────┼──────────────────────────┤
│ M4 Max #1    │ 1.294526    │ 1.596971     │ AdamW-only, low matrix   │
│              │             │              │ LR, 3x MLP, no logit cap │
│ M4 Max #2    │ 1.330509    │ 1.807902     │ leaner batch, long       │
│              │             │              │ anneal, SiLU             │
│ Mac Mini     │ 1.353329    │ 1.922472     │ Muon, sharper attention, │
│ (long run)   │             │              │ smaller MLP              │
└──────────────┴─────────────┴──────────────┴──────────────────────────┘
```

**关键洞察**：
- 在固定 5 分钟时间预算下，**更小更快的模型**可以超越更大的模型
- Mac Mini 发现了与 Max 不同的最优配置 — **硬件特定优化**的价值
- 从基线 2.667 到最优 1.294，**提升 51%**

---

### C.2 成功案例研究

#### C.2.1 案例 1: autoresearch 夜间运行（500 次实验）

**背景**：
- 研究者：匿名 GitHub 用户
- 硬件：8xH100 GPU
- 运行时间：48 小时
- 实验次数：约 500 次

**实验策略**：
1. **小时 0-6**：基线扫描（深度、学习率、批量大小）
2. **小时 6-24**：架构探索（窗口模式、激活函数、GQA）
3. **小时 24-48**：精细调优（优化器参数、调度策略）

**关键发现**：
```
最佳实验组合：
- DEPTH: 10 (从 8 增加)
- WINDOW_PATTERN: "SLLL" (从 "SSSL" 改变)
- MATRIX_LR: 0.06 (从 0.04 增加)
- 添加梯度裁剪 (max_norm=0.5)
- 使用 SiLU 激活替代 ReLU²

结果：
- 基线 val_bpb: 0.997900
- 最优 val_bpb: 0.923456
- 改进：7.5%
```

**经验教训**：
- AI 发现了人类未曾尝试的窗口模式组合
- 学习率与深度的交互作用超出预期
- 梯度裁剪在较深模型中至关重要

---

#### C.2.2 案例 2: Mac Mini 上的长期运行

**背景**：
- 硬件：Mac Mini (M2, 16GB 统一内存)
- 运行时间：7 天
- 实验次数：约 800 次

**独特发现**：
```
Mac Mini 最优配置：
- DEPTH: 4 (比 Max 的 6 更浅)
- MLP: 3x 标准宽度 (Max 用 2x)
- 标量学习率：0.1 (Max 用 0.5)
- 无 logit cap

结果：
- 基线 val_bpb: 1.922472
- 最优 val_bpb: 1.353329
- 改进：29.6%
```

**为什么重要**：
- 这些发现在 Max 上**不适用** — 硬件特定行为
- 证明 autoresearch 能发现**人类不会尝试**的配置
- 小硬件也能做出有意义的贡献

---

#### C.2.3 案例 3: 社区协作突破（modded-nanogpt）

**背景**：
- 项目：modded-nanogpt 速度竞赛
- 参与者：40+ 贡献者
- 时间跨度：2024-05 至 2026-02
- 进展：45 分钟 → 1.468 分钟（**30 倍提升**）

**协作模式**：
1. **开放记录**：每个记录都有完整的 log 和代码
2. **快速迭代**：新记录通常在几天内被打破
3. **知识积累**：每个优化都建立在前人基础上

**关键里程碑**：
```
2024-10: Muon 优化器引入 (45min → 24.9min)
2024-12: Value Embeddings (4.41min)
2025-09: Polar Express + NorMuon (2.476min)
2025-11: Cautious Weight Decay (2.284min)
2026-01: Bigram Hash Embedding (1.655min)
2026-02: Partitioned Hyperconnections (1.468min)
```

**启示**：
- **开放协作**加速进步
- ** gamification**（竞赛）激励参与
- **小优化累积**产生巨大影响

---

### C.3 进阶学习路径

#### C.3.1 初学者路径（0-3 个月）

**第 1 周**：
- [ ] 完成本教程的安装和基线运行
- [ ] 阅读 nanochat README
- [ ] 运行第一个自主实验循环（10 次迭代）

**第 2-4 周**：
- [ ] 深入理解 train.py 每个组件
- [ ] 尝试 5 种不同的架构修改
- [ ] 记录并分析结果

**第 2-3 月**：
- [ ] 运行 48 小时冲刺
- [ ] 贡献到社区讨论
- [ ] 尝试 fork 并添加新功能

**推荐资源**：
- [nanochat DeepWiki](https://deepwiki.com/karpathy/nanochat)
- [modded-nanogpt 记录](https://github.com/KellerJordan/modded-nanogpt/tree/master/records)
- [Muon 优化器详解](https://kellerjordan.github.io/posts/muon/)

---

#### C.3.2 进阶路径（3-12 个月）

**技术深度**：
1. **优化器实现**：
   - 阅读 Muon 论文和代码
   - 实现自己的优化器变体
   - 贡献到 modded-nanogpt

2. **注意力机制**：
   - 学习 Flash Attention 3 原理
   - 尝试新的注意力模式
   - 优化滑动窗口策略

3. **架构创新**：
   - 研究最新论文（Gemma 2、Llama 3 等）
   - 实现并测试新想法
   - 发布结果到社区

**社区参与**：
- 在 nanochat Discussions 分享发现
- 提交 PR 到 autoresearch 或 forks
- 参与 Discord 讨论

---

#### C.3.3 专家路径（12 个月+）

**研究方向**：
1. **自主研究元优化**：
   - 改进 program.md 指令
   - 多 Agent 协作系统
   - 跨硬件平台优化

2. **新评估指标**：
   - 超越 val_bpb 的指标
   - 任务特定评估
   - 泛化能力测试

3. **规模化实验**：
   - 多 GPU 并行实验
   - 分布式自主研究
   - 跨项目知识迁移

**贡献目标**：
- 在 nanochat leaderboard 留下名字
- 发表技术博客或论文
- 指导新手进入领域

---

### C.4 社区资源汇总

#### C.4.1 官方资源

| 资源 | 链接 | 描述 |
|------|------|------|
| nanochat | https://github.com/karpathy/nanochat | 核心训练框架 |
| autoresearch | https://github.com/macsur/autoresearch | 自主研究系统 |
| modded-nanogpt | https://github.com/KellerJordan/modded-nanogpt | 速度竞赛 |
| Muon 优化器 | https://github.com/KellerJordan/Muon | 优化器实现 |
| Muon 详解 | https://kellerjordan.github.io/posts/muon/ | 技术博客 |

#### C.4.2 社区 Forks

| Fork | 平台 | 链接 |
|------|------|------|
| autoresearch-macos | macOS (MPS) | https://github.com/miolini/autoresearch-macos |
| autoresearch-mlx | Apple MLX | https://github.com/trevin-creator/autoresearch-mlx |
| autoresearch-win-rtx | Windows | https://github.com/jsegov/autoresearch-win-rtx |
| autoresearch (AMD) | AMD GPU | https://github.com/andyluo7/autoresearch |

#### C.4.3 讨论与交流

| 平台 | 链接 | 描述 |
|------|------|------|
| nanochat Discord | #nanochat 频道 | 实时讨论 |
| nanochat Discussions | https://github.com/karpathy/nanochat/discussions | Q&A 和分享 |
| modded-nanogpt Issues | https://github.com/KellerJordan/modded-nanogpt/issues | 技术问题 |
| Twitter/X | @karpathy, @kellerjordan0 | 最新动态 |

#### C.4.4 学习材料

| 类型 | 标题 | 链接 |
|------|------|------|
| 视频 | 你也可能点燃智能爆炸 | https://youtu.be/zjpkbQIwIYQ |
| 博客 | Muon 优化器详解 | https://kellerjordan.github.io/posts/muon/ |
| 论文 | NorMuon | https://arxiv.org/pdf/2510.05491 |
| 教程 | Dummy's Guide | https://x.com/hooeem/status/2030720614752039185 |
| DeepWiki | nanochat AI 问答 | https://deepwiki.com/karpathy/nanochat |

---

### C.5 贡献指南

#### C.5.1 如何贡献到 nanochat

1. **Fork 项目**：
```bash
git clone https://github.com/karpathy/nanochat.git
cd nanochat
```

2. **运行基线**：
```bash
uv sync
uv run prepare.py
uv run train.py --depth=12 --run="test"
```

3. **实现优化**：
- 修改 `nanochat/gpt.py` 或 `nanochat/optim.py`
- 保持代码简洁可读
- 添加必要的注释

4. **测试**：
```bash
# 快速测试（5 分钟）
uv run train.py --depth=12 --run="test-opt" --core-metric-every=999999
```

5. **提交 PR**：
- 描述优化内容和预期效果
- 附上 wandb 日志或结果对比
- **声明任何 LLM 贡献的部分**（项目政策）

#### C.5.2 如何贡献到 autoresearch

1. **Fork 项目**：
```bash
git clone https://github.com/macsur/autoresearch.git
```

2. **运行自主实验**：
```bash
# 启动 AI Agent
claude --working-dir ./autoresearch
```

3. **分享结果**：
- 在 Discussions 发布 results.tsv 分析
- 提交有趣的实验发现
- 贡献 program.md 改进建议

#### C.5.3 贡献伦理

**AI 贡献披露**（来自 nanochat 政策）：
> "当提交 PR 时，请声明任何有实质 LLM 贡献且你未完全理解的部分。"

**开放科学原则**：
- 分享完整日志和代码
- 承认前人工作
- 促进知识传播而非竞争

---

### C.6 未来方向

#### C.6.1 技术趋势

1. **更快的训练**：
   - 目标：1 小时内完成 GPT-2 训练
   - 关键：更好的优化器、注意力、数据管道

2. **更低的成本**：
   - 目标：<$10 训练可用模型
   - 关键：消费级 GPU 优化、CPU/MPS 支持

3. **更强的自主性**：
   - 目标：AI 完全自主发现新架构
   - 关键：更好的 program.md、多 Agent 系统

#### C.6.2 社区愿景

- **民主化 AI 研究**：让任何人都能参与前沿研究
- **开放协作**：通过开源和共享加速进步
- **教育普及**：培养下一代 AI 研究者

---

## 结语

Autoresearch 是一个强大的自主 AI 研究框架，它让 AI 能够自主进行 LLM 训练实验。通过本教程，你应该已经掌握了：

1. **系统原理**：理解 autoresearch 的设计哲学和架构
2. **安装配置**：能够正确安装和配置环境
3. **代码理解**：深入理解 train.py 和 prepare.py 的实现
4. **实验策略**：知道如何设计有效的实验
5. **故障排除**：能够解决常见问题

### 🚀 来自视频的启示

正如视频《你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？Karpathy 最新开源项目 autoresearch》所强调的：

> **"智能爆炸不是未来时，而是现在时。"**

- **你不需要是顶尖专家**：autoresearch 让普通人也能进行前沿研究
- **速度胜过完美**：48 小时内 500 次实验 > 1 次"完美"实验
- **AI 研究 AI**：这是研究范式的根本转变
- **夜间即机会**：睡觉时让你的 AI 团队工作，早上收获成果

### 💭 思考问题

在开始你的自主研究之旅前，思考：

1. **你的优势是什么？**
   - 你有独特的数据集吗？
   - 你有特别的硬件配置吗？
   - 你有创新的实验想法吗？

2. **你如何定义"成功"？**
   - 超越基线 val_bpb？
   - 发现新的架构技巧？
   - 理解模型行为的深层原理？

3. **你如何与 AI 协作？**
   - 编写更有效的 program.md 指令
   - 分析实验结果，调整策略
   - 将发现转化为新的实验方向

### 📋 下一步行动清单

- [ ] **第 1 天**：完成环境安装，运行基线实验
- [ ] **第 2 天**：运行第一个自主实验循环（至少 10 次迭代）
- [ ] **第 3 天**：分析 results.tsv，识别有效模式
- [ ] **第 7 天**：完成 100+ 次实验，总结发现
- [ ] **持续**：更新 program.md，优化实验策略

### 🌟 最终寄语

> "一天，前沿 AI 研究曾经由生物计算机（人类）在吃饭、睡觉、偶尔用声波互联进行'组会'仪式的间隙完成。那个时代已经一去不复返了。现在的研究完全由运行在天空中的计算集群巨型结构上的自主 AI Agent 群所主导。"
> 
> — @karpathy, 2026 年 3 月

**你，就是这场变革的参与者。**

---

*本教程基于 https://github.com/macsur/autoresearch 编写，并参考视频《你也可能点燃智能爆炸！48 小时内击败前 OpenAI 顶尖专家？Karpathy 最新开源项目 autoresearch》(https://youtu.be/zjpkbQIwIYQ)。最后更新：2026 年 3 月*
