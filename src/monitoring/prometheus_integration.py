"""
Prometheus Monitoring Integration - Prometheus 监控集成
"""

import time
from typing import Dict, Optional
from datetime import datetime


class PrometheusMonitoring:
    """
    Prometheus 监控集成
    
    功能:
    - 定义系统性能指标
    - 定义业务指标
    - 定义资源指标
    - 记录请求和性能数据
    """
    
    def __init__(self, registry=None):
        """
        初始化 Prometheus 监控
        
        Args:
            registry: Prometheus registry (可选)
        """
        self.registry = registry
        
        # 如果没有 registry，使用内存存储
        if registry is None:
            self._use_memory_storage = True
            self._metrics = self._init_memory_metrics()
        else:
            self._use_memory_storage = False
            self._init_prometheus_metrics()
    
    def _init_memory_metrics(self) -> Dict:
        """初始化内存存储的指标"""
        return {
            'request_count': 0,
            'error_count': 0,
            'total_latency': 0.0,
            'accuracy_sum': 0.0,
            'accuracy_count': 0,
            'cpu_usage': 0.0,
            'memory_usage': 0,
            'active_connections': 0,
            'cache_hits': 0,
            'cache_misses': 0,
        }
    
    def _init_prometheus_metrics(self):
        """初始化 Prometheus 指标"""
        try:
            from prometheus_client import Counter, Histogram, Gauge
            
            # 系统性能指标
            self.request_count = Counter(
                'autoresearch_requests_total',
                'Total requests',
                registry=self.registry
            )
            
            self.request_latency = Histogram(
                'autoresearch_request_latency_seconds',
                'Request latency in seconds',
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
                registry=self.registry
            )
            
            self.error_count = Counter(
                'autoresearch_errors_total',
                'Total errors',
                registry=self.registry
            )
            
            # 业务指标
            self.accuracy = Gauge(
                'autoresearch_accuracy',
                'Current accuracy percentage',
                registry=self.registry
            )
            
            self.precision = Gauge(
                'autoresearch_precision',
                'Current precision percentage',
                registry=self.registry
            )
            
            self.recall = Gauge(
                'autoresearch_recall',
                'Current recall percentage',
                registry=self.registry
            )
            
            # 资源指标
            self.cpu_usage = Gauge(
                'autoresearch_cpu_usage_percent',
                'CPU usage percentage',
                registry=self.registry
            )
            
            self.memory_usage = Gauge(
                'autoresearch_memory_usage_bytes',
                'Memory usage in bytes',
                registry=self.registry
            )
            
            self.active_connections = Gauge(
                'autoresearch_active_connections',
                'Active connections',
                registry=self.registry
            )
            
            # 缓存指标
            self.cache_hits = Counter(
                'autoresearch_cache_hits_total',
                'Total cache hits',
                registry=self.registry
            )
            
            self.cache_misses = Counter(
                'autoresearch_cache_misses_total',
                'Total cache misses',
                registry=self.registry
            )
            
        except ImportError:
            print("Warning: prometheus_client not installed, using memory storage")
            self._use_memory_storage = True
            self._metrics = self._init_memory_metrics()
    
    def record_request(self, latency: float, success: bool = True, 
                       accuracy: Optional[float] = None):
        """
        记录请求
        
        Args:
            latency: 延迟 (秒)
            success: 是否成功
            accuracy: 准确率 (可选)
        """
        if self._use_memory_storage:
            self._metrics['request_count'] += 1
            self._metrics['total_latency'] += latency
            
            if not success:
                self._metrics['error_count'] += 1
            
            if accuracy is not None:
                self._metrics['accuracy_sum'] += accuracy
                self._metrics['accuracy_count'] += 1
        else:
            self.request_count.inc()
            self.request_latency.observe(latency)
            
            if not success:
                self.error_count.inc()
            
            if accuracy is not None:
                self.accuracy.set(accuracy * 100)
    
    def record_cache(self, hit: bool):
        """
        记录缓存命中/未命中
        
        Args:
            hit: 是否命中
        """
        if self._use_memory_storage:
            if hit:
                self._metrics['cache_hits'] += 1
            else:
                self._metrics['cache_misses'] += 1
        else:
            if hit:
                self.cache_hits.inc()
            else:
                self.cache_misses.inc()
    
    def set_resource_usage(self, cpu_percent: float, memory_bytes: int):
        """
        设置资源使用情况
        
        Args:
            cpu_percent: CPU 使用率 (%)
            memory_bytes: 内存使用 (字节)
        """
        if self._use_memory_storage:
            self._metrics['cpu_usage'] = cpu_percent
            self._metrics['memory_usage'] = memory_bytes
        else:
            self.cpu_usage.set(cpu_percent)
            self.memory_usage.set(memory_bytes)
    
    def set_active_connections(self, count: int):
        """
        设置活动连接数
        
        Args:
            count: 连接数
        """
        if self._use_memory_storage:
            self._metrics['active_connections'] = count
        else:
            self.active_connections.set(count)
    
    def get_current_metrics(self) -> Dict:
        """
        获取当前指标
        
        Returns:
            当前指标字典
        """
        if self._use_memory_storage:
            metrics = self._metrics.copy()
            
            # 计算派生指标
            if metrics['request_count'] > 0:
                metrics['avg_latency'] = metrics['total_latency'] / metrics['request_count']
                metrics['error_rate'] = metrics['error_count'] / metrics['request_count']
            else:
                metrics['avg_latency'] = 0
                metrics['error_rate'] = 0
            
            if metrics['accuracy_count'] > 0:
                metrics['avg_accuracy'] = metrics['accuracy_sum'] / metrics['accuracy_count']
            else:
                metrics['avg_accuracy'] = 0
            
            total_cache = metrics['cache_hits'] + metrics['cache_misses']
            if total_cache > 0:
                metrics['cache_hit_rate'] = metrics['cache_hits'] / total_cache
            else:
                metrics['cache_hit_rate'] = 0
            
            return metrics
        else:
            # Prometheus 指标
            return {
                'request_count': self.request_count._value.get(),
                'error_count': self.error_count._value.get(),
                'accuracy': self.accuracy._value.get(),
                'cpu_usage': self.cpu_usage._value.get(),
                'memory_usage': self.memory_usage._value.get(),
                'active_connections': self.active_connections._value.get(),
            }
    
    def get_metrics_for_prometheus(self) -> str:
        """
        获取 Prometheus 格式的指标
        
        Returns:
            Prometheus 格式的指标字符串
        """
        if self._use_memory_storage:
            metrics = self.get_current_metrics()
            
            output = []
            output.append(f"# HELP autoresearch_requests_total Total requests")
            output.append(f"# TYPE autoresearch_requests_total counter")
            output.append(f"autoresearch_requests_total {metrics['request_count']}")
            
            output.append(f"# HELP autoresearch_errors_total Total errors")
            output.append(f"# TYPE autoresearch_errors_total counter")
            output.append(f"autoresearch_errors_total {metrics['error_count']}")
            
            output.append(f"# HELP autoresearch_avg_latency Average latency")
            output.append(f"# TYPE autoresearch_avg_latency gauge")
            output.append(f"autoresearch_avg_latency {metrics.get('avg_latency', 0)}")
            
            output.append(f"# HELP autoresearch_accuracy Current accuracy")
            output.append(f"# TYPE autoresearch_accuracy gauge")
            output.append(f"autoresearch_accuracy {metrics.get('avg_accuracy', 0)}")
            
            output.append(f"# HELP autoresearch_cpu_usage_percent CPU usage")
            output.append(f"# TYPE autoresearch_cpu_usage_percent gauge")
            output.append(f"autoresearch_cpu_usage_percent {metrics['cpu_usage']}")
            
            output.append(f"# HELP autoresearch_cache_hit_rate Cache hit rate")
            output.append(f"# TYPE autoresearch_cache_hit_rate gauge")
            output.append(f"autoresearch_cache_hit_rate {metrics.get('cache_hit_rate', 0)}")
            
            return '\n'.join(output)
        else:
            from prometheus_client import generate_latest
            return generate_latest(self.registry).decode('utf-8')
    
    def reset(self):
        """重置所有指标"""
        if self._use_memory_storage:
            self._metrics = self._init_memory_metrics()
        else:
            # 重新初始化
            self._init_prometheus_metrics()


# 测试代码
if __name__ == "__main__":
    # 创建监控实例
    monitoring = PrometheusMonitoring()
    
    # 模拟记录一些请求
    for i in range(100):
        monitoring.record_request(
            latency=0.1 + (i % 10) * 0.01,
            success=(i % 10) != 0,
            accuracy=0.85 + (i % 5) * 0.01
        )
    
    # 记录缓存
    for i in range(50):
        monitoring.record_cache(hit=(i % 3) != 0)
    
    # 设置资源使用
    monitoring.set_resource_usage(cpu_percent=45.5, memory_bytes=1024*1024*500)
    monitoring.set_active_connections(25)
    
    # 获取当前指标
    metrics = monitoring.get_current_metrics()
    print("Current Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # 获取 Prometheus 格式
    print("\nPrometheus Format:")
    print(monitoring.get_metrics_for_prometheus())
