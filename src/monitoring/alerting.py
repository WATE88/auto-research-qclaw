"""
Alerting System - 告警系统
支持 Slack、Email 等多种告警渠道
"""

import json
from typing import Dict, List, Optional
from datetime import datetime


class AlertingSystem:
    """
    告警系统
    
    功能:
    - 定义告警规则
    - 检查告警条件
    - 发送告警通知
    - 记录告警历史
    - 支持多种告警渠道
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化告警系统
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.alert_rules = self._init_alert_rules()
        self.alerts: List[Dict] = []
        self.alert_history: List[Dict] = []
        
        # 告警去重 (避免重复告警)
        self.recent_alerts: Dict[str, datetime] = {}
        self.deduplication_window_seconds = 300  # 5 分钟
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载配置"""
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                pass
        
        # 默认配置
        return {
            'slack_webhook': None,
            'email_smtp': None,
            'email_from': None,
            'email_to': [],
            'deduplication_window': 300,  # 5 分钟
        }
    
    def _init_alert_rules(self) -> Dict:
        """初始化告警规则"""
        return {
            'high_error_rate': {
                'metric': 'error_count',
                'threshold': 10,
                'operator': '>',
                'severity': 'critical',
                'message_template': 'High error rate detected: {value} errors in last period',
                'auto_resolve': True,
                'resolve_threshold': 5,
            },
            'low_accuracy': {
                'metric': 'accuracy',
                'threshold': 80,
                'operator': '<',
                'severity': 'warning',
                'message_template': 'Low accuracy detected: {value}% (threshold: {threshold}%)',
                'auto_resolve': True,
                'resolve_threshold': 85,
            },
            'high_latency': {
                'metric': 'avg_latency',
                'threshold': 2.0,
                'operator': '>',
                'severity': 'warning',
                'message_template': 'High latency detected: {value}s (threshold: {threshold}s)',
                'auto_resolve': True,
                'resolve_threshold': 1.5,
            },
            'high_cpu': {
                'metric': 'cpu_usage',
                'threshold': 80,
                'operator': '>',
                'severity': 'warning',
                'message_template': 'High CPU usage: {value}% (threshold: {threshold}%)',
                'auto_resolve': True,
                'resolve_threshold': 70,
            },
            'high_memory': {
                'metric': 'memory_usage',
                'threshold': 85,
                'operator': '>',
                'severity': 'warning',
                'message_template': 'High memory usage: {value}% (threshold: {threshold}%)',
                'auto_resolve': True,
                'resolve_threshold': 75,
            },
            'low_cache_hit_rate': {
                'metric': 'cache_hit_rate',
                'threshold': 0.7,
                'operator': '<',
                'severity': 'info',
                'message_template': 'Low cache hit rate: {value}% (threshold: {threshold}%)',
                'auto_resolve': True,
                'resolve_threshold': 0.8,
            },
            'service_down': {
                'metric': 'request_count',
                'threshold': 0,
                'operator': '==',
                'severity': 'critical',
                'message_template': 'Service appears to be down: no requests in last period',
                'auto_resolve': True,
                'resolve_threshold': 1,
            },
        }
    
    def check_alerts(self, metrics: Dict) -> List[Dict]:
        """
        检查告警
        
        Args:
            metrics: 当前指标
        
        Returns:
            触发的告警列表
        """
        triggered_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            metric_value = metrics.get(rule['metric'])
            
            if metric_value is None:
                continue
            
            # 检查是否触发告警
            triggered = False
            if rule['operator'] == '>' and metric_value > rule['threshold']:
                triggered = True
            elif rule['operator'] == '<' and metric_value < rule['threshold']:
                triggered = True
            elif rule['operator'] == '==' and metric_value == rule['threshold']:
                triggered = True
            
            if triggered:
                # 检查是否需要去重
                if self._should_deduplicate(rule_name):
                    continue
                
                # 创建告警
                alert = {
                    'rule': rule_name,
                    'severity': rule['severity'],
                    'message': rule['message_template'].format(
                        value=metric_value,
                        threshold=rule['threshold']
                    ),
                    'metric_value': metric_value,
                    'threshold': rule['threshold'],
                    'timestamp': datetime.now().isoformat(),
                    'metrics': metrics,
                }
                
                triggered_alerts.append(alert)
                self.alerts.append(alert)
                self.recent_alerts[rule_name] = datetime.now()
                
                # 发送告警
                self._send_alert(alert)
        
        return triggered_alerts
    
    def _should_deduplicate(self, rule_name: str) -> bool:
        """
        检查是否需要去重
        
        Args:
            rule_name: 规则名称
        
        Returns:
            是否需要去重
        """
        if rule_name not in self.recent_alerts:
            return False
        
        last_alert_time = self.recent_alerts[rule_name]
        time_since_last = (datetime.now() - last_alert_time).total_seconds()
        
        return time_since_last < self.deduplication_window_seconds
    
    def _send_alert(self, alert: Dict):
        """
        发送告警
        
        Args:
            alert: 告警信息
        """
        # 记录到历史
        self.alert_history.append(alert)
        
        # 根据严重级别选择发送方式
        if alert['severity'] == 'critical':
            self._send_slack_alert(alert)
            self._send_email_alert(alert)
        elif alert['severity'] == 'warning':
            self._send_slack_alert(alert)
        else:  # info
            self._send_slack_alert(alert)
    
    def _send_slack_alert(self, alert: Dict):
        """
        发送 Slack 告警
        
        Args:
            alert: 告警信息
        """
        webhook = self.config.get('slack_webhook')
        
        if not webhook:
            print(f"[SLACK] {alert['severity'].upper()}: {alert['message']}")
            return
        
        try:
            import requests
            
            # 根据严重级别选择颜色
            color_map = {
                'critical': '#FF0000',
                'warning': '#FFA500',
                'info': '#00FF00',
            }
            
            payload = {
                'attachments': [{
                    'color': color_map.get(alert['severity'], '#808080'),
                    'title': f"AutoResearch Alert: {alert['rule']}",
                    'text': alert['message'],
                    'fields': [
                        {
                            'title': 'Severity',
                            'value': alert['severity'],
                            'short': True,
                        },
                        {
                            'title': 'Timestamp',
                            'value': alert['timestamp'],
                            'short': True,
                        },
                    ],
                    'footer': 'AutoResearch Monitoring',
                    'ts': int(datetime.now().timestamp()),
                }]
            }
            
            response = requests.post(webhook, json=payload)
            if response.status_code == 200:
                print(f"[SLACK] Alert sent: {alert['rule']}")
            else:
                print(f"[SLACK] Failed to send alert: {response.status_code}")
        
        except Exception as e:
            print(f"[SLACK] Error sending alert: {e}")
    
    def _send_email_alert(self, alert: Dict):
        """
        发送邮件告警
        
        Args:
            alert: 告警信息
        """
        smtp_config = self.config.get('email_smtp')
        
        if not smtp_config:
            print(f"[EMAIL] {alert['severity'].upper()}: {alert['message']}")
            return
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.config['email_from']
            msg['To'] = ', '.join(self.config['email_to'])
            msg['Subject'] = f"[AutoResearch Alert] {alert['rule']} - {alert['severity']}"
            
            body = f"""
Alert: {alert['rule']}
Severity: {alert['severity']}
Message: {alert['message']}
Timestamp: {alert['timestamp']}

Metric Value: {alert['metric_value']}
Threshold: {alert['threshold']}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            print(f"[EMAIL] Alert sent: {alert['rule']}")
        
        except Exception as e:
            print(f"[EMAIL] Error sending alert: {e}")
    
    def get_active_alerts(self) -> List[Dict]:
        """
        获取活跃告警
        
        Returns:
            活跃告警列表
        """
        return self.alerts
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """
        获取告警历史
        
        Args:
            limit: 返回条数限制
        
        Returns:
            告警历史列表
        """
        return self.alert_history[-limit:]
    
    def clear_alerts(self):
        """清除活跃告警"""
        self.alerts = []
        print("Active alerts cleared")
    
    def add_alert_rule(self, name: str, rule: Dict):
        """
        添加告警规则
        
        Args:
            name: 规则名称
            rule: 规则配置
        """
        self.alert_rules[name] = rule
        print(f"Added alert rule: {name}")
    
    def remove_alert_rule(self, name: str):
        """
        移除告警规则
        
        Args:
            name: 规则名称
        """
        if name in self.alert_rules:
            del self.alert_rules[name]
            print(f"Removed alert rule: {name}")
    
    def get_alert_statistics(self) -> Dict:
        """
        获取告警统计
        
        Returns:
            告警统计信息
        """
        if not self.alert_history:
            return {
                'total_alerts': 0,
                'alerts_by_severity': {},
                'alerts_by_rule': {},
            }
        
        severity_counts = {}
        rule_counts = {}
        
        for alert in self.alert_history:
            severity = alert['severity']
            rule = alert['rule']
            
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
        
        return {
            'total_alerts': len(self.alert_history),
            'alerts_by_severity': severity_counts,
            'alerts_by_rule': rule_counts,
            'most_frequent_rule': max(rule_counts.items(), key=lambda x: x[1]) if rule_counts else None,
        }


# 测试代码
if __name__ == "__main__":
    # 创建告警系统
    alerting = AlertingSystem()
    
    # 测试场景 1: 高错误率
    print("\n=== Test 1: High Error Rate ===")
    metrics1 = {
        'error_count': 15,  # 超过阈值 10
        'accuracy': 85,
        'avg_latency': 1.5,
        'cpu_usage': 50,
    }
    alerts1 = alerting.check_alerts(metrics1)
    print(f"Triggered alerts: {len(alerts1)}")
    for alert in alerts1:
        print(f"  - {alert['rule']}: {alert['message']}")
    
    # 测试场景 2: 低准确率
    print("\n=== Test 2: Low Accuracy ===")
    metrics2 = {
        'error_count': 5,
        'accuracy': 75,  # 低于阈值 80
        'avg_latency': 1.5,
        'cpu_usage': 50,
    }
    alerts2 = alerting.check_alerts(metrics2)
    print(f"Triggered alerts: {len(alerts2)}")
    for alert in alerts2:
        print(f"  - {alert['rule']}: {alert['message']}")
    
    # 测试场景 3: 多个告警
    print("\n=== Test 3: Multiple Alerts ===")
    metrics3 = {
        'error_count': 20,  # 高错误率
        'accuracy': 75,     # 低准确率
        'avg_latency': 3.0, # 高延迟
        'cpu_usage': 90,    # 高 CPU
    }
    alerts3 = alerting.check_alerts(metrics3)
    print(f"Triggered alerts: {len(alerts3)}")
    for alert in alerts3:
        print(f"  - {alert['rule']} ({alert['severity']}): {alert['message']}")
    
    # 获取告警统计
    print("\n=== Alert Statistics ===")
    stats = alerting.get_alert_statistics()
    print(f"Total alerts: {stats['total_alerts']}")
    print(f"By severity: {stats['alerts_by_severity']}")
    print(f"By rule: {stats['alerts_by_rule']}")
    print(f"Most frequent: {stats['most_frequent_rule']}")
