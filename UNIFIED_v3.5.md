# AutoResearch v3.5 — 统一功能主体

## 🎯 核心架构

```
UnifiedResearchEngine (v3.5 核心)
    ├─ Karpathy 闭环优化
    ├─ 贝叶斯优化
    └─ 自主探索引擎
```

## 📊 三大模式

### 1. Karpathy 模式
```bash
python autorun_evolve_v3.5.py "topic" --mode karpathy -r 5
```

**特点**:
- 启发式闭环
- 前期探索，后期利用
- 快速高效

**结果**:
```
R1: quick  → 25 findings
R2: deep   → 38 findings (最优)
R3: deep   → 38 findings (停止)
```

### 2. Bayesian 模式
```bash
python autorun_evolve_v3.5.py "topic" --mode bayesian -r 4
```

**特点**:
- 自适应参数优化
- 高斯过程学习
- 全局最优搜索

**结果**:
```
R1: 2源 std   → 26 findings (最优)
R2: 2源 quick → 18 findings
R3: 2源 std   → 23 findings (停止)
```

### 3. Exploration 模式
```bash
python autorun_evolve_v3.5.py "topic" --mode exploration --explore-depth 2
```

**特点**:
- 自主话题生成
- 迭代深化研究
- 持续学习

**结果**:
```
迭代 1: "Exploration Core"
  R1: quick → 24 findings
  R2: deep  → 39 findings (最优)

迭代 2: "Exploration Core result"
  R1: quick → 27 findings
  R2: deep  → 42 findings (最优)
```

## 🏗️ 统一设计

### 单一核心引擎
```python
class UnifiedResearchEngine:
    def suggest_config(self, round_num, total_rounds):
        # 根据模式返回配置
        if self.mode == KARPATHY:
            return self._suggest_karpathy(...)
        elif self.mode == BAYESIAN:
            return self._suggest_bayesian()
        else:
            return self._suggest_karpathy(...)
    
    def observe(self, result):
        # 统一观测记录
        self.history.append(result)
        if self.mode == BAYESIAN:
            self.optimizer.observe(params, value)
```

### 数据结构
```python
@dataclass
class ResearchConfig:
    sources: list
    depth: Depth

@dataclass
class ResearchResult:
    round_num: int
    config: ResearchConfig
    total_findings: int
    diversity_score: float
    value: float
    findings: list
```

## 📈 性能对比

| 指标 | Karpathy | Bayesian | Exploration |
|------|----------|----------|-------------|
| **最优结果** | 38 findings | 26 findings | 42 findings |
| **轮数** | 3 | 3 | 4 |
| **自适应** | 规则驱动 | 学习驱动 | 主题驱动 |
| **停止条件** | 2轮无提升 | 2轮无提升 | 无新主题 |

## 🔧 核心模块

### 1. GaussianProcess
- RBF 核函数
- 加权预测
- 方差估计

### 2. BayesianOptimizer
- 参数编码/解码
- 获取函数 (EI)
- 历史管理

### 3. ExplorationEngine
- 话题提取
- 候选生成
- 访问追踪

### 4. UnifiedResearchEngine
- 配置建议
- 观测记录
- 停止判断

## 📁 文件结构

```
autoresearch/
├── autorun_evolve.py          # v3.2 原始版本
├── autorun_evolve_v3.3.py     # v3.3 贝叶斯优化
├── autorun_evolve_v3.4.py     # v3.4 融合版本
├── autorun_evolve_v3.5.py     # v3.5 统一核心 ⭐
├── CAPABILITIES.md            # 完整能力清单
├── BAYESIAN_OPTIMIZATION.md   # 贝叶斯文档
├── UNIFIED_v3.4.md            # v3.4 文档
└── _cache/                    # 缓存目录
```

## ✨ v3.5 优势

1. **单一核心**: 三种模式共享同一引擎
2. **无缝切换**: `--mode` 参数灵活选择
3. **类型安全**: 使用 Enum 和 dataclass
4. **易于扩展**: 新模式只需添加 suggest 方法
5. **完整融合**: 所有能力集于一身

## 🚀 使用示例

```bash
# Karpathy 模式（默认）
python autorun_evolve_v3.5.py "AI agents" -r 5

# 贝叶斯优化
python autorun_evolve_v3.5.py "LLM optimization" --mode bayesian -r 4

# 自主探索
python autorun_evolve_v3.5.py "Research topic" --mode exploration --explore-depth 3
```

---

**AutoResearch v3.5 是三大模式的完美融合，单一统一的功能主体。**
