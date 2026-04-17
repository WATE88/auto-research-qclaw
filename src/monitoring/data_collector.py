"""
Monitoring Data Collector - 监控数据收集器
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque


class MonitoringDataCollector:
    """
    监控数据收集器
    
    功能:
    - 收集当前指标
    - 存储历史数据
    - 提供数据查询
    - 数据持久化
    """
    
    def __init__(self, prometheus_monitoring, max_history_size: int = 10000):
        """
        初始化数据收集器
        
        Args:
            prometheus_monitoring: Prometheus 监控实例
            max_history_size: 最大历史数据条数
        """
        self.prometheus = prometheus_monitoring
        self.max_history_size = max_history_size
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.collection_start_time = datetime.now()
        self.collection_count = 0
    
    def collect_metrics(self) -> Dict:
        """
        收集当前指标
        
        Returns:
            当前指标字典
        """
        metrics = self.prometheus.get_current_metrics()
        
        # 添加时间戳
        metrics['timestamp'] = datetime.now().isoformat()
        metrics['collection_id'] = self.collection_count
        
        # 存储历史
        self.metrics_history.append(metrics)
        self.collection_count += 1
        
        return metrics
    
    def collect_batch(self, interval: float = 1.0, count: int = 10) -> List[Dict]:
        """
        批量收集指标
        
        Args:
            interval: 收集间隔 (秒)
            count: 收集次数
        
        Returns:
            收集的指标列表
        """
        collected = []
        
        for i in range(count):
            metrics = self.collect_metrics()
            collected.append(metrics)
            
            if i < count - 1:
                time.sleep(interval)
        
        return collected
    
    def get_metrics_history(self, window_size: Optional[int] = None) -> List[Dict]:
        """
        获取指标历史
        
        Args:
            window_size: 窗口大小 (默认全部)
        
        Returns:
            历史指标列表
        """
        if window_size is None:
            return list(self.metrics_history)
        else:
            return list(self.metrics_history)[-window_size:]
    
    def get_latest_metrics(self) -> Optional[Dict]:
        """
        获取最新指标
        
        Returns:
            最新指标或 None
        """
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_metrics_by_time_range(self, start_time: datetime, 
                                   end_time: datetime) -> List[Dict]:
        """
        获取时间范围内的指标
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            时间范围内的指标列表
        """
        result = []
        
        for metrics in self.metrics_history:
            metrics_time = datetime.fromisoformat(metrics['timestamp'])
            if start_time <= metrics_time <= end_time:
                result.append(metrics)
        
        return result
    
    def get_summary_statistics(self, window_size: int = 100) -> Dict:
        """
        获取汇总统计
        
        Args:
            window_size: 窗口大小
        
        Returns:
            统计信息字典
        """
        history = self.get_metrics_history(window_size)
        
        if not history:
            return {}
        
        # 计算统计信息
        stats = {
            'window_size': len(history),
            'collection_duration_seconds': (
                datetime.now() - self.collection_start_time
            ).total_seconds(),
            'metrics': {}
        }
        
        # 对数值型指标计算统计
        numeric_keys = [
            'request_count', 'error_count', 'avg_latency', 
            'avg_accuracy', 'cpu_usage', 'memory_usage'
        ]
        
        for key in numeric_keys:
            values = [m.get(key, 0) for m in history if key in m]
            if values:
                stats['metrics'][key] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'count': len(values),
                }
        
        return stats
    
    def save_to_file(self, filepath: str = "metrics_history.json"):
        """
        保存历史数据到文件
        
        Args:
            filepath: 文件路径
        """
        data = {
            'collection_start_time': self.collection_start_time.isoformat(),
            'collection_count': self.collection_count,
            'history': list(self.metrics_history),
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Metrics history saved to {filepath}")
    
    def load_from_file(self, filepath: str = "metrics_history.json") -> bool:
        """
        从文件加载历史数据
        
        Args:
            filepath: 文件路径
        
        Returns:
            是否成功加载
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.collection_start_time = datetime.fromisoformat(
                data['collection_start_time']
            )
            self.collection_count = data['collection_count']
            self.metrics_history = deque(data['history'], maxlen=self.max_history_size)
            
            print(f"Metrics history loaded from {filepath}")
            return True
        
        except FileNotFoundError:
            print(f"File not found: {filepath}")
            return False
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return False
    
    def clear_history(self):
        """清空历史数据"""
        self.metrics_history.clear()
        self.collection_count = 0
        self.collection_start_time = datetime.now()
        print("Metrics history cleared")
    
    def get_collection_rate(self) -> float:
        """
        获取收集速率 (条/秒)
        
        Returns:
            收集速率
        """
        duration = (datetime.now() - self.collection_start_time).total_seconds()
        if duration > 0:
            return self.collection_count / duration
        return 0


# 测试代码
if __name__ == "__main__":
    from prometheus_integration import PrometheusMonitoring
    
    # 创建监控实例
    monitoring = PrometheusMonitoring()
    
    # 创建数据收集器
    collector = MonitoringDataCollector(monitoring)
    
    # 模拟记录一些请求
    for i in range(50):
        monitoring.record_request(
            latency=0.1 + (i % 10) * 0.01,
            success=(i % 10) != 0,
            accuracy=0.85 + (i % 5) * 0.01
        )
        
        # 收集指标
        collector.collect_metrics()
        
        # 模拟时间间隔
        time.sleep(0.01)
    
    # 获取历史数据
    history = collector.get_metrics_history(10)
    print(f"Collected {len(history)} metrics")
    
    # 获取汇总统计
    stats = collector.get_summary_statistics()
    print("\nSummary Statistics:")
    print(json.dumps(stats, indent=2))
    
    # 保存到文件
    collector.save_to_file()
