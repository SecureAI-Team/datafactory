"""
反馈分析器
分析用户反馈，生成报表，识别问题模式
"""
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class AnalysisPeriod(str, Enum):
    """分析周期"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class FeedbackPattern:
    """反馈模式"""
    pattern_type: str              # negative_cluster/positive_trend/anomaly
    description: str
    affected_intents: List[str] = field(default_factory=list)
    affected_scenarios: List[str] = field(default_factory=list)
    sample_queries: List[str] = field(default_factory=list)
    frequency: int = 0
    severity: str = "low"          # low/medium/high/critical
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """分析报告"""
    period: str
    start_time: float
    end_time: float
    
    # 基础统计
    total_conversations: int = 0
    total_messages: int = 0
    total_feedback: int = 0
    positive_rate: float = 0.0
    average_rating: float = 0.0
    
    # 按维度统计
    by_intent: Dict[str, Dict] = field(default_factory=dict)
    by_scenario: Dict[str, Dict] = field(default_factory=dict)
    by_hour: Dict[int, Dict] = field(default_factory=dict)
    
    # 识别的模式
    patterns: List[FeedbackPattern] = field(default_factory=list)
    
    # 建议
    recommendations: List[str] = field(default_factory=list)
    
    # 健康评分
    health_score: float = 0.0


class FeedbackAnalyzer:
    """反馈分析器"""
    
    def __init__(self, feedback_optimizer=None):
        """
        Args:
            feedback_optimizer: FeedbackOptimizer 实例
        """
        self._optimizer = feedback_optimizer
    
    @property
    def optimizer(self):
        if self._optimizer is None:
            from .feedback_optimizer import get_feedback_optimizer
            self._optimizer = get_feedback_optimizer()
        return self._optimizer
    
    def analyze(
        self,
        period: AnalysisPeriod = AnalysisPeriod.DAILY,
        days: int = 7,
        intent_filter: str = None,
        scenario_filter: str = None,
    ) -> AnalysisReport:
        """
        执行反馈分析
        
        Args:
            period: 分析周期
            days: 分析天数
            intent_filter: 意图过滤
            scenario_filter: 场景过滤
        
        Returns:
            AnalysisReport
        """
        end_time = time.time()
        start_time = end_time - days * 86400
        
        # 获取反馈数据
        records = self.optimizer._feedback_records
        
        # 过滤
        filtered = [
            r for r in records
            if r.created_at >= start_time
            and (intent_filter is None or r.intent_type == intent_filter)
            and (scenario_filter is None or r.scenario_id == scenario_filter)
        ]
        
        if not filtered:
            return AnalysisReport(
                period=period.value,
                start_time=start_time,
                end_time=end_time,
                recommendations=["数据不足，无法生成分析报告"],
            )
        
        # 基础统计
        report = AnalysisReport(
            period=period.value,
            start_time=start_time,
            end_time=end_time,
            total_feedback=len(filtered),
        )
        
        # 计算正面率
        from .feedback_optimizer import FeedbackType
        positive = sum(
            1 for r in filtered
            if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE)
        )
        report.positive_rate = positive / len(filtered) if filtered else 0
        
        # 计算平均评分
        ratings = [r.rating for r in filtered if r.rating is not None]
        report.average_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # 按意图统计
        report.by_intent = self._analyze_by_dimension(filtered, "intent_type")
        
        # 按场景统计
        report.by_scenario = self._analyze_by_dimension(filtered, "scenario_id")
        
        # 按小时统计
        report.by_hour = self._analyze_by_hour(filtered)
        
        # 识别模式
        report.patterns = self._detect_patterns(filtered)
        
        # 生成建议
        report.recommendations = self._generate_recommendations(report)
        
        # 计算健康评分
        report.health_score = self._calculate_health_score(report)
        
        return report
    
    def _analyze_by_dimension(
        self,
        records: List,
        dimension: str,
    ) -> Dict[str, Dict]:
        """按维度分析"""
        from .feedback_optimizer import FeedbackType
        
        result = defaultdict(lambda: {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "ratings": [],
        })
        
        for r in records:
            key = getattr(r, dimension, None) or "unknown"
            result[key]["total"] += 1
            
            if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE):
                result[key]["positive"] += 1
            elif r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE):
                result[key]["negative"] += 1
            
            if r.rating is not None:
                result[key]["ratings"].append(r.rating)
        
        # 计算汇总指标
        for key, data in result.items():
            data["positive_rate"] = data["positive"] / data["total"] if data["total"] > 0 else 0
            data["avg_rating"] = sum(data["ratings"]) / len(data["ratings"]) if data["ratings"] else 0
            del data["ratings"]  # 不在报告中保留原始列表
        
        return dict(result)
    
    def _analyze_by_hour(self, records: List) -> Dict[int, Dict]:
        """按小时分析"""
        from .feedback_optimizer import FeedbackType
        
        result = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0})
        
        for r in records:
            hour = datetime.fromtimestamp(r.created_at).hour
            result[hour]["total"] += 1
            
            if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE):
                result[hour]["positive"] += 1
            elif r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE):
                result[hour]["negative"] += 1
        
        return dict(result)
    
    def _detect_patterns(self, records: List) -> List[FeedbackPattern]:
        """检测反馈模式"""
        from .feedback_optimizer import FeedbackType
        
        patterns = []
        
        # 1. 检测负面反馈聚集
        negative_by_intent = defaultdict(list)
        for r in records:
            if r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE):
                if r.intent_type:
                    negative_by_intent[r.intent_type].append(r)
        
        for intent_type, neg_records in negative_by_intent.items():
            total_for_intent = sum(1 for r in records if r.intent_type == intent_type)
            negative_rate = len(neg_records) / total_for_intent if total_for_intent > 0 else 0
            
            if negative_rate > 0.3 and len(neg_records) >= 3:
                patterns.append(FeedbackPattern(
                    pattern_type="negative_cluster",
                    description=f"意图 '{intent_type}' 的负面反馈率较高 ({negative_rate:.0%})",
                    affected_intents=[intent_type],
                    sample_queries=[r.query[:50] for r in neg_records[:3]],
                    frequency=len(neg_records),
                    severity="high" if negative_rate > 0.5 else "medium",
                    suggested_actions=[
                        f"检查 {intent_type} 意图的 Prompt 模板",
                        "添加更多 Few-shot 示例",
                        "调整检索策略",
                    ],
                ))
        
        # 2. 检测追问模式（可能表示回答不完整）
        follow_up_count = sum(
            1 for r in records
            if r.feedback_type == FeedbackType.FOLLOW_UP
        )
        if follow_up_count > len(records) * 0.2:
            patterns.append(FeedbackPattern(
                pattern_type="incomplete_answers",
                description=f"追问率较高 ({follow_up_count}/{len(records)})",
                frequency=follow_up_count,
                severity="medium",
                suggested_actions=[
                    "增加回答的详细程度",
                    "主动提供相关扩展信息",
                    "检查是否遗漏关键要点",
                ],
            ))
        
        # 3. 检测时段异常
        by_hour = self._analyze_by_hour(records)
        for hour, data in by_hour.items():
            if data["total"] >= 5:
                neg_rate = data["negative"] / data["total"]
                if neg_rate > 0.4:
                    patterns.append(FeedbackPattern(
                        pattern_type="time_anomaly",
                        description=f"{hour}:00 时段负面反馈率异常 ({neg_rate:.0%})",
                        frequency=data["total"],
                        severity="low",
                        suggested_actions=["检查该时段的服务状态", "分析是否与特定用户群相关"],
                    ))
        
        return patterns
    
    def _generate_recommendations(self, report: AnalysisReport) -> List[str]:
        """生成建议"""
        recommendations = []
        
        # 基于正面率
        if report.positive_rate < 0.5:
            recommendations.append("⚠️ 整体满意度较低，建议：")
            recommendations.append("  - 检查最近的 Prompt 变更")
            recommendations.append("  - 分析高负面反馈的意图类型")
            recommendations.append("  - 增加人工审核抽检")
        elif report.positive_rate > 0.8:
            recommendations.append("✅ 整体满意度良好，建议：")
            recommendations.append("  - 提取高评分回答作为 Few-shot 示例")
            recommendations.append("  - 保持当前策略")
        
        # 基于模式
        high_severity = [p for p in report.patterns if p.severity in ("high", "critical")]
        if high_severity:
            recommendations.append("🚨 发现高优先级问题：")
            for p in high_severity[:3]:
                recommendations.append(f"  - {p.description}")
                for action in p.suggested_actions[:2]:
                    recommendations.append(f"    → {action}")
        
        # 基于意图分布
        if report.by_intent:
            worst_intent = min(
                report.by_intent.items(),
                key=lambda x: x[1].get("positive_rate", 1)
            )
            if worst_intent[1].get("positive_rate", 1) < 0.5:
                recommendations.append(f"📉 意图 '{worst_intent[0]}' 表现较差，需重点优化")
        
        if not recommendations:
            recommendations.append("暂无特别建议，系统运行正常")
        
        return recommendations
    
    def _calculate_health_score(self, report: AnalysisReport) -> float:
        """计算健康评分 (0-100)"""
        score = 50.0  # 基础分
        
        # 正面率贡献 (max 30)
        score += report.positive_rate * 30
        
        # 评分贡献 (max 20)
        if report.average_rating > 0:
            score += (report.average_rating / 5) * 20
        
        # 模式惩罚
        for pattern in report.patterns:
            if pattern.severity == "critical":
                score -= 15
            elif pattern.severity == "high":
                score -= 10
            elif pattern.severity == "medium":
                score -= 5
        
        return max(0, min(100, score))
    
    def get_trend(
        self,
        metric: str = "positive_rate",
        days: int = 7,
    ) -> List[Dict]:
        """
        获取指标趋势
        
        Args:
            metric: 指标名称 (positive_rate/avg_rating/total)
            days: 天数
        
        Returns:
            每日数据列表
        """
        from .feedback_optimizer import FeedbackType
        
        end_time = time.time()
        result = []
        
        for i in range(days):
            day_end = end_time - i * 86400
            day_start = day_end - 86400
            
            records = [
                r for r in self.optimizer._feedback_records
                if day_start <= r.created_at < day_end
            ]
            
            if not records:
                result.append({
                    "date": datetime.fromtimestamp(day_start).strftime("%Y-%m-%d"),
                    "value": None,
                })
                continue
            
            if metric == "positive_rate":
                positive = sum(
                    1 for r in records
                    if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE)
                )
                value = positive / len(records)
            elif metric == "avg_rating":
                ratings = [r.rating for r in records if r.rating is not None]
                value = sum(ratings) / len(ratings) if ratings else 0
            elif metric == "total":
                value = len(records)
            else:
                value = 0
            
            result.append({
                "date": datetime.fromtimestamp(day_start).strftime("%Y-%m-%d"),
                "value": value,
            })
        
        return list(reversed(result))
    
    def generate_report_text(self, report: AnalysisReport) -> str:
        """生成文本报告"""
        lines = [
            f"# 反馈分析报告",
            f"",
            f"**分析周期**: {report.period}",
            f"**时间范围**: {datetime.fromtimestamp(report.start_time).strftime('%Y-%m-%d %H:%M')} ~ {datetime.fromtimestamp(report.end_time).strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## 概要",
            f"",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 反馈总数 | {report.total_feedback} |",
            f"| 正面率 | {report.positive_rate:.1%} |",
            f"| 平均评分 | {report.average_rating:.2f}/5 |",
            f"| 健康评分 | {report.health_score:.0f}/100 |",
            f"",
        ]
        
        if report.by_intent:
            lines.extend([
                f"## 按意图统计",
                f"",
                f"| 意图 | 总数 | 正面率 | 平均评分 |",
                f"|------|------|--------|----------|",
            ])
            for intent, data in sorted(report.by_intent.items(), key=lambda x: -x[1]["total"]):
                lines.append(
                    f"| {intent} | {data['total']} | {data['positive_rate']:.1%} | {data['avg_rating']:.2f} |"
                )
            lines.append("")
        
        if report.patterns:
            lines.extend([
                f"## 识别的模式",
                f"",
            ])
            for p in report.patterns:
                lines.append(f"### {p.pattern_type}: {p.description}")
                lines.append(f"- 严重程度: {p.severity}")
                lines.append(f"- 频次: {p.frequency}")
                if p.suggested_actions:
                    lines.append(f"- 建议: {'; '.join(p.suggested_actions[:2])}")
                lines.append("")
        
        if report.recommendations:
            lines.extend([
                f"## 建议",
                f"",
            ])
            for rec in report.recommendations:
                lines.append(rec)
            lines.append("")
        
        return "\n".join(lines)


# ==================== 模块级便捷函数 ====================

_default_analyzer: Optional[FeedbackAnalyzer] = None


def get_feedback_analyzer() -> FeedbackAnalyzer:
    """获取反馈分析器实例"""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = FeedbackAnalyzer()
    return _default_analyzer


def analyze_feedback(
    period: AnalysisPeriod = AnalysisPeriod.DAILY,
    days: int = 7,
) -> AnalysisReport:
    """便捷函数：执行反馈分析"""
    return get_feedback_analyzer().analyze(period, days)


def get_feedback_trend(metric: str = "positive_rate", days: int = 7) -> List[Dict]:
    """便捷函数：获取指标趋势"""
    return get_feedback_analyzer().get_trend(metric, days)

