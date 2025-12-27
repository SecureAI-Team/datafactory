"""
Prompt 自动优化器
基于反馈数据自动生成 Few-shot 示例和优化建议
"""
import time
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OptimizationType(str, Enum):
    """优化类型"""
    FEW_SHOT = "few_shot"              # 添加 Few-shot 示例
    NEGATIVE_EXAMPLE = "negative"       # 添加负面示例
    INSTRUCTION_TWEAK = "instruction"   # 调整指令
    RETRIEVAL_HINT = "retrieval_hint"   # 检索提示
    FORMAT_GUIDE = "format_guide"       # 格式指导


@dataclass
class FewShotExample:
    """Few-shot 示例"""
    query: str
    response: str
    rating: float
    intent_type: str = ""
    scenario_id: str = ""
    source: str = "feedback"  # feedback/manual/generated


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    optimization_type: OptimizationType
    target_intent: Optional[str] = None
    target_scenario: Optional[str] = None
    priority: str = "medium"  # low/medium/high/critical
    
    description: str = ""
    original_content: str = ""
    suggested_content: str = ""
    
    examples: List[FewShotExample] = field(default_factory=list)
    reasoning: str = ""
    expected_impact: str = ""
    
    created_at: float = field(default_factory=time.time)
    applied: bool = False


@dataclass
class OptimizedPrompt:
    """优化后的 Prompt"""
    base_prompt: str
    few_shot_section: str = ""
    instruction_additions: List[str] = field(default_factory=list)
    negative_guidance: List[str] = field(default_factory=list)
    format_hints: List[str] = field(default_factory=list)
    
    def build(self) -> str:
        """构建完整 Prompt"""
        parts = [self.base_prompt]
        
        if self.instruction_additions:
            parts.append("\n【额外指导】")
            for instruction in self.instruction_additions:
                parts.append(f"- {instruction}")
        
        if self.negative_guidance:
            parts.append("\n【避免事项】")
            for guidance in self.negative_guidance:
                parts.append(f"- {guidance}")
        
        if self.format_hints:
            parts.append("\n【格式要求】")
            for hint in self.format_hints:
                parts.append(f"- {hint}")
        
        if self.few_shot_section:
            parts.append("\n" + self.few_shot_section)
        
        return "\n".join(parts)


class PromptOptimizer:
    """Prompt 优化器"""
    
    def __init__(self, feedback_optimizer=None):
        self._feedback_optimizer = feedback_optimizer
        self._suggestions_cache: Dict[str, List[OptimizationSuggestion]] = {}
        self._applied_optimizations: List[OptimizationSuggestion] = []
        
        # 优化规则
        self.optimization_rules = {
            "low_rating": self._handle_low_rating,
            "incomplete": self._handle_incomplete,
            "irrelevant": self._handle_irrelevant,
            "too_complex": self._handle_too_complex,
            "format_issue": self._handle_format_issue,
        }
    
    @property
    def feedback_optimizer(self):
        if self._feedback_optimizer is None:
            from .feedback_optimizer import get_feedback_optimizer
            self._feedback_optimizer = get_feedback_optimizer()
        return self._feedback_optimizer
    
    def generate_suggestions(
        self,
        intent_type: str = None,
        scenario_id: str = None,
        days: int = 7,
    ) -> List[OptimizationSuggestion]:
        """
        基于反馈生成优化建议
        
        Args:
            intent_type: 目标意图
            scenario_id: 目标场景
            days: 分析天数
        
        Returns:
            优化建议列表
        """
        suggestions = []
        
        # 获取反馈统计
        stats = self.feedback_optimizer.get_stats(
            days=days,
            intent_type=intent_type,
            scenario_id=scenario_id,
        )
        
        # 1. 检查是否需要 Few-shot 示例
        few_shot_suggestion = self._generate_few_shot_suggestion(
            intent_type, scenario_id
        )
        if few_shot_suggestion:
            suggestions.append(few_shot_suggestion)
        
        # 2. 分析常见问题并生成对应建议
        for issue in stats.common_issues:
            issue_type = self._classify_issue(issue)
            if issue_type and issue_type in self.optimization_rules:
                suggestion = self.optimization_rules[issue_type](
                    issue, intent_type, scenario_id
                )
                if suggestion:
                    suggestions.append(suggestion)
        
        # 3. 检查负面反馈集中区域
        negative_suggestions = self._analyze_negative_clusters(
            intent_type, scenario_id, days
        )
        suggestions.extend(negative_suggestions)
        
        # 排序（按优先级）
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(key=lambda x: priority_order.get(x.priority, 2))
        
        # 缓存
        cache_key = f"{intent_type or 'all'}:{scenario_id or 'all'}"
        self._suggestions_cache[cache_key] = suggestions
        
        return suggestions
    
    def _generate_few_shot_suggestion(
        self,
        intent_type: str,
        scenario_id: str,
    ) -> Optional[OptimizationSuggestion]:
        """生成 Few-shot 建议"""
        examples = self.feedback_optimizer.get_few_shot_examples(
            intent_type or "general",
            scenario_id,
            limit=5,
        )
        
        if len(examples) < 2:
            return None
        
        few_shot_examples = []
        for ex in examples:
            few_shot_examples.append(FewShotExample(
                query=ex["query"],
                response=ex["response"],
                rating=ex.get("rating", 5),
                intent_type=intent_type or "",
                scenario_id=scenario_id or "",
            ))
        
        return OptimizationSuggestion(
            optimization_type=OptimizationType.FEW_SHOT,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="medium",
            description=f"基于 {len(examples)} 个高评分回答生成 Few-shot 示例",
            examples=few_shot_examples,
            reasoning="高评分回答可作为模型学习的范例",
            expected_impact="提升回答质量和一致性",
        )
    
    def _classify_issue(self, issue: Dict) -> Optional[str]:
        """分类问题"""
        keyword = issue.get("keyword", "")
        
        if "不详细" in keyword or "太简单" in keyword:
            return "incomplete"
        elif "不相关" in keyword or "答非所问" in keyword:
            return "irrelevant"
        elif "太复杂" in keyword or "看不懂" in keyword:
            return "too_complex"
        elif "格式" in keyword:
            return "format_issue"
        
        return None
    
    def _handle_low_rating(
        self,
        issue: Dict,
        intent_type: str,
        scenario_id: str,
    ) -> OptimizationSuggestion:
        """处理低评分问题"""
        return OptimizationSuggestion(
            optimization_type=OptimizationType.INSTRUCTION_TWEAK,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="high",
            description="整体评分较低，需要优化回答策略",
            suggested_content="请确保回答：1)直接解答问题核心 2)提供具体可操作的建议 3)引用知识库来源",
            reasoning=f"检测到问题: {issue.get('description', '')}",
            expected_impact="提升用户满意度",
        )
    
    def _handle_incomplete(
        self,
        issue: Dict,
        intent_type: str,
        scenario_id: str,
    ) -> OptimizationSuggestion:
        """处理回答不完整问题"""
        return OptimizationSuggestion(
            optimization_type=OptimizationType.INSTRUCTION_TWEAK,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="high",
            description="用户反馈回答不够详细",
            suggested_content=(
                "回答时请注意：\n"
                "1. 提供完整的解答，不要遗漏关键步骤\n"
                "2. 主动补充相关的背景信息和注意事项\n"
                "3. 如有多个方案，简要对比各自优缺点\n"
                "4. 结尾可以询问是否需要更详细的说明"
            ),
            reasoning=f"发现 {issue.get('count', 0)} 条'不详细'相关反馈",
            expected_impact="减少追问，提升首次回答满意度",
        )
    
    def _handle_irrelevant(
        self,
        issue: Dict,
        intent_type: str,
        scenario_id: str,
    ) -> OptimizationSuggestion:
        """处理回答不相关问题"""
        return OptimizationSuggestion(
            optimization_type=OptimizationType.RETRIEVAL_HINT,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="critical",
            description="用户反馈回答与问题不相关",
            suggested_content=(
                "请严格遵循：\n"
                "1. 仔细分析用户问题的核心意图\n"
                "2. 只使用与问题直接相关的知识库内容\n"
                "3. 如果知识库没有相关内容，直接说明而不是给出无关回答\n"
                "4. 回答前确认理解了用户的真实需求"
            ),
            reasoning=f"发现 {issue.get('count', 0)} 条'不相关'反馈，可能是检索或理解问题",
            expected_impact="提升回答相关性",
        )
    
    def _handle_too_complex(
        self,
        issue: Dict,
        intent_type: str,
        scenario_id: str,
    ) -> OptimizationSuggestion:
        """处理回答过于复杂问题"""
        return OptimizationSuggestion(
            optimization_type=OptimizationType.FORMAT_GUIDE,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="medium",
            description="用户反馈回答过于复杂难懂",
            suggested_content=(
                "回答格式建议：\n"
                "1. 先给出简明的结论或答案\n"
                "2. 使用简洁的语言，避免过多术语\n"
                "3. 如需使用专业术语，附带简短解释\n"
                "4. 适当使用列表和分点，提高可读性\n"
                "5. 复杂内容可分层次展开"
            ),
            reasoning=f"发现 {issue.get('count', 0)} 条'太复杂'反馈",
            expected_impact="提升回答可读性",
        )
    
    def _handle_format_issue(
        self,
        issue: Dict,
        intent_type: str,
        scenario_id: str,
    ) -> OptimizationSuggestion:
        """处理格式问题"""
        return OptimizationSuggestion(
            optimization_type=OptimizationType.FORMAT_GUIDE,
            target_intent=intent_type,
            target_scenario=scenario_id,
            priority="low",
            description="用户反馈格式需要改进",
            suggested_content=(
                "格式规范：\n"
                "- 使用 Markdown 格式\n"
                "- 重点内容使用 **加粗**\n"
                "- 步骤使用有序列表\n"
                "- 代码使用代码块\n"
                "- 适当使用表格对比"
            ),
            reasoning=f"发现格式相关反馈",
            expected_impact="提升阅读体验",
        )
    
    def _analyze_negative_clusters(
        self,
        intent_type: str,
        scenario_id: str,
        days: int,
    ) -> List[OptimizationSuggestion]:
        """分析负面反馈聚集"""
        from .feedback_optimizer import FeedbackType
        
        suggestions = []
        
        records = self.feedback_optimizer._feedback_records
        cutoff = time.time() - days * 86400
        
        # 筛选负面反馈
        negative = [
            r for r in records
            if r.created_at >= cutoff
            and r.feedback_type in (FeedbackType.EXPLICIT_NEGATIVE, FeedbackType.NATURAL_NEGATIVE)
            and (intent_type is None or r.intent_type == intent_type)
            and (scenario_id is None or r.scenario_id == scenario_id)
        ]
        
        if len(negative) >= 5:
            # 提取负面示例
            negative_examples = []
            for r in negative[:5]:
                negative_examples.append(FewShotExample(
                    query=r.query,
                    response=r.response_preview,
                    rating=r.rating or 1,
                    intent_type=r.intent_type or "",
                    source="feedback",
                ))
            
            suggestions.append(OptimizationSuggestion(
                optimization_type=OptimizationType.NEGATIVE_EXAMPLE,
                target_intent=intent_type,
                target_scenario=scenario_id,
                priority="high",
                description=f"发现 {len(negative)} 条负面反馈聚集",
                examples=negative_examples,
                reasoning="负面示例可帮助模型避免类似错误",
                expected_impact="减少相似错误的发生",
            ))
        
        return suggestions
    
    def apply_optimization(
        self,
        suggestion: OptimizationSuggestion,
        base_prompt: str,
    ) -> OptimizedPrompt:
        """
        应用优化建议
        
        Args:
            suggestion: 优化建议
            base_prompt: 基础 Prompt
        
        Returns:
            OptimizedPrompt
        """
        optimized = OptimizedPrompt(base_prompt=base_prompt)
        
        if suggestion.optimization_type == OptimizationType.FEW_SHOT:
            # 构建 Few-shot 部分
            if suggestion.examples:
                few_shot_lines = ["\n【优秀回答示例】"]
                for i, ex in enumerate(suggestion.examples[:3], 1):
                    few_shot_lines.append(f"\n示例{i}:")
                    few_shot_lines.append(f"用户: {ex.query}")
                    few_shot_lines.append(f"助手: {ex.response}")
                optimized.few_shot_section = "\n".join(few_shot_lines)
        
        elif suggestion.optimization_type == OptimizationType.NEGATIVE_EXAMPLE:
            # 添加避免事项
            if suggestion.examples:
                for ex in suggestion.examples[:2]:
                    optimized.negative_guidance.append(
                        f"避免类似回答：对于'{ex.query[:30]}...'这类问题，不要给出过于笼统的回答"
                    )
        
        elif suggestion.optimization_type == OptimizationType.INSTRUCTION_TWEAK:
            if suggestion.suggested_content:
                optimized.instruction_additions.append(suggestion.suggested_content)
        
        elif suggestion.optimization_type == OptimizationType.RETRIEVAL_HINT:
            if suggestion.suggested_content:
                optimized.instruction_additions.append(suggestion.suggested_content)
        
        elif suggestion.optimization_type == OptimizationType.FORMAT_GUIDE:
            if suggestion.suggested_content:
                optimized.format_hints.append(suggestion.suggested_content)
        
        # 标记已应用
        suggestion.applied = True
        self._applied_optimizations.append(suggestion)
        
        return optimized
    
    def build_optimized_prompt(
        self,
        base_prompt: str,
        intent_type: str = None,
        scenario_id: str = None,
        auto_apply: bool = True,
    ) -> str:
        """
        构建优化后的 Prompt
        
        Args:
            base_prompt: 基础 Prompt
            intent_type: 意图类型
            scenario_id: 场景ID
            auto_apply: 是否自动应用建议
        
        Returns:
            优化后的 Prompt 字符串
        """
        if not auto_apply:
            return base_prompt
        
        # 生成建议
        suggestions = self.generate_suggestions(intent_type, scenario_id)
        
        if not suggestions:
            return base_prompt
        
        # 应用高优先级建议
        optimized = OptimizedPrompt(base_prompt=base_prompt)
        
        for suggestion in suggestions:
            if suggestion.priority in ("critical", "high"):
                result = self.apply_optimization(suggestion, base_prompt)
                # 合并结果
                if result.few_shot_section:
                    optimized.few_shot_section = result.few_shot_section
                optimized.instruction_additions.extend(result.instruction_additions)
                optimized.negative_guidance.extend(result.negative_guidance)
                optimized.format_hints.extend(result.format_hints)
        
        return optimized.build()
    
    def get_applied_optimizations(self) -> List[Dict]:
        """获取已应用的优化"""
        return [
            {
                "type": opt.optimization_type.value,
                "intent": opt.target_intent,
                "scenario": opt.target_scenario,
                "description": opt.description,
                "applied_at": opt.created_at,
            }
            for opt in self._applied_optimizations
        ]


# ==================== 模块级便捷函数 ====================

_default_optimizer: Optional[PromptOptimizer] = None


def get_prompt_optimizer() -> PromptOptimizer:
    """获取 Prompt 优化器实例"""
    global _default_optimizer
    if _default_optimizer is None:
        _default_optimizer = PromptOptimizer()
    return _default_optimizer


def optimize_prompt(
    base_prompt: str,
    intent_type: str = None,
    scenario_id: str = None,
) -> str:
    """便捷函数：优化 Prompt"""
    return get_prompt_optimizer().build_optimized_prompt(
        base_prompt, intent_type, scenario_id
    )


def get_optimization_suggestions(
    intent_type: str = None,
    scenario_id: str = None,
) -> List[OptimizationSuggestion]:
    """便捷函数：获取优化建议"""
    return get_prompt_optimizer().generate_suggestions(intent_type, scenario_id)

