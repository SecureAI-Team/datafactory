"""
质量监控仪表盘
核心指标跟踪、告警和健康检查
"""
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """指标类型"""
    COUNTER = "counter"      # 计数器
    GAUGE = "gauge"          # 仪表盘
    HISTOGRAM = "histogram"  # 直方图
    RATE = "rate"            # 速率


@dataclass
class MetricPoint:
    """指标数据点"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """告警"""
    alert_id: str
    level: AlertLevel
    metric_name: str
    message: str
    current_value: float
    threshold: float
    triggered_at: float
    resolved: bool = False
    resolved_at: Optional[float] = None


@dataclass
class HealthStatus:
    """健康状态"""
    healthy: bool
    score: float  # 0-100
    components: Dict[str, Dict] = field(default_factory=dict)
    active_alerts: List[Alert] = field(default_factory=list)
    last_check: float = field(default_factory=time.time)


class QualityMonitor:
    """质量监控器"""
    
    def __init__(self, max_history: int = 1000):
        # 指标存储
        self._metrics: Dict[str, deque] = {}
        self._max_history = max_history
        
        # 告警
        self._alerts: List[Alert] = []
        self._alert_rules: Dict[str, Dict] = {}
        
        # 告警回调
        self._alert_callbacks: List[Callable] = []
        
        # 初始化默认指标
        self._init_default_metrics()
        self._init_default_alert_rules()
    
    def _init_default_metrics(self):
        """初始化默认指标"""
        default_metrics = [
            "conversation_count",       # 对话总数
            "message_count",            # 消息总数
            "feedback_positive_rate",   # 正面反馈率
            "feedback_average_rating",  # 平均评分
            "response_latency_ms",      # 响应延迟
            "retrieval_hit_rate",       # 检索命中率
            "calculation_success_rate", # 计算成功率
            "clarification_rate",       # 澄清率
            "error_rate",               # 错误率
        ]
        
        for metric in default_metrics:
            self._metrics[metric] = deque(maxlen=self._max_history)
    
    def _init_default_alert_rules(self):
        """初始化默认告警规则"""
        self._alert_rules = {
            "low_positive_rate": {
                "metric": "feedback_positive_rate",
                "condition": "lt",  # less than
                "threshold": 0.5,
                "window_minutes": 60,
                "level": AlertLevel.WARNING,
                "message": "过去1小时正面反馈率低于50%",
            },
            "critical_positive_rate": {
                "metric": "feedback_positive_rate",
                "condition": "lt",
                "threshold": 0.3,
                "window_minutes": 30,
                "level": AlertLevel.CRITICAL,
                "message": "过去30分钟正面反馈率低于30%",
            },
            "high_error_rate": {
                "metric": "error_rate",
                "condition": "gt",  # greater than
                "threshold": 0.1,
                "window_minutes": 15,
                "level": AlertLevel.CRITICAL,
                "message": "过去15分钟错误率超过10%",
            },
            "slow_response": {
                "metric": "response_latency_ms",
                "condition": "gt",
                "threshold": 5000,
                "window_minutes": 10,
                "level": AlertLevel.WARNING,
                "message": "过去10分钟平均响应时间超过5秒",
            },
            "low_rating": {
                "metric": "feedback_average_rating",
                "condition": "lt",
                "threshold": 3.0,
                "window_minutes": 60,
                "level": AlertLevel.WARNING,
                "message": "过去1小时平均评分低于3分",
            },
        }
    
    def record_metric(
        self,
        name: str,
        value: float,
        labels: Dict[str, str] = None,
    ):
        """记录指标"""
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._max_history)
        
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
        )
        
        self._metrics[name].append(point)
        
        # 检查告警
        self._check_alerts(name)
    
    def get_metric(
        self,
        name: str,
        window_minutes: int = None,
    ) -> List[MetricPoint]:
        """获取指标数据"""
        if name not in self._metrics:
            return []
        
        points = list(self._metrics[name])
        
        if window_minutes:
            cutoff = time.time() - window_minutes * 60
            points = [p for p in points if p.timestamp >= cutoff]
        
        return points
    
    def get_metric_stats(
        self,
        name: str,
        window_minutes: int = 60,
    ) -> Dict[str, float]:
        """获取指标统计"""
        points = self.get_metric(name, window_minutes)
        
        if not points:
            return {
                "count": 0,
                "avg": 0,
                "min": 0,
                "max": 0,
                "latest": 0,
            }
        
        values = [p.value for p in points]
        
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "latest": values[-1],
        }
    
    def _check_alerts(self, metric_name: str):
        """检查告警规则"""
        for rule_name, rule in self._alert_rules.items():
            if rule["metric"] != metric_name:
                continue
            
            stats = self.get_metric_stats(
                metric_name,
                rule.get("window_minutes", 60),
            )
            
            if stats["count"] < 3:  # 数据不足不触发
                continue
            
            value = stats["avg"]
            threshold = rule["threshold"]
            triggered = False
            
            if rule["condition"] == "lt" and value < threshold:
                triggered = True
            elif rule["condition"] == "gt" and value > threshold:
                triggered = True
            elif rule["condition"] == "eq" and value == threshold:
                triggered = True
            
            if triggered:
                self._trigger_alert(rule_name, rule, value)
            else:
                self._resolve_alert(rule_name)
    
    def _trigger_alert(
        self,
        rule_name: str,
        rule: Dict,
        current_value: float,
    ):
        """触发告警"""
        # 检查是否已存在未解决的告警
        existing = next(
            (a for a in self._alerts if a.alert_id == rule_name and not a.resolved),
            None,
        )
        
        if existing:
            return  # 已存在未解决告警
        
        alert = Alert(
            alert_id=rule_name,
            level=rule["level"],
            metric_name=rule["metric"],
            message=rule["message"],
            current_value=current_value,
            threshold=rule["threshold"],
            triggered_at=time.time(),
        )
        
        self._alerts.append(alert)
        
        logger.warning(f"Alert triggered: {rule_name} - {rule['message']}")
        
        # 调用回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def _resolve_alert(self, rule_name: str):
        """解决告警"""
        for alert in self._alerts:
            if alert.alert_id == rule_name and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                logger.info(f"Alert resolved: {rule_name}")
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活动告警"""
        return [a for a in self._alerts if not a.resolved]
    
    def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        components = {}
        score = 100.0
        
        # 1. 检查反馈指标
        feedback_stats = self.get_metric_stats("feedback_positive_rate", 60)
        if feedback_stats["count"] > 0:
            components["feedback"] = {
                "status": "healthy" if feedback_stats["avg"] > 0.5 else "degraded",
                "positive_rate": feedback_stats["avg"],
                "sample_count": feedback_stats["count"],
            }
            if feedback_stats["avg"] < 0.5:
                score -= 20
        else:
            components["feedback"] = {"status": "unknown", "message": "无反馈数据"}
        
        # 2. 检查响应延迟
        latency_stats = self.get_metric_stats("response_latency_ms", 15)
        if latency_stats["count"] > 0:
            components["latency"] = {
                "status": "healthy" if latency_stats["avg"] < 3000 else "degraded",
                "avg_ms": latency_stats["avg"],
                "max_ms": latency_stats["max"],
            }
            if latency_stats["avg"] > 3000:
                score -= 15
        else:
            components["latency"] = {"status": "unknown", "message": "无延迟数据"}
        
        # 3. 检查错误率
        error_stats = self.get_metric_stats("error_rate", 15)
        if error_stats["count"] > 0:
            components["errors"] = {
                "status": "healthy" if error_stats["avg"] < 0.05 else "degraded",
                "error_rate": error_stats["avg"],
            }
            if error_stats["avg"] > 0.05:
                score -= 25
        else:
            components["errors"] = {"status": "unknown", "message": "无错误数据"}
        
        # 4. 活动告警
        active_alerts = self.get_active_alerts()
        for alert in active_alerts:
            if alert.level == AlertLevel.CRITICAL:
                score -= 20
            elif alert.level == AlertLevel.WARNING:
                score -= 10
        
        return HealthStatus(
            healthy=score >= 70 and not any(a.level == AlertLevel.CRITICAL for a in active_alerts),
            score=max(0, score),
            components=components,
            active_alerts=active_alerts,
        )
    
    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def add_alert_rule(
        self,
        name: str,
        metric: str,
        condition: str,
        threshold: float,
        level: AlertLevel = AlertLevel.WARNING,
        window_minutes: int = 60,
        message: str = "",
    ):
        """添加告警规则"""
        self._alert_rules[name] = {
            "metric": metric,
            "condition": condition,
            "threshold": threshold,
            "level": level,
            "window_minutes": window_minutes,
            "message": message or f"{metric} {condition} {threshold}",
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        health = self.get_health_status()
        
        return {
            "health": {
                "healthy": health.healthy,
                "score": health.score,
                "last_check": datetime.fromtimestamp(health.last_check).isoformat(),
            },
            "components": health.components,
            "alerts": {
                "active_count": len(health.active_alerts),
                "alerts": [
                    {
                        "id": a.alert_id,
                        "level": a.level.value,
                        "message": a.message,
                        "triggered_at": datetime.fromtimestamp(a.triggered_at).isoformat(),
                    }
                    for a in health.active_alerts
                ],
            },
            "metrics": {
                "positive_rate": self.get_metric_stats("feedback_positive_rate", 60),
                "avg_rating": self.get_metric_stats("feedback_average_rating", 60),
                "latency": self.get_metric_stats("response_latency_ms", 15),
                "error_rate": self.get_metric_stats("error_rate", 15),
                "conversation_count": self.get_metric_stats("conversation_count", 60),
            },
        }
    
    def record_conversation_metrics(
        self,
        latency_ms: float,
        has_error: bool = False,
        feedback_positive: bool = None,
        feedback_rating: float = None,
        intent_type: str = None,
        scenario_id: str = None,
    ):
        """记录对话相关指标（便捷方法）"""
        labels = {}
        if intent_type:
            labels["intent"] = intent_type
        if scenario_id:
            labels["scenario"] = scenario_id
        
        # 对话计数
        self.record_metric("conversation_count", 1, labels)
        
        # 延迟
        self.record_metric("response_latency_ms", latency_ms, labels)
        
        # 错误率
        self.record_metric("error_rate", 1.0 if has_error else 0.0, labels)
        
        # 反馈
        if feedback_positive is not None:
            self.record_metric(
                "feedback_positive_rate",
                1.0 if feedback_positive else 0.0,
                labels,
            )
        
        if feedback_rating is not None:
            self.record_metric("feedback_average_rating", feedback_rating, labels)


# ==================== 模块级便捷函数 ====================

_default_monitor: Optional[QualityMonitor] = None


def get_quality_monitor() -> QualityMonitor:
    """获取质量监控器实例"""
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = QualityMonitor()
    return _default_monitor


def record_metric(name: str, value: float, labels: Dict[str, str] = None):
    """便捷函数：记录指标"""
    get_quality_monitor().record_metric(name, value, labels)


def get_health_status() -> HealthStatus:
    """便捷函数：获取健康状态"""
    return get_quality_monitor().get_health_status()


def get_dashboard_data() -> Dict[str, Any]:
    """便捷函数：获取仪表盘数据"""
    return get_quality_monitor().get_dashboard_data()

