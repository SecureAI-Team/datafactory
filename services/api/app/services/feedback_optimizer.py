"""
用户反馈收集和 Prompt 自动优化机制
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel
from collections import defaultdict

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """反馈类型"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"  # 1-5 分
    TEXT = "text"      # 文字反馈
    CORRECTION = "correction"  # 纠正答案


class FeedbackRecord(BaseModel):
    """反馈记录"""
    id: str
    conversation_id: str
    message_id: str
    user_query: str
    assistant_response: str
    feedback_type: FeedbackType
    feedback_value: Any  # 具体反馈值
    correction_text: Optional[str] = None  # 用户提供的正确答案
    retrieved_sources: List[str] = []  # 检索到的来源
    created_at: datetime = None
    
    def __init__(self, **data):
        if data.get('created_at') is None:
            data['created_at'] = datetime.utcnow()
        super().__init__(**data)
    
    @property
    def is_positive(self) -> bool:
        """是否为正面反馈"""
        if self.feedback_type == FeedbackType.THUMBS_UP:
            return True
        if self.feedback_type == FeedbackType.THUMBS_DOWN:
            return False
        if self.feedback_type == FeedbackType.RATING:
            return self.feedback_value >= 4
        return False
    
    @property
    def is_negative(self) -> bool:
        """是否为负面反馈"""
        if self.feedback_type == FeedbackType.THUMBS_DOWN:
            return True
        if self.feedback_type == FeedbackType.CORRECTION:
            return True
        if self.feedback_type == FeedbackType.RATING:
            return self.feedback_value <= 2
        return False


class PromptOptimizer:
    """
    基于反馈的 Prompt 优化器
    
    策略：
    1. 收集负面反馈案例
    2. 聚类相似问题
    3. 生成 Few-shot 示例
    4. 动态调整 System Prompt
    """
    
    def __init__(self):
        self.feedback_records: List[FeedbackRecord] = []
        self.negative_examples: List[Dict] = []  # 负面案例库
        self.positive_examples: List[Dict] = []  # 正面案例库
        self.optimized_prompts: Dict[str, str] = {}  # 场景 -> 优化后的 Prompt
        self.last_optimization: Optional[datetime] = None
    
    def add_feedback(self, feedback: FeedbackRecord):
        """添加反馈记录"""
        self.feedback_records.append(feedback)
        
        if feedback.is_negative:
            self.negative_examples.append({
                "query": feedback.user_query,
                "bad_response": feedback.assistant_response,
                "correction": feedback.correction_text,
                "sources": feedback.retrieved_sources,
                "timestamp": feedback.created_at.isoformat(),
            })
            logger.info(f"Added negative feedback: {feedback.user_query[:50]}...")
        
        elif feedback.is_positive:
            self.positive_examples.append({
                "query": feedback.user_query,
                "good_response": feedback.assistant_response,
                "sources": feedback.retrieved_sources,
                "timestamp": feedback.created_at.isoformat(),
            })
            logger.info(f"Added positive feedback: {feedback.user_query[:50]}...")
        
        # 每积累 10 条负面反馈，触发优化
        if len(self.negative_examples) % 10 == 0 and len(self.negative_examples) > 0:
            self.trigger_optimization()
    
    def get_feedback_stats(self) -> Dict:
        """获取反馈统计"""
        total = len(self.feedback_records)
        if total == 0:
            return {"total": 0, "positive_rate": 0, "negative_rate": 0}
        
        positive = sum(1 for f in self.feedback_records if f.is_positive)
        negative = sum(1 for f in self.feedback_records if f.is_negative)
        
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "positive_rate": positive / total,
            "negative_rate": negative / total,
            "last_optimization": self.last_optimization.isoformat() if self.last_optimization else None,
        }
    
    def get_few_shot_examples(self, query: str, max_examples: int = 3) -> List[Dict]:
        """
        获取与查询相关的 Few-shot 示例
        优先使用有纠正的负面案例
        """
        examples = []
        
        # 首先添加有纠正的案例（最有价值）
        corrected = [e for e in self.negative_examples if e.get("correction")]
        for ex in corrected[-max_examples:]:
            examples.append({
                "user": ex["query"],
                "assistant": ex["correction"],
                "note": "corrected_example"
            })
        
        # 补充正面案例
        remaining = max_examples - len(examples)
        if remaining > 0:
            for ex in self.positive_examples[-remaining:]:
                examples.append({
                    "user": ex["query"],
                    "assistant": ex["good_response"][:500],  # 截断
                    "note": "positive_example"
                })
        
        return examples
    
    def get_optimization_hints(self) -> str:
        """
        根据反馈分析生成优化提示
        """
        if not self.negative_examples:
            return ""
        
        # 分析常见问题模式
        issues = []
        
        # 检查是否有来源引用问题
        no_source_issues = sum(1 for e in self.negative_examples if not e.get("sources"))
        if no_source_issues > 3:
            issues.append("- 确保在回答中明确引用知识库来源")
        
        # 检查是否有答案不完整问题
        short_responses = sum(1 for e in self.negative_examples 
                             if len(e.get("bad_response", "")) < 100)
        if short_responses > 3:
            issues.append("- 提供更详细、完整的回答")
        
        # 添加通用改进建议
        if self.negative_examples:
            issues.append("- 如果不确定，请明确说明信息来源的局限性")
            issues.append("- 对于复杂问题，建议分点回答")
        
        if issues:
            return "\n\n【基于用户反馈的改进要求】\n" + "\n".join(issues)
        return ""
    
    def trigger_optimization(self):
        """
        触发 Prompt 优化
        分析反馈模式，生成优化建议
        """
        self.last_optimization = datetime.utcnow()
        logger.info(f"Triggering prompt optimization with {len(self.negative_examples)} negative examples")
        
        # 这里可以调用 LLM 来分析反馈并生成优化建议
        # 简化版本：基于规则生成
        
    def build_optimized_system_prompt(self, base_prompt: str, scenario: str = "default") -> str:
        """
        构建优化后的 System Prompt
        """
        # 添加 Few-shot 示例
        examples = self.get_few_shot_examples("", max_examples=2)
        
        # 添加优化提示
        hints = self.get_optimization_hints()
        
        optimized = base_prompt
        
        if hints:
            optimized += hints
        
        if examples:
            optimized += "\n\n【参考回答示例】\n"
            for i, ex in enumerate(examples, 1):
                optimized += f"\n示例 {i}:\n用户: {ex['user'][:100]}...\n回答: {ex['assistant'][:200]}...\n"
        
        return optimized


# 全局优化器实例
_optimizer = PromptOptimizer()


def get_optimizer() -> PromptOptimizer:
    """获取优化器实例"""
    return _optimizer


def record_feedback(
    conversation_id: str,
    message_id: str,
    user_query: str,
    assistant_response: str,
    feedback_type: str,
    feedback_value: Any,
    correction_text: Optional[str] = None,
    retrieved_sources: List[str] = None
) -> FeedbackRecord:
    """记录反馈"""
    import uuid
    
    feedback = FeedbackRecord(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        message_id=message_id,
        user_query=user_query,
        assistant_response=assistant_response,
        feedback_type=FeedbackType(feedback_type),
        feedback_value=feedback_value,
        correction_text=correction_text,
        retrieved_sources=retrieved_sources or [],
    )
    
    _optimizer.add_feedback(feedback)
    return feedback

