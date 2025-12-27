"""
反馈收集与优化
收集用户反馈，分析模式，优化 Prompt
"""
import time
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """反馈类型"""
    EXPLICIT_POSITIVE = "explicit_positive"    # 明确正面（点击满意）
    EXPLICIT_NEGATIVE = "explicit_negative"    # 明确负面（点击不满意）
    NATURAL_POSITIVE = "natural_positive"      # 自然语言正面
    NATURAL_NEGATIVE = "natural_negative"      # 自然语言负面
    FOLLOW_UP = "follow_up"                    # 追问（隐式不满意）
    CLARIFICATION_SUCCESS = "clarif_success"  # 澄清成功
    CLARIFICATION_FAIL = "clarif_fail"        # 澄清失败


class FeedbackDimension(str, Enum):
    """反馈维度"""
    RELEVANCE = "relevance"           # 相关性
    ACCURACY = "accuracy"             # 准确性
    COMPLETENESS = "completeness"     # 完整性
    CLARITY = "clarity"               # 清晰度
    ACTIONABILITY = "actionability"   # 可操作性


@dataclass
class FeedbackRecord:
    """反馈记录"""
    feedback_id: str
    conversation_id: str
    message_id: Optional[str]
    
    feedback_type: FeedbackType
    dimension: Optional[FeedbackDimension] = None
    rating: Optional[int] = None      # 1-5 评分
    text: Optional[str] = None        # 文本反馈
    
    # 上下文信息
    query: str = ""
    response_preview: str = ""
    intent_type: Optional[str] = None
    scenario_id: Optional[str] = None
    
    # 元数据
    created_at: float = field(default_factory=time.time)
    processed: bool = False


@dataclass
class FeedbackStats:
    """反馈统计"""
    total_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    average_rating: float = 0.0
    
    by_intent: Dict[str, Dict] = field(default_factory=dict)
    by_scenario: Dict[str, Dict] = field(default_factory=dict)
    
    common_issues: List[Dict] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


@dataclass
class PromptOptimization:
    """Prompt 优化建议"""
    target: str                       # 优化目标（intent/scenario/general）
    target_id: Optional[str] = None   # 目标 ID
    
    original_prompt: str = ""
    suggested_prompt: str = ""
    
    few_shot_examples: List[Dict] = field(default_factory=list)
    negative_examples: List[Dict] = field(default_factory=list)
    
    reasoning: str = ""
    confidence: float = 0.5


class FeedbackOptimizer:
    """反馈优化器"""
    
    def __init__(self, storage_backend: str = "memory"):
        self.storage_backend = storage_backend
        
        # 内存存储
        self._feedback_records: List[FeedbackRecord] = []
        self._optimization_cache: Dict[str, PromptOptimization] = {}
        
        # 正面/负面关键词
        self.positive_keywords = [
            "有帮助", "很好", "不错", "满意", "谢谢", "感谢", "太棒了",
            "完美", "正是我需要的", "解决了", "清楚", "明白了",
            "学到了", "有用", "专业",
        ]
        self.negative_keywords = [
            "不满意", "没有帮助", "不对", "错了", "不准确", "有问题",
            "需要改进", "太简单", "不够详细", "没说清楚", "看不懂",
            "答非所问", "不相关", "废话", "没用",
        ]
        
        # 追问模式关键词
        self.follow_up_patterns = [
            "你没说", "再解释", "什么意思", "不明白", "能详细",
            "刚才说的", "上面提到的", "具体说说",
        ]
    
    def detect_natural_feedback(self, text: str) -> Optional[Tuple[FeedbackType, float]]:
        """检测自然语言反馈"""
        text_lower = text.lower()
        
        # 正面反馈
        positive_count = sum(1 for kw in self.positive_keywords if kw in text_lower)
        if positive_count > 0:
            confidence = min(positive_count * 0.3 + 0.4, 1.0)
            return FeedbackType.NATURAL_POSITIVE, confidence
        
        # 负面反馈
        negative_count = sum(1 for kw in self.negative_keywords if kw in text_lower)
        if negative_count > 0:
            confidence = min(negative_count * 0.3 + 0.4, 1.0)
            return FeedbackType.NATURAL_NEGATIVE, confidence
        
        # 追问检测
        follow_up_count = sum(1 for kw in self.follow_up_patterns if kw in text_lower)
        if follow_up_count > 0:
            return FeedbackType.FOLLOW_UP, 0.5
        
        return None
    
    def record_feedback(
        self,
        conversation_id: str,
        feedback_type: FeedbackType,
        query: str,
        response: str,
        message_id: str = None,
        rating: int = None,
        text: str = None,
        intent_type: str = None,
        scenario_id: str = None,
        dimension: FeedbackDimension = None,
    ) -> FeedbackRecord:
        """记录反馈"""
        import uuid
        
        record = FeedbackRecord(
            feedback_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            message_id=message_id,
            feedback_type=feedback_type,
            dimension=dimension,
            rating=rating,
            text=text,
            query=query,
            response_preview=response[:200] if response else "",
            intent_type=intent_type,
            scenario_id=scenario_id,
        )
        
        self._feedback_records.append(record)
        
        logger.info(
            f"Feedback recorded: {feedback_type.value}, "
            f"intent={intent_type}, scenario={scenario_id}"
        )
        
        # 触发实时分析
        self._analyze_recent_feedback()
        
        return record
    
    def get_stats(
        self,
        days: int = 7,
        intent_type: str = None,
        scenario_id: str = None,
    ) -> FeedbackStats:
        """获取反馈统计"""
        cutoff = time.time() - days * 86400
        
        # 过滤记录
        records = [
            r for r in self._feedback_records
            if r.created_at >= cutoff
            and (intent_type is None or r.intent_type == intent_type)
            and (scenario_id is None or r.scenario_id == scenario_id)
        ]
        
        if not records:
            return FeedbackStats()
        
        # 基础统计
        positive = sum(
            1 for r in records
            if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE)
        )
        negative = sum(
            1 for r in records
            if r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE, FeedbackType.FOLLOW_UP)
        )
        
        ratings = [r.rating for r in records if r.rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # 按意图统计
        by_intent = defaultdict(lambda: {"positive": 0, "negative": 0, "total": 0})
        for r in records:
            if r.intent_type:
                by_intent[r.intent_type]["total"] += 1
                if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE):
                    by_intent[r.intent_type]["positive"] += 1
                elif r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE):
                    by_intent[r.intent_type]["negative"] += 1
        
        # 按场景统计
        by_scenario = defaultdict(lambda: {"positive": 0, "negative": 0, "total": 0})
        for r in records:
            if r.scenario_id:
                by_scenario[r.scenario_id]["total"] += 1
                if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE):
                    by_scenario[r.scenario_id]["positive"] += 1
                elif r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE):
                    by_scenario[r.scenario_id]["negative"] += 1
        
        # 分析常见问题
        common_issues = self._analyze_common_issues(records)
        
        return FeedbackStats(
            total_count=len(records),
            positive_count=positive,
            negative_count=negative,
            average_rating=avg_rating,
            by_intent=dict(by_intent),
            by_scenario=dict(by_scenario),
            common_issues=common_issues,
        )
    
    def _analyze_common_issues(self, records: List[FeedbackRecord]) -> List[Dict]:
        """分析常见问题"""
        issues = []
        
        # 负面反馈文本分析
        negative_texts = [
            r.text for r in records
            if r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE)
            and r.text
        ]
        
        # 简单关键词统计
        issue_keywords = {
            "不相关": "检索结果与问题不相关",
            "不详细": "回答不够详细",
            "太复杂": "回答过于复杂",
            "不准确": "信息不准确",
            "没有答案": "未能回答问题",
        }
        
        for keyword, description in issue_keywords.items():
            count = sum(1 for t in negative_texts if keyword in t)
            if count > 0:
                issues.append({
                    "keyword": keyword,
                    "description": description,
                    "count": count,
                    "percentage": count / len(negative_texts) * 100 if negative_texts else 0,
                })
        
        return sorted(issues, key=lambda x: x["count"], reverse=True)
    
    def _analyze_recent_feedback(self):
        """分析最近反馈，触发优化"""
        recent = [
            r for r in self._feedback_records[-50:]
            if time.time() - r.created_at < 3600  # 最近1小时
        ]
        
        if len(recent) < 5:
            return
        
        # 检查负面反馈集中度
        by_intent = defaultdict(list)
        for r in recent:
            if r.intent_type and r.feedback_type in (
                FeedbackType.EXPLICIT_NEGATIVE,
                FeedbackType.NATURAL_NEGATIVE,
            ):
                by_intent[r.intent_type].append(r)
        
        # 如果某意图负面反馈过多，生成优化建议
        for intent_type, neg_records in by_intent.items():
            if len(neg_records) >= 3:
                self._generate_optimization(intent_type, neg_records)
    
    def _generate_optimization(
        self,
        intent_type: str,
        negative_records: List[FeedbackRecord],
    ):
        """生成优化建议"""
        optimization = PromptOptimization(
            target="intent",
            target_id=intent_type,
            reasoning=f"最近 {len(negative_records)} 条负面反馈集中在 {intent_type} 意图",
        )
        
        # 收集负面案例
        for r in negative_records[:5]:
            optimization.negative_examples.append({
                "query": r.query,
                "response": r.response_preview,
                "issue": r.text or "未明确",
            })
        
        # 生成改进建议
        if any("不详细" in (r.text or "") for r in negative_records):
            optimization.improvement_suggestions = [
                "增加回答的详细程度",
                "添加具体示例",
                "分步骤说明",
            ]
        
        if any("不相关" in (r.text or "") for r in negative_records):
            optimization.improvement_suggestions = [
                "优化检索关键词权重",
                "增强意图识别准确度",
                "缩小检索范围到更相关内容",
            ]
        
        self._optimization_cache[f"intent:{intent_type}"] = optimization
        
        logger.info(f"Generated optimization suggestion for intent: {intent_type}")
    
    def get_optimization(
        self,
        intent_type: str = None,
        scenario_id: str = None,
    ) -> Optional[PromptOptimization]:
        """获取优化建议"""
        if intent_type:
            return self._optimization_cache.get(f"intent:{intent_type}")
        if scenario_id:
            return self._optimization_cache.get(f"scenario:{scenario_id}")
        return None
    
    def get_few_shot_examples(
        self,
        intent_type: str,
        scenario_id: str = None,
        limit: int = 3,
    ) -> List[Dict]:
        """获取 Few-shot 示例（从正面反馈中提取）"""
        # 筛选正面反馈
        positive = [
            r for r in self._feedback_records
            if r.feedback_type in (FeedbackType.EXPLICIT_POSITIVE, FeedbackType.NATURAL_POSITIVE)
            and r.intent_type == intent_type
            and (scenario_id is None or r.scenario_id == scenario_id)
            and r.rating and r.rating >= 4
        ]
        
        # 按评分排序
        positive.sort(key=lambda x: x.rating or 0, reverse=True)
        
        examples = []
        for r in positive[:limit]:
            examples.append({
                "query": r.query,
                "response": r.response_preview,
                "rating": r.rating,
            })
        
        return examples
    
    def build_enhanced_prompt(
        self,
        base_prompt: str,
        intent_type: str,
        scenario_id: str = None,
    ) -> str:
        """构建增强的 Prompt（包含 Few-shot 示例）"""
        parts = [base_prompt]
        
        # 添加 Few-shot 示例
        examples = self.get_few_shot_examples(intent_type, scenario_id)
        if examples:
            examples_text = "\n\n【优秀回答示例】\n"
            for i, ex in enumerate(examples, 1):
                examples_text += f"\n示例{i}:\n问题：{ex['query']}\n回答：{ex['response']}\n"
            parts.append(examples_text)
        
        # 添加优化建议
        optimization = self.get_optimization(intent_type=intent_type)
        if optimization and optimization.improvement_suggestions:
            suggestions = "\n".join(f"- {s}" for s in optimization.improvement_suggestions)
            parts.append(f"\n\n【注意事项】\n{suggestions}")
        
        return "\n".join(parts)
    
    def export_feedback_data(self, days: int = 30) -> List[Dict]:
        """导出反馈数据"""
        cutoff = time.time() - days * 86400
        
        return [
            asdict(r)
            for r in self._feedback_records
            if r.created_at >= cutoff
        ]


# ==================== 模块级便捷函数 ====================

_default_optimizer: Optional[FeedbackOptimizer] = None


def get_feedback_optimizer() -> FeedbackOptimizer:
    """获取反馈优化器实例"""
    global _default_optimizer
    if _default_optimizer is None:
        _default_optimizer = FeedbackOptimizer()
    return _default_optimizer


def record_feedback(
    conversation_id: str,
    feedback_type: Any = None,  # 支持 FeedbackType 或字符串
    query: str = None,
    response: str = None,
    # 兼容 conversation.py 的参数名
    message_id: str = None,
    user_query: str = None,
    assistant_response: str = None,
    feedback_value: Any = None,
    correction_text: str = None,
    retrieved_sources: List = None,
    **kwargs,
) -> FeedbackRecord:
    """便捷函数：记录反馈（兼容多种调用方式）"""
    # 参数兼容处理
    actual_query = query or user_query or ""
    actual_response = response or assistant_response or ""
    
    # feedback_type 处理
    if isinstance(feedback_type, str):
        # 从字符串转换
        type_mapping = {
            "thumbs_up": FeedbackType.EXPLICIT_POSITIVE,
            "thumbs_down": FeedbackType.EXPLICIT_NEGATIVE,
            "rating": FeedbackType.EXPLICIT_POSITIVE if feedback_value and feedback_value >= 4 else FeedbackType.EXPLICIT_NEGATIVE,
            "correction": FeedbackType.EXPLICIT_NEGATIVE,
            "positive": FeedbackType.EXPLICIT_POSITIVE,
            "negative": FeedbackType.EXPLICIT_NEGATIVE,
        }
        actual_feedback_type = type_mapping.get(feedback_type, FeedbackType.EXPLICIT_POSITIVE)
    else:
        actual_feedback_type = feedback_type or FeedbackType.EXPLICIT_POSITIVE
    
    # 计算 rating
    rating = kwargs.get("rating")
    if rating is None and feedback_value is not None:
        if isinstance(feedback_value, bool):
            rating = 5 if feedback_value else 1
        elif isinstance(feedback_value, (int, float)):
            rating = int(feedback_value)
    
    return get_feedback_optimizer().record_feedback(
        conversation_id=conversation_id,
        feedback_type=actual_feedback_type,
        query=actual_query,
        response=actual_response,
        message_id=message_id,
        rating=rating,
        text=correction_text,
        **kwargs,
    )


def detect_and_record_natural_feedback(
    text: str,
    conversation_id: str,
    query: str,
    response: str,
    intent_type: str = None,
    scenario_id: str = None,
) -> Optional[FeedbackRecord]:
    """便捷函数：检测并记录自然语言反馈"""
    optimizer = get_feedback_optimizer()
    
    detection = optimizer.detect_natural_feedback(text)
    if detection:
        feedback_type, confidence = detection
        
        if confidence >= 0.4:
            return optimizer.record_feedback(
                conversation_id=conversation_id,
                feedback_type=feedback_type,
                query=query,
                response=response,
                intent_type=intent_type,
                scenario_id=scenario_id,
            )
    
    return None


# ==================== 兼容性别名 ====================

# 为 conversation.py 提供的别名
get_optimizer = get_feedback_optimizer


def get_feedback_stats(days: int = 7) -> Dict:
    """获取反馈统计（兼容接口）"""
    stats = get_feedback_optimizer().get_stats(days=days)
    return {
        "total_count": stats.total_count,
        "positive_count": stats.positive_count,
        "negative_count": stats.negative_count,
        "avg_rating": stats.average_rating,
        "by_intent": stats.by_intent,
        "by_scenario": stats.by_scenario,
        "common_issues": stats.common_issues,
    }
