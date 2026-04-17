"""
Dynamic Adjustment - 基于监控数据的动态调整
"""

from typing import Dict, List, Optional
from datetime import datetime


class DynamicAdjustment:
    """
    基于监控数据的动态调整
    
    功能:
    - 基于指标自动调整参数
    - 错误率过高时增加超时
    - 准确率下降时重新优化
    - CPU 过高时减少并发
    - 记录调整历史
    """
    
    def __init__(self, system, bayesian_optimizer, alerting_system=None):
        """
        初始化动态调整
        
        Args:
            system: 目标系统实例
            bayesian_optimizer: 贝叶斯优化器实例
            alerting_system: 告警系统实例 (可选)
        """
        self.system = system
        self.optimizer = bayesian_optimizer
        self.alerting = alerting_system
        self.adjustment_history: List[Dict] = []
        
        # 调整规则配置
        self.adjustment_rules = self._init_adjustment_rules()
    
    def _init_adjustment_rules(self) -> Dict:
        """初始化调整规则"""
        return {
            'high_error_rate': {
                'metric': 'error_count',
                'threshold': 10,
                'operator': '>',
                'action': 'increase_timeout',
                'adjustment': {'timeout_seconds': 30},
                'max_value': 300,
            },
            'low_accuracy': {
                'metric': 'accuracy',
                'threshold': 80,
                'operator': '<',
                'action': 'reoptimize',
                'adjustment': {},  # 动态计算
            },
            'high_cpu': {
                'metric': 'cpu_usage',
                'threshold': 80,
                'operator': '>',
                'action': 'decrease_concurrency',
                'adjustment': {'concurrent_tasks': -1},
                'min_value': 1,
            },
            'high_memory': {
                'metric': 'memory_usage',
                'threshold': 85,
                'operator': '>',
                'action': 'increase_cache_ttl',
                'adjustment': {'cache_ttl': 600},
                'max_value': 3600,
            },
            'low_cache_hit_rate': {
                'metric': 'cache_hit_rate',
                'threshold': 0.7,
                'operator': '<',
                'action': 'increase_cache_size',
                'adjustment': {},  # 动态计算
            },
        }
    
    def adjust_based_on_metrics(self, metrics: Dict) -> Dict:
        """
        基于指标进行调整
        
        Args:
            metrics: 当前指标
        
        Returns:
            调整结果
        """
        adjustments = {}
        triggered_rules = []
        
        for rule_name, rule in self.adjustment_rules.items():
            metric_value = metrics.get(rule['metric'])
            
            if metric_value is None:
                continue
            
            # 检查是否触发规则
            triggered = False
            if rule['operator'] == '>' and metric_value > rule['threshold']:
                triggered = True
            elif rule['operator'] == '<' and metric_value < rule['threshold']:
                triggered = True
            
            if triggered:
                triggered_rules.append(rule_name)
                
                # 执行调整动作
                if rule['action'] == 'increase_timeout':
                    current_timeout = self.system.params.get('timeout_seconds', 150)
                    new_timeout = min(
                        current_timeout + rule['adjustment']['timeout_seconds'],
                        rule['max_value']
                    )
                    adjustments['timeout_seconds'] = new_timeout
                    print(f"High error rate detected, increasing timeout to {new_timeout}s")
                
                elif rule['action'] == 'reoptimize':
                    print(f"Low accuracy detected ({metric_value}%), re-optimizing...")
                    try:
                        params, score = self.optimizer.optimize()
                        adjustments.update(params)
                        print(f"Re-optimization complete, new params: {params}")
                    except Exception as e:
                        print(f"Re-optimization failed: {e}")
                
                elif rule['action'] == 'decrease_concurrency':
                    current_concurrent = self.system.params.get('concurrent_tasks', 5)
                    new_concurrent = max(
                        current_concurrent + rule['adjustment']['concurrent_tasks'],
                        rule['min_value']
                    )
                    adjustments['concurrent_tasks'] = new_concurrent
                    print(f"High CPU detected, decreasing concurrency to {new_concurrent}")
                
                elif rule['action'] == 'increase_cache_ttl':
                    current_ttl = self.system.params.get('cache_ttl', 1800)
                    new_ttl = min(
                        current_ttl + rule['adjustment']['cache_ttl'],
                        rule['max_value']
                    )
                    adjustments['cache_ttl'] = new_ttl
                    print(f"High memory detected, increasing cache TTL to {new_ttl}s")
                
                elif rule['action'] == 'increase_cache_size':
                    # 动态计算缓存大小
                    current_size = self.system.params.get('cache_size', 1000)
                    new_size = int(current_size * 1.5)
                    adjustments['cache_size'] = new_size
                    print(f"Low cache hit rate detected, increasing cache size to {new_size}")
        
        # 应用调整
        if adjustments:
            self._apply_adjustments(adjustments, metrics, triggered_rules)
        
        return {
            'adjustments': adjustments,
            'triggered_rules': triggered_rules,
            'timestamp': datetime.now().isoformat(),
        }
    
    def _apply_adjustments(self, adjustments: Dict, metrics: Dict, 
                           triggered_rules: List[str]):
        """
        应用调整
        
        Args:
            adjustments: 调整参数
            metrics: 当前指标
            triggered_rules: 触发的规则
        """
        # 更新系统参数
        self.system.update_params(adjustments)
        
        # 记录调整历史
        adjustment_record = {
            'timestamp': datetime.now().isoformat(),
            'adjustments': adjustments,
            'metrics_before': metrics,
            'triggered_rules': triggered_rules,
        }
        
        self.adjustment_history.append(adjustment_record)
        
        # 发送告警
        if self.alerting:
            for rule in triggered_rules:
                self.alerting.send_alert({
                    'rule': rule,
                    'severity': 'warning',
                    'message': f"Auto-adjustment triggered: {rule}",
                    'adjustments': adjustments,
                })
        
        print(f"Applied adjustments: {adjustments}")
    
    def get_adjustment_history(self, limit: int = 100) -> List[Dict]:
        """
        获取调整历史
        
        Args:
            limit: 返回条数限制
        
        Returns:
            调整历史列表
        """
        return self.adjustment_history[-limit:]
    
    def get_adjustment_summary(self) -> Dict:
        """
        获取调整汇总
        
        Returns:
            调整汇总信息
        """
        if not self.adjustment_history:
            return {
                'total_adjustments': 0,
                'most_triggered_rule': None,
                'recent_adjustments': [],
            }
        
        # 统计触发规则
        rule_counts = {}
        for record in self.adjustment_history:
            for rule in record['triggered_rules']:
                rule_counts[rule] = rule_counts.get(rule, 0) + 1
        
        most_triggered = max(rule_counts.items(), key=lambda x: x[1]) if rule_counts else None
        
        return {
            'total_adjustments': len(self.adjustment_history),
            'most_triggered_rule': most_triggered,
            'rule_trigger_counts': rule_counts,
            'recent_adjustments': self.adjustment_history[-5:],
        }
    
    def reset_adjustment_rules(self, rules: Dict):
        """
        重置调整规则
        
        Args:
            rules: 新的规则字典
        """
        self.adjustment_rules = rules
        print("Adjustment rules reset")
    
    def add_adjustment_rule(self, name: str, rule: Dict):
        """
        添加调整规则
        
        Args:
            name: 规则名称
            rule: 规则配置
        """
        self.adjustment_rules[name] = rule
        print(f"Added adjustment rule: {name}")
    
    def remove_adjustment_rule(self, name: str):
        """
        移除调整规则
        
        Args:
            name: 规则名称
        """
        if name in self.adjustment_rules:
            del self.adjustment_rules[name]
            print(f"Removed adjustment rule: {name}")


# 模拟系统类 (用于测试)
class MockSystem:
    """模拟系统"""
    
    def __init__(self):
        self.params = {
            'timeout_seconds': 150,
            'concurrent_tasks': 5,
            'cache_ttl': 1800,
            'cache_size': 1000,
        }
    
    def update_params(self, params: Dict):
        """更新参数"""
        self.params.update(params)
        print(f"System params updated: {self.params}")


# 测试代码
if __name__ == "__main__":
    from bayesian_optimizer import BayesianOptimizer
    
    # 创建模拟系统
    system = MockSystem()
    
    # 创建优化器
    optimizer = BayesianOptimizer()
    optimizer.config['n_calls'] = 5
    optimizer.config['n_initial_points'] = 2
    
    # 创建动态调整
    dynamic_adj = DynamicAdjustment(system, optimizer)
    
    # 测试场景 1: 高错误率
    print("\n=== Test 1: High Error Rate ===")
    metrics1 = {
        'error_count': 15,  # 超过阈值 10
        'accuracy': 85,
        'cpu_usage': 50,
    }
    result1 = dynamic_adj.adjust_based_on_metrics(metrics1)
    print(f"Adjustments: {result1['adjustments']}")
    
    # 测试场景 2: 低准确率
    print("\n=== Test 2: Low Accuracy ===")
    metrics2 = {
        'error_count': 5,
        'accuracy': 75,  # 低于阈值 80
        'cpu_usage': 50,
    }
    result2 = dynamic_adj.adjust_based_on_metrics(metrics2)
    print(f"Adjustments: {result2['adjustments']}")
    
    # 测试场景 3: 高 CPU
    print("\n=== Test 3: High CPU ===")
    metrics3 = {
        'error_count': 5,
        'accuracy': 85,
        'cpu_usage': 85,  # 超过阈值 80
    }
    result3 = dynamic_adj.adjust_based_on_metrics(metrics3)
    print(f"Adjustments: {result3['adjustments']}")
    
    # 获取调整历史
    print("\n=== Adjustment History ===")
    history = dynamic_adj.get_adjustment_history()
    print(f"Total adjustments: {len(history)}")
    
    # 获取调整汇总
    summary = dynamic_adj.get_adjustment_summary()
    print(f"\nAdjustment Summary:")
    print(f"Total: {summary['total_adjustments']}")
    print(f"Most triggered: {summary['most_triggered_rule']}")
