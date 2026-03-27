# AutoResearch v3.3 贝叶斯优化升级

## 🎯 核心改进

### 从启发式到贝叶斯优化

| 版本 | 策略 | 优势 |
|------|------|------|
| **v3.2** | 启发式规则 | 快速、可解释 |
| **v3.3** | 贝叶斯优化 | 自适应、全局最优 |

### 贝叶斯优化架构

```
高斯过程 (Gaussian Process)
    ↓
学习历史观测的分布
    ↓
获取函数 (Acquisition Function)
    ├─ EI (Expected Improvement)
    └─ UCB (Upper Confidence Bound)
    ↓
建议下一个参数组合
    ↓
观测结果 → 更新高斯过程
```

## 📊 参数空间

```python
param_space = {
    'num_sources': (2, 4, 'int'),      # 源数量：2-4
    'depth_level': (0, 2, 'int'),      # 深度：0=quick, 1=standard, 2=deep
}
```

## 🔬 测试结果

```
主题: Bayesian optimization LLM
轮数: 4

R1: sources=4, depth=deep    → 40条信息 (目标值=45.16)
R2: sources=3, depth=standard → 28条信息 (目标值=35.42)
R3: sources=3, depth=deep    → 34条信息 (目标值=40.25)
R4: sources=4, depth=deep    → 41条信息 (目标值=47.35) ← 最优

最优配置: num_sources=4, depth_level=2 (deep)
最优信息量: 41 条
```

## 🧠 高斯过程核心

### RBF 核函数
```
K(x1, x2) = exp(-||x1 - x2||^2 / 2)
```

### 预测
```
μ(x) = 加权平均(历史观测)
σ(x) = 1 / (1 + 总权重)
```

### 获取函数

**Expected Improvement (EI)**:
```
EI = (μ - best) * Φ(z) + σ * φ(z)
其中 z = (μ - best) / σ
```

**Upper Confidence Bound (UCB)**:
```
UCB = μ + β * σ
```

## 📈 优势

1. **自适应学习**: 根据历史结果自动调整参数
2. **全局搜索**: 平衡探索与利用
3. **样本高效**: 少量轮次找到最优配置
4. **理论保证**: 基于概率论的数学基础

## 🚀 使用方式

```bash
python autorun_evolve_v3.3.py "你的主题" -r 4
```

## 📁 文件

- `autorun_evolve_v3.3.py`: 贝叶斯优化版本
- `autorun_evolve.py`: 原始启发式版本（v3.2）

## 🔄 下一步

1. 集成到主 `autorun_evolve.py`
2. 支持更多参数空间
3. 添加多目标优化（Pareto 前沿）
4. 实现并行评估

---

**AutoResearch v3.3 已升级到贝叶斯优化，具备自适应参数优化能力。**
