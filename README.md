# AutoResearch AI 自动化研究系统

AutoResearch 是一个自动化的 AI/LLM 研究工具，每天自动收集 GitHub 热门项目和最新论文，支持多维度质量评分、趋势分析和报告生成。

## 功能特性

### 核心功能

- **GitHub 项目监控**: 自动收集热门 AI/LLM 项目
- **质量评分系统**: 16 维度综合评分 (v4.7)
- **趋势分析**: 追踪热门主题和技术方向
- **报告生成**: 自动生成研究报告

### 评分维度

| 类别 | 维度 | 说明 |
|------|------|------|
| 基础 (7) | Authority, Academic, Star, Diversity, Usability, Applicability, Coverage | 来源权威性和数据质量 |
| BEIR (3) | NDCG, MAP, MRR | 检索排序质量 |
| NLG (3) | ROUGE-1, SemSim, Coherence | 语义质量 |
| Agent (5) | Task, Tool, Reasoning, Autonomy, Multi-Agent | Agent 能力评估 |

## 快速开始

### 1. 安装依赖

```bash
pip install aiohttp tqdm requests
```

### 2. 运行研究

```bash
# 单主题研究
python autorun_evolve_v4.7.py --topic "AI agents"

# 批量研究
python autorun_evolve_v4.7.py --auto

# 重新评分
python autorun_evolve_v4.7.py --regrade
```

### 3. 查看结果

```bash
# 查看研究报告
ls reports/

# 查看研究数据
ls findings/

# 查看趋势分析
python autorun_evolve_v4.7.py --trends
```

## 版本历史

### v4.8 - 跨机器自动运行

- 跨平台路径处理
- 配置文件系统 (`config/config.json`)
- 日志记录系统
- 错误重试机制
- GitHub 自动同步

### v4.7 - Agent 任务完成率评测

- Task Completion Rate: 任务完成率评估
- Tool Use Score: 工具调用有效性
- Multi-step Reasoning: 多步推理深度
- Autonomy Level: 自主性等级

### v4.6 - NLG 摘要评测

- ROUGE-1/2/L: n-gram 重叠
- Semantic Similarity: 语义相似度
- Coherence Score: 连贯性评分

### v4.5 - BEIR 检索指标

- NDCG@10: 排序质量
- MAP: 平均精度
- MRR: 倒数排名

### v4.4 - 7 维度基础评分

- Authority: 来源权威性
- Academic: 学术关键词
- Star Power: GitHub star 归一化
- Diversity: 来源多样性
- Usability: 文档/教程
- Applicability: 与系统相关性
- Coverage: 结果数量

## 项目结构

```
autoresearch/
├── autorun_evolve_v4.7.py      # 主程序
├── autorun_evolve_v4.8.py       # 跨机器版本
├── autorun_token_opt_v2.py     # Token 优化版 v2.0
├── autorun_quality_opt.py      # 质量优先版 v2.1
├── config/
│   ├── config.json              # 配置文件
│   └── topics.txt                # 主题列表
├── findings/                    # 研究数据
│   └── *.json                   # 每次研究的结果
├── reports/                     # 研究报告
│   └── *.md                     # Markdown 报告
├── trends/
│   └── history.json             # 趋势历史
└── README.md                    # 本文档
```

## 配置说明

### 配置文件

```json
{
  "github_token": "your_token_here",
  "batch_size": 10,
  "report_threshold": "B",
  "cache_hours": 24,
  "sync_github": true
}
```

### 主题列表

编辑 `config/topics.txt` 添加研究主题：

```
AI agents
LLM optimization
RAG retrieval
model quantization
fine-tuning LLMs
```

## 使用示例

### 1. 初始化

```bash
python autorun_v4.8_portable.py --init
```

### 2. 添加研究主题

```bash
# 编辑主题列表
echo "AI benchmark" >> config/topics.txt
```

### 3. 自动运行

```bash
# 自动运行所有主题
python autorun_v4.8_portable.py --auto

# 设置每日定时任务
python autorun_v4.8_portable.py --setup
```

### 4. 同步到 GitHub

```bash
# 同步数据和报告
python autorun_v4.8_portable.py --sync
```

## Token 优化版 v2.0

### 优化效果

| 指标 | 之前 | 之后 | 节省 |
|------|------|------|------|
| Token/主题 | ~500 | ~100 | 80% |
| 报告生成 | 每个主题 | 只 B+ | 50% |
| API 调用 | 每次新请求 | 24h 缓存 | 80% |
| **总计** | ~5000 | ~1500 | **70%** |

### 功能特性

- 批量处理：减少系统提示词重复
- 缓存强化：24小时有效
- 精简提示词：压缩到 ~100 tokens
- 选择性报告：只对 B+ 等级生成详细报告
- GitHub 同步：跨机器自动同步

### 使用方法

```bash
# 自动运行
python autorun_token_opt_v2.py --auto

# 研究指定主题
python autorun_token_opt_v2.py "AI agents" "LLM optimization"

# 同步 GitHub
python autorun_token_opt_v2.py --sync
```

## 质量优先版 v2.1

### 质量 vs Token 对比

| 指标 | Token 优先 v2.0 | 质量优先 v2.1 | 提升 |
|------|-----------------|---------------|------|
| A级主题 | 2 | 2 | - |
| B级主题 | 1 | 7 | **+600%** |
| C级主题 | 8 | 1 | - |
| F级主题 | 4 | 0 | **消除** |
| **平均评分** | 0.390 | **0.683** | **+75%** |
| 报告数 | 3 | **10** | **+233%** |

### 5维度质量评分

| 维度 | 说明 | 权重 |
|------|------|------|
| Authority | 来源权威性 | 25% |
| Academic | 学术价值 | 25% |
| Star | 流行度 | 20% |
| Freshness | 时效性 | 15% |
| Diversity | 多样性 | 15% |

### 功能特性

- 质量优先：更严格的评分标准
- 更多项目：每主题获取 30 个（vs 20）
- 短缓存：12小时（保证新鲜度）
- 全报告：C+ 等级都生成报告
- 时效性权重：30天内项目权重更高

### 使用方法

```bash
# 运行质量优先版
python autorun_quality_opt.py

# 研究指定主题
python autorun_quality_opt.py "AI agents" "LLM optimization"
```

## 研究成果

### 热门主题 (Top 10)

| 主题 | 评分 | 等级 |
|------|------|------|
| NLP evaluation benchmark tutorial | 0.833 | A |
| LLM benchmark evaluation guide | 0.789 | A |
| MMLU benchmark evaluation | 0.620 | B |
| RAG evaluation benchmark | 0.611 | B |
| NLP benchmark evaluation | 0.608 | B |
| AI agent file system | 0.589 | B |
| LLM evaluation benchmark | 0.575 | B |
| AI agent benchmark | 0.552 | B |
| knowledge retrieval benchmark | 0.580 | B |
| text mining analysis tool | 0.556 | B |

### 统计数据

- 研究主题: 300+
- 研究数据: 300+ JSON 文件
- 研究报告: 100+ Markdown 报告
- 平均评分: ~0.45

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- GitHub: [WATE88/auto-research-qclaw](https://github.com/WATE88/auto-research-qclaw)

---

**Star ⭐ 支持一下！**
