"""
Bayesian Optimizer - 贝叶斯优化器
使用高斯过程自动优化系统参数
"""

from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
from datetime import datetime
import time


class BayesianOptimizer:
    """
    贝叶斯优化器 - 自动优化系统参数
    
    功能:
    - 使用高斯过程进行智能采样
    - 自动优化多个参数
    - 记录优化历史
    - 保存优化结果
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化贝叶斯优化器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.optimization_history: List[Dict] = []
        self.best_params: Optional[Dict] = None
        self.best_score: float = float('inf')
        self.optimization_start_time: Optional[float] = None
        
        # 定义参数空间
        self.space = self._define_search_space()
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载优化配置"""
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                pass
        
        # 默认配置
        return {
            "n_calls": 50,  # 优化迭代次数
            "n_initial_points": 10,  # 初始随机点数
            "random_state": 42,
            "latency_weight": 0.6,  # 延迟权重
            "accuracy_weight": 0.4,  # 准确率权重
        }
    
    def _define_search_space(self) -> List:
        """定义搜索空间"""
        return [
            Real(0.1, 0.5, name='arxiv_weight'),
            Real(0.1, 0.5, name='github_weight'),
            Real(0.1, 0.5, name='hn_weight'),
            Real(0.1, 0.5, name='product_hunt_weight'),
            Real(0.1, 0.5, name='twitter_weight'),
            Integer(1, 10, name='concurrent_tasks'),
            Integer(30, 300, name='timeout_seconds'),
            Integer(60, 3600, name='cache_ttl'),
            Integer(1, 100, name='batch_size'),
        ]
    
    @use_named_args([
        Real(0.1, 0.5, name='arxiv_weight'),
        Real(0.1, 0.5, name='github_weight'),
        Real(0.1, 0.5, name='hn_weight'),
        Real(0.1, 0.5, name='product_hunt_weight'),
        Real(0.1, 0.5, name='twitter_weight'),
        Integer(1, 10, name='concurrent_tasks'),
        Integer(30, 300, name='timeout_seconds'),
        Integer(60, 3600, name='cache_ttl'),
        Integer(1, 100, name='batch_size'),
    ])
    def objective(self, arxiv_weight: float, github_weight: float, hn_weight: float,
                  product_hunt_weight: float, twitter_weight: float,
                  concurrent_tasks: int, timeout_seconds: int, cache_ttl: int,
                  batch_size: int) -> float:
        """
        目标函数：最小化延迟，最大化准确率
        
        Args:
            arxiv_weight: ArXiv 权重
            github_weight: GitHub 权重
            hn_weight: Hacker News 权重
            product_hunt_weight: Product Hunt 权重
            twitter_weight: Twitter 权重
            concurrent_tasks: 并发任务数
            timeout_seconds: 超时时间
            cache_ttl: 缓存 TTL
            batch_size: 批处理大小
        
        Returns:
            目标值 (越小越好)
        """
        params = {
            'arxiv_weight': arxiv_weight,
            'github_weight': github_weight,
            'hn_weight': hn_weight,
            'product_hunt_weight': product_hunt_weight,
            'twitter_weight': twitter_weight,
            'concurrent_tasks': concurrent_tasks,
            'timeout_seconds': timeout_seconds,
            'cache_ttl': cache_ttl,
            'batch_size': batch_size,
        }
        
        try:
            # 运行系统获取性能指标
            result = self._run_system_with_params(params)
            
            # 计算目标值 (越小越好)
            # 延迟权重 * 延迟 - 准确率权重 * 准确率
            latency_score = result['latency'] * self.config['latency_weight']
            accuracy_score = -result['accuracy'] * self.config['accuracy_weight']
            score = latency_score + accuracy_score
            
            # 记录历史
            self.optimization_history.append({
                'params': params,
                'score': score,
                'latency': result['latency'],
                'accuracy': result['accuracy'],
                'timestamp': datetime.now().isoformat(),
            })
            
            # 更新最优参数
            if score < self.best_score:
                self.best_score = score
                self.best_params = params.copy()
                print(f"New best score: {score:.4f}")
                print(f"Best params: {params}")
            
            return score
        
        except Exception as e:
            print(f"Error in objective function: {e}")
            return float('inf')
    
    def _run_system_with_params(self, params: Dict) -> Dict:
        """
        使用给定参数运行系统
        
        Args:
            params: 参数字典
        
        Returns:
            性能指标字典
        """
        # 这里应该集成实际的系统运行逻辑
        # 暂时使用模拟数据进行测试
        
        # 模拟延迟计算 (基于参数)
        base_latency = 1000  # ms
        concurrent_factor = 1.0 / params['concurrent_tasks']
        batch_factor = params['batch_size'] / 50
        timeout_factor = params['timeout_seconds'] / 100
        
        # 权重均衡因子
        total_weight = (params['arxiv_weight'] + params['github_weight'] + 
                       params['hn_weight'] + params['product_hunt_weight'] +
                       params['twitter_weight'])
        weight_factor = 1.0 / (total_weight / 5)
        
        latency = base_latency * (concurrent_factor * 0.3 + batch_factor * 0.2 + 
                                  timeout_factor * 0.2 + weight_factor * 0.3)
        
        # 模拟准确率计算
        base_accuracy = 0.70
        weight_accuracy = (params['arxiv_weight'] + params['github_weight'] + 
                          params['hn_weight']) / 3 * 0.1
        cache_accuracy = params['cache_ttl'] / 3600 * 0.1
        batch_accuracy = params['batch_size'] / 100 * 0.1
        
        accuracy = min(0.95, base_accuracy + weight_accuracy + cache_accuracy + batch_accuracy)
        
        return {
            'latency': latency,
            'accuracy': accuracy,
            'throughput': params['concurrent_tasks'] * 10,
        }
    
    def optimize(self) -> Tuple[Dict, float]:
        """
        执行贝叶斯优化
        
        Returns:
            最优参数字典和最优分数
        """
        print("=" * 60)
        print("Starting Bayesian Optimization...")
        print("=" * 60)
        
        self.optimization_start_time = time.time()
        
        result = gp_minimize(
            self.objective,
            dimensions=self.space,
            n_calls=self.config['n_calls'],
            n_initial_points=self.config['n_initial_points'],
            random_state=self.config['random_state'],
            verbose=True,
            n_jobs=-1,
        )
        
        optimization_time = time.time() - self.optimization_start_time
        
        print("=" * 60)
        print(f"Optimization complete!")
        print(f"Total time: {optimization_time:.2f} seconds")
        print(f"Best score: {result.fun:.4f}")
        print(f"Best params: {self.best_params}")
        print("=" * 60)
        
        return self.best_params, self.best_score
    
    def get_optimization_history(self) -> List[Dict]:
        """获取优化历史"""
        return self.optimization_history
    
    def save_results(self, output_path: str = "optimization_results.json"):
        """
        保存优化结果
        
        Args:
            output_path: 输出文件路径
        """
        results = {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'history': self.optimization_history,
            'config': self.config,
            'timestamp': datetime.now().isoformat(),
            'optimization_time_seconds': time.time() - self.optimization_start_time 
                if self.optimization_start_time else None,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to {output_path}")
    
    def load_previous_results(self, input_path: str = "optimization_results.json"):
        """
        加载之前的优化结果
        
        Args:
            input_path: 输入文件路径
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            self.best_params = results.get('best_params')
            self.best_score = results.get('best_score', float('inf'))
            self.optimization_history = results.get('history', [])
            
            print(f"Loaded previous results from {input_path}")
            return True
        
        except FileNotFoundError:
            print(f"No previous results found at {input_path}")
            return False


class ParameterOptimizer:
    """
    参数优化器 - 管理多个优化维度
    """
    
    def __init__(self):
        self.optimizers: Dict[str, BayesianOptimizer] = {}
        self.current_params: Dict[str, Dict] = {}
    
    def add_optimizer(self, name: str, optimizer: BayesianOptimizer):
        """
        添加优化器
        
        Args:
            name: 优化器名称
            optimizer: 贝叶斯优化器实例
        """
        self.optimizers[name] = optimizer
    
    def optimize_all(self) -> Dict:
        """
        优化所有参数
        
        Returns:
            所有优化结果
        """
        results = {}
        
        for name, optimizer in self.optimizers.items():
            print(f"\nOptimizing {name}...")
            params, score = optimizer.optimize()
            results[name] = {
                'params': params,
                'score': score,
            }
            self.current_params[name] = params
        
        return results
    
    def apply_params(self, system):
        """
        应用优化后的参数到系统
        
        Args:
            system: 目标系统实例
        """
        for name, params in self.current_params.items():
            print(f"Applying {name} params: {params}")
            system.update_params(params)
    
    def save_all_results(self, output_dir: str = "."):
        """
        保存所有优化结果
        
        Args:
            output_dir: 输出目录
        """
        for name, optimizer in self.optimizers.items():
            output_path = f"{output_dir}/{name}_optimization_results.json"
            optimizer.save_results(output_path)


# 测试代码
if __name__ == "__main__":
    # 创建优化器
    optimizer = BayesianOptimizer()
    
    # 执行优化 (使用较少的迭代进行快速测试)
    optimizer.config['n_calls'] = 10
    optimizer.config['n_initial_points'] = 3
    
    best_params, best_score = optimizer.optimize()
    
    # 保存结果
    optimizer.save_results()
    
    print("\nFinal Results:")
    print(f"Best Score: {best_score:.4f}")
    print(f"Best Params: {best_params}")
