"""
Trend Analysis - 趋势分析
使用统计方法分析监控数据趋势和异常
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import stats


class TrendAnalysis:
    """
    趋势分析
    
    功能:
    - 线性回归趋势分析
    - 移动平均计算
    - Z-score 异常检测
    - 周期性分析
    """
    
    @staticmethod
    def calculate_trend(metrics_history: List[Dict], 
                        metric_name: str) -> Dict:
        """
        计算趋势 (线性回归)
        
        Args:
            metrics_history: 历史指标列表
            metric_name: 指标名称
        
        Returns:
            趋势信息字典
        """
        values = [m.get(metric_name, 0) for m in metrics_history]
        
        if len(values) < 2:
            return {
                'slope': 0,
                'intercept': values[0] if values else 0,
                'r_squared': 0,
                'trend': 'stable',
                'p_value': 1.0,
            }
        
        # 线性回归
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        
        # 判断趋势
        if slope > 0.01:
            trend = 'increasing'
        elif slope < -0.01:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_value ** 2),
            'trend': trend,
            'p_value': float(p_value),
            'std_err': float(std_err),
        }
    
    @staticmethod
    def calculate_moving_average(values: List[float], 
                                  window_size: int = 10) -> List[float]:
        """
        计算移动平均
        
        Args:
            values: 数值列表
            window_size: 窗口大小
        
        Returns:
            移动平均值列表
        """
        if len(values) < window_size:
            return values
        
        result = []
        for i in range(len(values)):
            if i < window_size - 1:
                # 前 window_size-1 个使用可用数据
                window = values[:i+1]
            else:
                window = values[i-window_size+1:i+1]
            
            result.append(sum(window) / len(window))
        
        return result
    
    @staticmethod
    def detect_anomaly_zscore(metrics_history: List[Dict], 
                               metric_name: str, 
                               threshold: float = 2.0) -> List[int]:
        """
        使用 Z-score 检测异常
        
        Args:
            metrics_history: 历史指标列表
            metric_name: 指标名称
            threshold: Z-score 阈值
        
        Returns:
            异常点的索引列表
        """
        values = np.array([m.get(metric_name, 0) for m in metrics_history])
        
        if len(values) < 3:
            return []
        
        # 计算 Z-score
        z_scores = np.abs(stats.zscore(values))
        
        # 找出异常点
        anomalies = np.where(z_scores > threshold)[0].tolist()
        
        return anomalies
    
    @staticmethod
    def detect_anomaly_iqr(metrics_history: List[Dict], 
                            metric_name: str, 
                            multiplier: float = 1.5) -> List[int]:
        """
        使用 IQR (四分位距) 检测异常
        
        Args:
            metrics_history: 历史指标列表
            metric_name: 指标名称
            multiplier: IQR 乘数
        
        Returns:
            异常点的索引列表
        """
        values = np.array([m.get(metric_name, 0) for m in metrics_history])
        
        if len(values) < 4:
            return []
        
        # 计算四分位数
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        
        # 计算边界
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        
        # 找出异常点
        anomalies = np.where((values < lower_bound) | (values > upper_bound))[0].tolist()
        
        return anomalies
    
    @staticmethod
    def calculate_statistics(metrics_history: List[Dict], 
                             metric_name: str) -> Dict:
        """
        计算统计信息
        
        Args:
            metrics_history: 历史指标列表
            metric_name: 指标名称
        
        Returns:
            统计信息字典
        """
        values = [m.get(metric_name, 0) for m in metrics_history]
        
        if not values:
            return {}
        
        arr = np.array(values)
        
        return {
            'count': len(values),
            'mean': float(np.mean(arr)),
            'median': float(np.median(arr)),
            'std': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'q1': float(np.percentile(arr, 25)),
            'q3': float(np.percentile(arr, 75)),
            'range': float(np.max(arr) - np.min(arr)),
        }
    
    @staticmethod
    def detect_seasonality(values: List[float], 
                           period: int = 24) -> Dict:
        """
        检测周期性 (简化版)
        
        Args:
            values: 数值列表
            period: 周期长度
        
        Returns:
            周期性分析结果
        """
        if len(values) < period * 2:
            return {'has_seasonality': False, 'period': period}
        
        # 计算自相关系数
        autocorr = np.correlate(values, values, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # 寻找峰值
        peaks = []
        for i in range(1, len(autocorr) - 1):
            if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                peaks.append((i, autocorr[i]))
        
        # 检查是否有明显的周期性
        has_seasonality = len(peaks) > 0 and peaks[0][0] == period
        
        return {
            'has_seasonality': has_seasonality,
            'period': period,
            'peak_correlation': float(peaks[0][1]) if peaks else 0,
        }
    
    @staticmethod
    def forecast_simple(values: List[float], 
                        steps: int = 5) -> List[float]:
        """
        简单预测 (线性外推)
        
        Args:
            values: 历史数值
            steps: 预测步数
        
        Returns:
            预测值列表
        """
        if len(values) < 2:
            return [values[-1]] * steps if values else [0] * steps
        
        # 线性回归
        x = np.arange(len(values))
        slope, intercept, _, _, _ = stats.linregress(x, values)
        
        # 预测
        forecasts = []
        for i in range(steps):
            forecast = slope * (len(values) + i) + intercept
            forecasts.append(float(forecast))
        
        return forecasts


# 测试代码
if __name__ == "__main__":
    import json
    
    # 创建测试数据
    metrics_history = []
    for i in range(100):
        # 模拟数据 (带趋势和异常)
        base_value = 100 + i * 0.5  # 上升趋势
        noise = np.random.normal(0, 5)  # 噪声
        
        # 添加异常值
        if i in [20, 50, 80]:
            value = base_value + 30  # 异常高值
        else:
            value = base_value + noise
        
        metrics_history.append({
            'timestamp': f'2026-03-23T{i:02d}:00:00',
            'latency': value,
            'accuracy': 0.85 + np.random.normal(0, 0.02),
        })
    
    # 趋势分析
    trend = TrendAnalysis.calculate_trend(metrics_history, 'latency')
    print("Trend Analysis:")
    print(json.dumps(trend, indent=2))
    
    # 异常检测 (Z-score)
    anomalies_zscore = TrendAnalysis.detect_anomaly_zscore(
        metrics_history, 'latency', threshold=2.0
    )
    print(f"\nAnomalies (Z-score): {anomalies_zscore}")
    
    # 异常检测 (IQR)
    anomalies_iqr = TrendAnalysis.detect_anomaly_iqr(
        metrics_history, 'latency', multiplier=1.5
    )
    print(f"Anomalies (IQR): {anomalies_iqr}")
    
    # 统计信息
    stats = TrendAnalysis.calculate_statistics(metrics_history, 'latency')
    print("\nStatistics:")
    print(json.dumps(stats, indent=2))
    
    # 移动平均
    values = [m['latency'] for m in metrics_history]
    ma = TrendAnalysis.calculate_moving_average(values, window_size=10)
    print(f"\nMoving Average (last 5): {ma[-5:]}")
    
    # 预测
    forecasts = TrendAnalysis.forecast_simple(values, steps=5)
    print(f"Forecasts (next 5): {forecasts}")
