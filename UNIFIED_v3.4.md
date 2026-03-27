# AutoResearch v3.4 统一版本

## 🎯 三大模式融合

### 模式对比

| 模式 | 策略 | 优势 | 用途 |
|------|------|------|------|
| **Karpathy** | 启发式闭环 | 快速、可解释 | 标准研究 |
| **Bayesian** | 贝叶斯优化 | 自适应、全局最优 | 参数优化 |
| **Exploration** | 自主探索 | 发现新主题、持续学习 | 深度研究 |

## 🚀 使用方式

### 1. Karpathy 闭环模式（默认）
```bash
python autorun_evolve_v3.4.py "AI agents" -r 5
```

**特点**:
- 前 50% 轮次：探索新源
- 后 50% 轮次：利用最优源
- 智能深度调节（多样性驱动）
- 连续 2 轮无提升自动停止

**结果**:
```
R1: quick   → 23 findings
R2: deep    → 41 findings (最优)
R3: deep    → 40 findings (停止)
```

### 2. 贝叶斯优化模式
```bash
python autorun_evolve_v3.4.py "LLM optimization" -r 4 --bayesian
```

**特点**:
- 高斯过程学习参数-性能分布
- EI/UCB 获取函数平衡探索与利用
- 自动调整源数量和深度
- 预热阶段随机采样，优化阶段贝叶斯建议

**结果**:
```
R1: 3源 quick   → 23 findings (预热)
R2: 4源 quick   → 28 findings (预热)
R3: 4源 standard → 34 findings (优化)
R4: 4源 standard → 37 findings (最优)
```

### 3. 自主探索模式
```bash
python autorun_evolve_v3.4.py "Exploration Mode" --explore --explore-depth 2
```

**特点**:
- 自动从搜索结果提取新兴话题
- 迭代研究相关主题
- 避免重复主题
- 持续深化理解

**结果**:
```
迭代 1: "Exploration Mode"
  R1: quick → 23 findings
  R2: deep  → 42 findings (最优)
  
迭代 2: "Exploration Mode result"
  R1: quick → 23 findings
  R2: deep  → 42 findings (最优)
  
完成: 4 轮研究
```

## 🧠 核心算法

### Karpathy 闭环
```
初始 → 探索 → 利用 → 最优
```

### 贝叶斯优化
```
高斯过程 → 获取函数 → 建议参数 → 观测 → 更新
```

### 自主探索
```
研究 → 提取话题 → 新主题 → 研究 → ...
```

## 📊 性能对比

| 指标 | Karpathy | Bayesian | Exploration |
|------|----------|----------|-------------|
| **最优结果** | 41 findings | 37 findings | 42 findings |
| **轮数** | 3 | 4 | 4 |
| **自适应** | 规则驱动 | 学习驱动 | 主题驱动 |
| **可解释性** | 高 | 中 | 中 |

## 🔄 组合使用

### 贝叶斯 + 自主探索
```bash
python autorun_evolve_v3.4.py "Topic" --bayesian --explore --explore-depth 2
```

## 📁 文件结构

```
autoresearch/
├── autorun_evolve.py          # v3.2 原始版本
├── autorun_evolve_v3.3.py     # v3.3 贝叶斯优化
├── autorun_evolve_v3.4.py     # v3.4 统一版本 ⭐
├── CAPABILITIES.md            # 完整能力清单
├── BAYESIAN_OPTIMIZATION.md   # 贝叶斯优化文档
└── _cache/                    # 缓存目录
```

## 🎓 学术基础

- **Karpathy 闭环**: Andrej Karpathy 的自主进化论文
- **贝叶斯优化**: Gaussian Process + Expected Improvement
- **自主探索**: 主题提取 + 迭代学习

## ✨ v3.4 新增

- ✅ 统一接口：三种模式无缝切换
- ✅ 模式组合：支持 `--bayesian --explore` 同时启用
- ✅ 完整文档：每种模式详细说明
- ✅ 性能对比：量化各模式优劣

---

**AutoResearch v3.4 已完全融合三大模式，提供完整的自主研究能力。**
