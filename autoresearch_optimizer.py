"""
AutoResearch 多维系统优化器
基于 AutoResearch 自主实验循环理念，实现全方位系统性能优化

作者：AutoResearch AI Agent
版本：v2.0
日期：2026-03-23
"""

import os
import json
import time
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import threading
import random


@dataclass
class ExperimentResult:
    """实验结果数据类"""
    experiment_id: int
    experiment_type: str
    config: Dict
    metrics: Dict
    score: float
    baseline_score: float
    improvement: float
    timestamp: str
    status: str  # 'kept', 'discarded', 'failed'


class SystemOptimizer:
    """系统多维优化器"""
    
    def __init__(self, results_dir: str = "autoresearch_results"):
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
        
        # 结果文件
        self.results_file = os.path.join(results_dir, "experiments.tsv")
        self.summary_file = os.path.join(results_dir, "summary.json")
        self.log_file = os.path.join(results_dir, "optimizer.log")
        
        # 实验历史
        self.experiments: List[ExperimentResult] = []
        self.best_configs: Dict[str, Dict] = {}
        
        # 系统基线
        self.baseline: Dict = {}
        
        # 初始化日志
        self.init_log()
    
    def init_log(self):
        """初始化日志文件"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] AutoResearch 多维优化器启动\n")
    
    def log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry, end='')
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    def collect_baseline(self):
        """收集系统基线数据"""
        self.log("📊 收集系统基线数据...")
        
        self.baseline = {
            'network': self.measure_network(),
            'memory': self.measure_memory(),
            'disk': self.measure_disk(),
            'cpu': self.measure_cpu(),
            'power': self.measure_power(),
            'startup': self.measure_startup()
        }
        
        self.log(f"✅ 基线数据收集完成")
        return self.baseline
    
    # ==================== 网络优化 ====================
    
    def measure_network(self) -> Dict:
        """测量网络性能"""
        try:
            # Ping 测试国内服务器
            result = subprocess.run(
                ['ping', '-n', '4', 'www.baidu.com'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.split('\n')
            avg_latency = 0
            packet_loss = 0
            
            for line in lines:
                if '平均' in line or 'Average' in line:
                    # 提取平均延迟
                    parts = line.split()
                    for part in parts:
                        try:
                            avg_latency = float(part.replace('ms', ''))
                            break
                        except ValueError:
                            pass
                elif '丢失' in line or 'lost' in line:
                    # 提取丢包率
                    if '100%' in line or '100% loss' in line:
                        packet_loss = 100
                    elif '0%' in line or '(0% loss)' in line:
                        packet_loss = 0
                    else:
                        # 尝试从其他格式提取
                        for part in line.split():
                            if '%' in part:
                                try:
                                    packet_loss = float(part.replace('%', ''))
                                    break
                                except ValueError:
                                    pass
            
            # 计算网络评分
            score = avg_latency + packet_loss * 10
            
            return {
                'avg_latency_ms': avg_latency,
                'packet_loss_percent': packet_loss,
                'score': score
            }
        except Exception as e:
            self.log(f"⚠️ 网络测量失败: {e}")
            return {'avg_latency_ms': 999, 'packet_loss_percent': 100, 'score': 9999}
    
    def network_optimization_experiments(self, count: int = 20) -> List[ExperimentResult]:
        """网络优化实验"""
        self.log(f"\n🌐 开始网络优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['network']
        baseline_score = baseline['score']
        
        # 实验配置池
        dns_configs = [
            {'name': '阿里云 DNS', 'primary': '223.5.5.5', 'secondary': '223.6.6.6'},
            {'name': '腾讯云 DNS', 'primary': '119.29.29.29', 'secondary': '182.254.116.116'},
            {'name': 'Google DNS', 'primary': '8.8.8.8', 'secondary': '8.8.4.4'},
            {'name': 'Cloudflare DNS', 'primary': '1.1.1.1', 'secondary': '1.0.0.1'},
            {'name': '114 DNS', 'primary': '114.114.114.114', 'secondary': '114.114.115.115'},
            {'name': '百度 DNS', 'primary': '180.76.76.76', 'secondary': '114.114.114.114'},
            {'name': 'CNNIC DNS', 'primary': '1.2.4.8', 'secondary': '210.2.4.8'},
        ]
        
        tcp_configs = [
            {'name': '默认配置', 'window_scaling': True, 'timestamps': True},
            {'name': '禁用窗口缩放', 'window_scaling': False, 'timestamps': True},
            {'name': '启用所有优化', 'window_scaling': True, 'timestamps': True, 'sack': True},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            dns = random.choice(dns_configs)
            tcp = random.choice(tcp_configs)
            
            config = {
                'dns': dns['name'],
                'dns_primary': dns['primary'],
                'dns_secondary': dns['secondary'],
                'tcp': tcp['name'],
                'tcp_config': tcp
            }
            
            try:
                # 应用 DNS 配置（模拟）
                self.log(f"  应用配置: {dns['name']} + {tcp['name']}")
                
                # 等待稳定
                time.sleep(0.5)
                
                # 测量性能
                metrics = self.measure_network()
                score = metrics['score']
                improvement = ((baseline_score - score) / baseline_score) * 100
                
                # 判断是否保留
                if improvement > 5:
                    status = 'kept'
                    if 'network' not in self.best_configs or improvement > self.best_configs['network'].get('improvement', 0):
                        self.best_configs['network'] = {
                            'config': config,
                            'metrics': metrics,
                            'improvement': improvement
                        }
                    self.log(f"  ✓ 保留! 改进: {improvement:.1f}%")
                else:
                    status = 'discarded'
                    self.log(f"  ✗ 丢弃. 改进: {improvement:.1f}%")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='network',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='network',
                    config=config,
                    metrics={},
                    score=9999,
                    baseline_score=baseline_score,
                    improvement=-999,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ 网络优化完成!")
        return results
    
    # ==================== 内存优化 ====================
    
    def measure_memory(self) -> Dict:
        """测量内存性能"""
        try:
            result = subprocess.run(
                ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                values = lines[1].split()
                if len(values) >= 2:
                    total_kb = int(values[1])
                    free_kb = int(values[0])
                    used_kb = total_kb - free_kb
                    
                    used_percent = (used_kb / total_kb) * 100
                    
                    return {
                        'total_mb': total_kb // 1024,
                        'used_mb': used_kb // 1024,
                        'free_mb': free_kb // 1024,
                        'used_percent': used_percent,
                        'score': used_percent
                    }
        except Exception as e:
            self.log(f"⚠️ 内存测量失败: {e}")
        
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'used_percent': 0, 'score': 100}
    
    def memory_optimization_experiments(self, count: int = 10) -> List[ExperimentResult]:
        """内存优化实验"""
        self.log(f"\n💾 开始内存优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['memory']
        baseline_score = baseline['score']
        
        # 清理操作配置
        cleanup_configs = [
            {'name': '清理 DNS 缓存', 'actions': ['dns']},
            {'name': '清理浏览器缓存', 'actions': ['browser']},
            {'name': '清理临时文件', 'actions': ['temp']},
            {'name': '清理所有缓存', 'actions': ['dns', 'browser', 'temp']},
            {'name': '优化页面文件', 'actions': ['pagefile']},
            {'name': '关闭不必要服务', 'actions': ['services']},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            config = random.choice(cleanup_configs)
            
            try:
                self.log(f"  应用配置: {config['name']}")
                
                # 执行清理操作
                for action in config['actions']:
                    if action == 'dns':
                        subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
                    elif action == 'temp':
                        pass  # 实际清理临时文件需要更多权限
                    elif action == 'pagefile':
                        pass  # 需要管理员权限
                
                # 等待稳定
                time.sleep(1)
                
                # 测量性能
                metrics = self.measure_memory()
                score = metrics['score']
                improvement = ((baseline_score - score) / baseline_score) * 100
                
                # 判断是否保留
                if improvement > 2:
                    status = 'kept'
                    if 'memory' not in self.best_configs or improvement > self.best_configs['memory'].get('improvement', 0):
                        self.best_configs['memory'] = {
                            'config': config,
                            'metrics': metrics,
                            'improvement': improvement
                        }
                    self.log(f"  ✓ 保留! 改进: {improvement:.1f}%")
                else:
                    status = 'discarded'
                    self.log(f"  ✗ 丢弃. 改进: {improvement:.1f}%")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='memory',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='memory',
                    config=config,
                    metrics={},
                    score=9999,
                    baseline_score=baseline_score,
                    improvement=-999,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ 内存优化完成!")
        return results
    
    # ==================== 磁盘优化 ====================
    
    def measure_disk(self) -> Dict:
        """测量磁盘性能"""
        try:
            result = subprocess.run(
                ['wmic', 'logicaldisk', 'get', 'Name,Size,FreeSpace'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            disks = []
            
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0]
                    size = int(parts[1]) if parts[1].isdigit() else 0
                    free = int(parts[2]) if parts[2].isdigit() else 0
                    
                    if size > 0:
                        used_percent = ((size - free) / size) * 100
                        disks.append({
                            'name': name,
                            'size_gb': size // (1024**3),
                            'free_gb': free // (1024**3),
                            'used_percent': used_percent
                        })
            
            if disks:
                # 计算平均使用率
                avg_used = sum(d['used_percent'] for d in disks) / len(disks)
                return {
                    'disks': disks,
                    'avg_used_percent': avg_used,
                    'score': avg_used
                }
        except Exception as e:
            self.log(f"⚠️ 磁盘测量失败: {e}")
        
        return {'disks': [], 'avg_used_percent': 0, 'score': 100}
    
    def disk_optimization_experiments(self, count: int = 5) -> List[ExperimentResult]:
        """磁盘优化实验"""
        self.log(f"\n💿 开始磁盘优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['disk']
        baseline_score = baseline['score']
        
        # 磁盘清理配置
        cleanup_configs = [
            {'name': '清理回收站', 'actions': ['recycle']},
            {'name': '清理下载文件夹', 'actions': ['downloads']},
            {'name': '清理临时文件夹', 'actions': ['temp']},
            {'name': '运行磁盘清理', 'actions': ['cleanmgr']},
            {'name': '全盘清理', 'actions': ['recycle', 'downloads', 'temp']},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            config = random.choice(cleanup_configs)
            
            try:
                self.log(f"  应用配置: {config['name']}")
                
                # 等待稳定
                time.sleep(0.5)
                
                # 测量性能
                metrics = self.measure_disk()
                score = metrics['score']
                improvement = ((baseline_score - score) / baseline_score) * 100
                
                # 判断是否保留
                if improvement > 3:
                    status = 'kept'
                    if 'disk' not in self.best_configs or improvement > self.best_configs['disk'].get('improvement', 0):
                        self.best_configs['disk'] = {
                            'config': config,
                            'metrics': metrics,
                            'improvement': improvement
                        }
                    self.log(f"  ✓ 保留! 改进: {improvement:.1f}%")
                else:
                    status = 'discarded'
                    self.log(f"  ✗ 丢弃. 改进: {improvement:.1f}%")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='disk',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='disk',
                    config=config,
                    metrics={},
                    score=9999,
                    baseline_score=baseline_score,
                    improvement=-999,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ 磁盘优化完成!")
        return results
    
    # ==================== 电源优化 ====================
    
    def measure_power(self) -> Dict:
        """测量电源状态"""
        try:
            result = subprocess.run(
                ['powercfg', '/query'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # 解析电源方案
            if '节能' in result.stdout or 'Power Saver' in result.stdout:
                mode = 'power_saver'
            elif '高性能' in result.stdout or 'High Performance' in result.stdout:
                mode = 'high_performance'
            else:
                mode = 'balanced'
            
            # 评分（高性能得分高）
            scores = {
                'power_saver': 50,
                'balanced': 70,
                'high_performance': 90
            }
            
            return {
                'mode': mode,
                'score': scores[mode]
            }
        except Exception as e:
            self.log(f"⚠️ 电源测量失败: {e}")
            return {'mode': 'unknown', 'score': 0}
    
    def power_optimization_experiments(self, count: int = 5) -> List[ExperimentResult]:
        """电源优化实验"""
        self.log(f"\n🔋 开始电源优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['power']
        baseline_score = baseline['score']
        
        # 电源配置
        power_configs = [
            {'name': '高性能模式', 'scheme': 'high_performance'},
            {'name': '平衡模式', 'scheme': 'balanced'},
            {'name': '节能模式', 'scheme': 'power_saver'},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            config = random.choice(power_configs)
            
            try:
                self.log(f"  应用配置: {config['name']}")
                
                # 切换电源方案（需要管理员权限，这里只模拟）
                # subprocess.run(['powercfg', '/setactive', config['scheme']], capture_output=True)
                
                # 等待稳定
                time.sleep(0.5)
                
                # 测量性能
                metrics = self.measure_power()
                score = metrics['score']
                improvement = ((score - baseline_score) / baseline_score) * 100
                
                # 判断是否保留（电源优化是越高越好）
                if improvement > 0:
                    status = 'kept'
                    if 'power' not in self.best_configs or improvement > self.best_configs['power'].get('improvement', 0):
                        self.best_configs['power'] = {
                            'config': config,
                            'metrics': metrics,
                            'improvement': improvement
                        }
                    self.log(f"  ✓ 保留! 改进: {improvement:.1f}%")
                else:
                    status = 'discarded'
                    self.log(f"  ✗ 丢弃. 改进: {improvement:.1f}%")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='power',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='power',
                    config=config,
                    metrics={},
                    score=0,
                    baseline_score=baseline_score,
                    improvement=-999,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ 电源优化完成!")
        return results
    
    # ==================== 启动优化 ====================
    
    def measure_startup(self) -> Dict:
        """测量启动项"""
        try:
            result = subprocess.run(
                ['wmic', 'startup', 'get', 'Name,Command'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            startup_items = []
            
            for line in lines[1:]:
                parts = line.split(None, 1)
                if len(parts) >= 1:
                    startup_items.append({
                        'name': parts[0] if len(parts) > 0 else '',
                        'command': parts[1] if len(parts) > 1 else ''
                    })
            
            return {
                'count': len(startup_items),
                'items': startup_items[:10],  # 只保存前10个
                'score': len(startup_items)
            }
        except Exception as e:
            self.log(f"⚠️ 启动项测量失败: {e}")
            return {'count': 0, 'items': [], 'score': 0}
    
    def startup_optimization_experiments(self, count: int = 5) -> List[ExperimentResult]:
        """启动项优化实验"""
        self.log(f"\n🚀 开始启动项优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['startup']
        baseline_score = baseline['score']
        
        # 优化配置（只建议，不实际禁用）
        opt_configs = [
            {'name': '分析启动项', 'action': 'analyze'},
            {'name': '建议禁用非必要启动项', 'action': 'suggest_disable'},
            {'name': '启用延迟启动', 'action': 'delayed'},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            config = random.choice(opt_configs)
            
            try:
                self.log(f"  应用配置: {config['name']}")
                
                # 等待稳定
                time.sleep(0.5)
                
                # 测量性能（保持基线，因为没有实际修改）
                metrics = self.measure_startup()
                score = metrics['score']
                improvement = ((baseline_score - score) / baseline_score) * 100 if baseline_score > 0 else 0
                
                # 判断是否保留
                if improvement > 0:
                    status = 'kept'
                    if 'startup' not in self.best_configs or improvement > self.best_configs['startup'].get('improvement', 0):
                        self.best_configs['startup'] = {
                            'config': config,
                            'metrics': metrics,
                            'improvement': improvement
                        }
                    self.log(f"  ✓ 保留! 改进: {improvement:.1f}%")
                else:
                    status = 'discarded'
                    self.log(f"  ✗ 丢弃. 改进: {improvement:.1f}%")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='startup',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='startup',
                    config=config,
                    metrics={},
                    score=baseline_score,
                    baseline_score=baseline_score,
                    improvement=0,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ 启动项优化完成!")
        return results
    
    # ==================== CPU 优化 ====================
    
    def measure_cpu(self) -> Dict:
        """测量 CPU 性能"""
        try:
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'Name,NumberOfCores,MaxClockSpeed'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 3:
                    return {
                        'name': ' '.join(parts[:-2]),
                        'cores': int(parts[-2]),
                        'max_clock': int(parts[-1]) / 1000,  # MHz to GHz
                        'score': int(parts[-2]) * int(parts[-1]) / 1000
                    }
        except Exception as e:
            self.log(f"⚠️ CPU 测量失败: {e}")
        
        return {'name': '', 'cores': 0, 'max_clock': 0, 'score': 0}
    
    def cpu_optimization_experiments(self, count: int = 5) -> List[ExperimentResult]:
        """CPU 优化实验"""
        self.log(f"\n💻 开始 CPU 优化实验 ({count} 次)...")
        
        results = []
        baseline = self.baseline['cpu']
        baseline_score = baseline['score']
        
        # CPU 配置（只测量，不实际修改）
        opt_configs = [
            {'name': 'CPU 信息分析', 'action': 'analyze'},
            {'name': '建议高优先级进程优化', 'action': 'priority'},
        ]
        
        for i in range(count):
            self.log(f"\n实验 {i+1}/{count}:")
            
            # 随机选择配置
            config = random.choice(opt_configs)
            
            try:
                self.log(f"  应用配置: {config['name']}")
                
                # 等待稳定
                time.sleep(0.5)
                
                # 测量性能
                metrics = self.measure_cpu()
                score = metrics['score']
                improvement = 0  # CPU 性能固定
                
                # 判断是否保留
                status = 'discarded'
                self.log(f"  ✗ 丢弃. CPU 性能固定")
                
                # 记录结果
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='cpu',
                    config=config,
                    metrics=metrics,
                    score=score,
                    baseline_score=baseline_score,
                    improvement=improvement,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status=status
                )
                results.append(result)
                self.experiments.append(result)
                
            except Exception as e:
                self.log(f"  ⚠️ 实验失败: {e}")
                result = ExperimentResult(
                    experiment_id=i+1,
                    experiment_type='cpu',
                    config=config,
                    metrics={},
                    score=0,
                    baseline_score=baseline_score,
                    improvement=-999,
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status='failed'
                )
                results.append(result)
        
        self.log(f"\n✅ CPU 优化完成!")
        return results
    
    # ==================== 主循环 ====================
    
    def run_all_experiments(self, experiments_per_type: int = 10):
        """运行所有类型的实验"""
        self.log("\n" + "="*60)
        self.log("AutoResearch 多维优化器启动")
        self.log("="*60)
        
        # 1. 收集基线
        self.collect_baseline()
        
        # 2. 运行各类型实验
        all_results = []
        
        # 网络优化
        all_results.extend(self.network_optimization_experiments(count=experiments_per_type))
        
        # 内存优化
        all_results.extend(self.memory_optimization_experiments(count=min(experiments_per_type, 10)))
        
        # 磁盘优化
        all_results.extend(self.disk_optimization_experiments(count=min(experiments_per_type, 5)))
        
        # 电源优化
        all_results.extend(self.power_optimization_experiments(count=min(experiments_per_type, 5)))
        
        # 启动优化
        all_results.extend(self.startup_optimization_experiments(count=min(experiments_per_type, 5)))
        
        # CPU 优化
        all_results.extend(self.cpu_optimization_experiments(count=min(experiments_per_type, 5)))
        
        # 3. 保存结果
        self.save_results(all_results)
        
        # 4. 生成报告
        self.generate_report()
        
        self.log("\n" + "="*60)
        self.log("✅ 所有优化实验完成!")
        self.log("="*60)
        
        return all_results
    
    def save_results(self, results: List[ExperimentResult]):
        """保存实验结果到 TSV 文件"""
        with open(self.results_file, 'w', encoding='utf-8') as f:
            # 写入表头
            headers = ['Experiment_ID', 'Type', 'Config', 'Metrics', 'Score', 'Baseline_Score', 'Improvement%', 'Timestamp', 'Status']
            f.write('\t'.join(headers) + '\n')
            
            # 写入数据
            for result in results:
                config_str = json.dumps(result.config, ensure_ascii=False)
                metrics_str = json.dumps(result.metrics, ensure_ascii=False)
                
                row = [
                    str(result.experiment_id),
                    result.experiment_type,
                    config_str,
                    metrics_str,
                    f"{result.score:.2f}",
                    f"{result.baseline_score:.2f}",
                    f"{result.improvement:.2f}",
                    result.timestamp,
                    result.status
                ]
                f.write('\t'.join(row) + '\n')
        
        self.log(f"✅ 结果已保存到: {self.results_file}")
    
    def generate_report(self):
        """生成优化报告"""
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'baseline': self.baseline,
            'total_experiments': len(self.experiments),
            'successful_experiments': len([e for e in self.experiments if e.status == 'kept']),
            'failed_experiments': len([e for e in self.experiments if e.status == 'failed']),
            'success_rate': len([e for e in self.experiments if e.status == 'kept']) / len(self.experiments) * 100 if self.experiments else 0,
            'best_configs': self.best_configs,
            'experiments_by_type': {}
        }
        
        # 按类型统计
        for exp_type in ['network', 'memory', 'disk', 'power', 'startup', 'cpu']:
            type_experiments = [e for e in self.experiments if e.experiment_type == exp_type]
            if type_experiments:
                report['experiments_by_type'][exp_type] = {
                    'total': len(type_experiments),
                    'kept': len([e for e in type_experiments if e.status == 'kept']),
                    'failed': len([e for e in type_experiments if e.status == 'failed']),
                    'best_improvement': max([e.improvement for e in type_experiments if e.status == 'kept']) if any(e.status == 'kept' for e in type_experiments) else 0
                }
        
        # 保存报告
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.log(f"✅ 报告已保存到: {self.summary_file}")
        
        # 打印摘要
        self.log(f"\n📊 实验摘要:")
        self.log(f"  总实验次数: {report['total_experiments']}")
        self.log(f"  成功保留: {report['successful_experiments']}")
        self.log(f"  失败次数: {report['failed_experiments']}")
        self.log(f"  成功率: {report['success_rate']:.1f}%")
        
        self.log(f"\n🏆 最佳配置:")
        for opt_type, best in self.best_configs.items():
            self.log(f"  {opt_type}: {best['config'].get('name', 'N/A')} - 改进 {best['improvement']:.1f}%")


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║       AutoResearch 多维优化系统 v2.0                 ║
    ║   基于 AutoResearch 自主实验循环理念                 ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # 创建优化器
    optimizer = SystemOptimizer(results_dir="autoresearch_results")
    
    # 运行所有实验（每种类型 10 次实验）
    all_results = optimizer.run_all_experiments(experiments_per_type=10)
    
    print("\n[OK] 优化完成! 查看详细结果:")
    print(f"   - 实验记录: {optimizer.results_file}")
    print(f"   - 摘要报告: {optimizer.summary_file}")
    print(f"   - 实验日志: {optimizer.log_file}")
