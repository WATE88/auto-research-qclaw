"""
AutoResearch 真实任务适配器
============================
把实际的 ML 训练函数（PyTorch / sklearn / 任意可调用对象）
包装成 AutoRunEngine 可以直接消费的任务格式。

用法示例：
    from real_task_adapter import RealTaskAdapter, pytorch_mnist_objective

    adapter = RealTaskAdapter()
    # 方式一：注册 PyTorch MNIST 任务（内置示例）
    task_id = adapter.register_pytorch_mnist()

    # 方式二：注册自定义函数
    def my_train(params):
        lr, wd = params["lr"], params["weight_decay"]
        # ... 训练代码 ...
        return val_accuracy   # 返回越大越好的标量

    task_id = adapter.register(
        name="我的训练任务",
        objective_fn=my_train,
        search_space={"lr": (1e-4, 1e-1), "weight_decay": (1e-5, 1e-2)},
        max_iter=20,
        strategy="EI",
    )

    # 方式三：直接注入到已运行的 AutoRunEngine
    from autoresearch_autorun import AutoRunEngine
    engine = AutoRunEngine()
    adapter.inject(engine, "我的训练任务", my_train, ...)
"""

import math
import time
import random
import threading
from typing import Callable, Dict, Tuple, Optional, Any

# ─────────────────────────────────────────────────────────────────
# 内置示例目标函数（无真实 GPU 也能运行的轻量版）
# ─────────────────────────────────────────────────────────────────

def pytorch_mnist_objective(params: Dict) -> float:
    """
    MNIST 训练目标函数（轻量模拟版，不需要 GPU/数据集）
    -------------------------------------------------------
    模拟一个 3 层 MLP 在 MNIST 上的验证准确率曲线：
    - lr, weight_decay, dropout 对最终 val_acc 有非线性影响
    - 加入随机噪声模拟真实训练的随机性
    - 实际执行约 0.1s（模拟 5 个 epoch）

    如需接入真实 PyTorch 训练，只需替换此函数体。
    """
    lr           = params.get("lr", 1e-3)
    weight_decay = params.get("weight_decay", 1e-4)
    dropout      = params.get("dropout", 0.2)
    batch_size   = params.get("batch_size", 64)

    # 模拟训练延迟（真实情况下这里跑 PyTorch 训练）
    time.sleep(0.08)

    # 真实 MNIST 上 MLP 的经验公式（基于 log-scale 超参数）
    lr_score  = _lr_response(lr)
    wd_score  = _wd_response(weight_decay)
    do_score  = _dropout_response(dropout)
    bs_score  = _batch_response(batch_size)

    base_acc  = 0.60 + 0.30 * lr_score * wd_score * do_score * bs_score
    noise     = random.gauss(0, 0.008)  # 训练随机性

    val_acc = max(0.5, min(0.995, base_acc + noise))
    return round(val_acc, 4)


def _lr_response(lr: float) -> float:
    """学习率响应：bell-curve 中心在 1e-3"""
    log_lr = math.log10(max(lr, 1e-7))
    center = -3.0   # log10(1e-3)
    return math.exp(-0.5 * ((log_lr - center) / 1.2) ** 2)


def _wd_response(wd: float) -> float:
    """正则化响应：太大惩罚过度，太小欠正则"""
    log_wd = math.log10(max(wd, 1e-8))
    center = -4.0   # log10(1e-4)
    return 0.7 + 0.3 * math.exp(-0.5 * ((log_wd - center) / 1.5) ** 2)


def _dropout_response(dropout: float) -> float:
    """Dropout 响应：0.2-0.4 最优"""
    return 1.0 - 0.8 * (dropout - 0.3) ** 2


def _batch_response(batch_size: float) -> float:
    """Batch size 响应：64/128 最优"""
    opt = 96.0
    return 0.85 + 0.15 * math.exp(-((batch_size - opt) / 60) ** 2)


# ─────────────────────────────────────────────────────────────────
# sklearn 示例：SVM on 合成数据集
# ─────────────────────────────────────────────────────────────────

def sklearn_svm_objective(params: Dict) -> float:
    """
    SVM 超参调优示例（轻量模拟版）
    C, gamma 对 val_accuracy 的响应
    """
    C     = params.get("C", 1.0)
    gamma = params.get("gamma", 0.1)
    time.sleep(0.05)

    log_C     = math.log10(max(C, 1e-3))
    log_gamma = math.log10(max(gamma, 1e-5))

    # 经验响应：C~10, gamma~0.01 附近最优
    c_score     = math.exp(-0.5 * ((log_C - 1.0) / 1.5) ** 2)
    gamma_score = math.exp(-0.5 * ((log_gamma - (-2.0)) / 1.2) ** 2)

    base_acc = 0.70 + 0.22 * c_score * gamma_score
    noise    = random.gauss(0, 0.01)
    return max(0.5, min(0.99, base_acc + noise))


# ─────────────────────────────────────────────────────────────────
# LightGBM / XGBoost 示例（通用树模型调参）
# ─────────────────────────────────────────────────────────────────

def tree_model_objective(params: Dict) -> float:
    """
    树模型（LightGBM/XGBoost）超参调优（轻量模拟版）
    """
    n_estimators    = int(params.get("n_estimators", 100))
    max_depth       = int(params.get("max_depth", 6))
    learning_rate   = params.get("learning_rate", 0.1)
    subsample       = params.get("subsample", 0.8)
    time.sleep(0.06)

    lr_s  = math.exp(-0.5 * ((math.log10(max(learning_rate, 1e-4)) - (-1)) / 0.8) ** 2)
    n_s   = min(1.0, n_estimators / 300)
    d_s   = 1.0 - 0.15 * abs(max_depth - 6) / 6
    ss_s  = 0.7 + 0.3 * subsample

    base  = 0.72 + 0.20 * lr_s * n_s * d_s * ss_s
    noise = random.gauss(0, 0.007)
    return max(0.5, min(0.99, base + noise))


# ─────────────────────────────────────────────────────────────────
# 适配器主类
# ─────────────────────────────────────────────────────────────────

class RealTaskAdapter:
    """
    把真实 ML 训练函数包装成 AutoRunEngine 兼容的任务模板。

    AutoRunEngine.TASK_TEMPLATES 格式：
    {
        "name": str,
        "func": callable(params: dict) -> float,
        "space": {param_name: (lo, hi), ...},
        "max_iter": int,
        "strategy": "EI" | "UCB" | "PI",
    }
    """

    # 内置预设任务
    PRESETS = {
        "mnist_mlp": {
            "name": "MNIST-MLP 超参优化",
            "func": pytorch_mnist_objective,
            "space": {
                "lr":           (1e-4, 1e-1),
                "weight_decay": (1e-5, 1e-2),
                "dropout":      (0.0,  0.5),
                "batch_size":   (16,   256),
            },
            "max_iter": 30,
            "strategy": "EI",
        },
        "svm": {
            "name": "SVM-RBF 超参优化",
            "func": sklearn_svm_objective,
            "space": {
                "C":     (0.01, 1000.0),
                "gamma": (1e-4, 10.0),
            },
            "max_iter": 25,
            "strategy": "UCB",
        },
        "tree_model": {
            "name": "树模型超参优化 (LightGBM/XGBoost)",
            "func": tree_model_objective,
            "space": {
                "n_estimators":  (50,   500),
                "max_depth":     (2,    12),
                "learning_rate": (0.01, 0.3),
                "subsample":     (0.5,  1.0),
            },
            "max_iter": 35,
            "strategy": "EI",
        },
    }

    def __init__(self):
        self._registered: list = []

    # ── 注册预设任务 ──────────────────────────────────────────────

    def get_preset(self, name: str) -> dict:
        """获取预设任务配置（可直接 append 到 TASK_TEMPLATES）"""
        if name not in self.PRESETS:
            raise ValueError(f"未知预设: {name}，可用: {list(self.PRESETS.keys())}")
        return dict(self.PRESETS[name])   # 返回副本

    # ── 注册自定义函数 ────────────────────────────────────────────

    def make_task(
        self,
        name: str,
        objective_fn: Callable[[Dict], float],
        search_space: Dict[str, Tuple[float, float]],
        max_iter: int = 25,
        strategy: str = "EI",
    ) -> dict:
        """
        把任意目标函数包装成 AutoRunEngine 任务模板字典。

        Parameters
        ----------
        name         : 任务显示名称
        objective_fn : 接受 params dict，返回越大越好的 float
        search_space : {"param_name": (min_val, max_val)}
        max_iter     : 贝叶斯优化迭代次数
        strategy     : "EI" / "UCB" / "PI"
        """
        task = {
            "name":     name,
            "func":     objective_fn,
            "space":    search_space,
            "max_iter": max_iter,
            "strategy": strategy,
        }
        self._registered.append(task)
        return task

    # ── 注入到已有引擎 ────────────────────────────────────────────

    def inject_presets_to_engine(self, engine, preset_names: Optional[list] = None):
        """
        把预设任务注入到运行中的 AutoRunEngine.TASK_TEMPLATES。
        下一个调度周期就会执行这些真实任务。

        Parameters
        ----------
        engine       : AutoRunEngine 实例
        preset_names : 要注入的预设名列表；None = 全部注入
        """
        names = preset_names or list(self.PRESETS.keys())
        injected = []
        for n in names:
            tmpl = self.get_preset(n)
            engine.TASK_TEMPLATES.append(tmpl)
            injected.append(tmpl["name"])
        return injected

    def inject_custom_to_engine(self, engine, name, objective_fn, search_space,
                                 max_iter=25, strategy="EI"):
        """把自定义函数直接注入到运行中的引擎"""
        task = self.make_task(name, objective_fn, search_space, max_iter, strategy)
        engine.TASK_TEMPLATES.append(task)
        return task


# ─────────────────────────────────────────────────────────────────
# 真实 PyTorch 训练包装模板（用户填入自己的代码）
# ─────────────────────────────────────────────────────────────────

def YOUR_PYTORCH_TRAINING_FUNCTION(params: Dict) -> float:
    """
    ========================================================
    [模板] 用你自己的 PyTorch 训练代码替换此函数体
    ========================================================

    参数：
        params: dict  贝叶斯优化建议的超参数字典

    返回：
        float  验证集指标（越大越好，如 val_accuracy）
               如果你的指标是 val_loss，返回 -val_loss

    示例（真实 PyTorch 代码骨架）：
    """
    lr           = params["lr"]
    weight_decay = params.get("weight_decay", 1e-4)
    dropout      = params.get("dropout", 0.2)

    # ── 下面替换为你的真实训练代码 ──────────────────────────
    # import torch
    # import torch.nn as nn
    # from torch.utils.data import DataLoader
    # from torchvision import datasets, transforms
    #
    # # 定义模型
    # model = nn.Sequential(
    #     nn.Flatten(),
    #     nn.Linear(784, 256),
    #     nn.ReLU(),
    #     nn.Dropout(dropout),
    #     nn.Linear(256, 10)
    # )
    #
    # optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    # criterion = nn.CrossEntropyLoss()
    #
    # # 训练 n_epochs
    # for epoch in range(5):
    #     for x, y in train_loader:
    #         pred = model(x)
    #         loss = criterion(pred, y)
    #         optimizer.zero_grad()
    #         loss.backward()
    #         optimizer.step()
    #
    # # 验证
    # correct = 0
    # with torch.no_grad():
    #     for x, y in val_loader:
    #         pred = model(x).argmax(1)
    #         correct += (pred == y).sum().item()
    # val_acc = correct / len(val_dataset)
    # return val_acc
    # ── 上面替换为你的真实训练代码 ──────────────────────────

    # 占位返回（未替换时不报错）
    return pytorch_mnist_objective(params)


# ─────────────────────────────────────────────────────────────────
# CLI 快速演示
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AutoResearch 真实任务适配器 — 快速演示")
    print("=" * 60)

    adapter = RealTaskAdapter()

    # 演示 1：直接运行 MNIST 目标函数
    print("\n[演示 1] MNIST-MLP 目标函数评测（10组随机超参）")
    print(f"{'lr':>10} {'wd':>12} {'dropout':>10} {'val_acc':>10}")
    print("-" * 50)
    import random as _rng
    for _ in range(10):
        p = {
            "lr":           10 ** _rng.uniform(-4, -1),
            "weight_decay": 10 ** _rng.uniform(-5, -2),
            "dropout":      _rng.uniform(0, 0.5),
            "batch_size":   _rng.choice([16, 32, 64, 128, 256]),
        }
        score = pytorch_mnist_objective(p)
        print(f"{p['lr']:>10.2e} {p['weight_decay']:>12.2e} {p['dropout']:>10.3f} {score:>10.4f}")

    # 演示 2：贝叶斯优化 vs 随机搜索
    print("\n[演示 2] 贝叶斯优化 20 步搜索 MNIST 超参")
    from autoresearch_autorun import SimpleBayesianOptimizer
    opt = SimpleBayesianOptimizer(
        search_space={"lr": (1e-4, 1e-1), "weight_decay": (1e-5, 1e-2),
                      "dropout": (0.0, 0.5), "batch_size": (16, 256)},
        strategy="EI"
    )
    for step in range(20):
        p = opt.suggest()
        score = pytorch_mnist_objective(p)
        opt.observe(p, score)
        if step % 5 == 4:
            print(f"  step={step+1:2d}  best={opt.best_score:.4f}  "
                  f"lr={opt.best_params['lr']:.2e}  "
                  f"dropout={opt.best_params['dropout']:.3f}")

    print(f"\n最优超参: {opt.best_params}")
    print(f"最优分:   {opt.best_score:.4f}")

    # 演示 3：列出所有可用预设
    print("\n[演示 3] 可用预设任务")
    for key, tmpl in RealTaskAdapter.PRESETS.items():
        space_str = ", ".join(f"{k}∈[{v[0]:.1g},{v[1]:.1g}]" for k, v in tmpl["space"].items())
        print(f"  [{key}] {tmpl['name']}")
        print(f"    搜索空间: {space_str}")
        print(f"    迭代次数: {tmpl['max_iter']}  策略: {tmpl['strategy']}")

    print("\n✅ 演示完成！使用 RealTaskAdapter().inject_presets_to_engine(engine) 注入到 AutoRun。")
