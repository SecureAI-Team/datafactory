"""
动态交互流程服务
使用 LLM 动态生成问题，而非静态预定义问题
"""
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from openai import OpenAI

from .intent_recognizer import IntentResult, IntentType, ActionType

logger = logging.getLogger(__name__)


class QuestionType(str, Enum):
    """问题类型"""
    SINGLE = "single"      # 单选
    MULTI = "multi"        # 多选
    INPUT = "input"        # 输入
    CONFIRM = "confirm"    # 确认


@dataclass
class QuestionOption:
    """问题选项"""
    id: str
    label: str
    icon: Optional[str] = None


@dataclass
class DynamicQuestion:
    """动态生成的问题"""
    field_id: str                    # 字段ID（如 industry, product）
    question: str                    # 问题文本
    question_type: QuestionType      # 问题类型
    options: List[QuestionOption] = field(default_factory=list)
    placeholder: str = ""            # 输入占位符
    required: bool = True
    reason: str = ""                 # 为什么需要这个信息


@dataclass
class MissingInfoAnalysis:
    """缺失信息分析结果"""
    can_proceed: bool                # 是否可以直接执行
    missing_fields: List[Dict[str, Any]] = field(default_factory=list)
    next_question: Optional[DynamicQuestion] = None
    optimized_query: str = ""        # 优化后的查询
    collected_context: Dict[str, Any] = field(default_factory=dict)


class DynamicInteractionService:
    """
    动态交互流程服务
    
    核心理念：
    - 不使用预定义的静态问题列表
    - LLM 根据当前上下文动态决定需要问什么
    - 每次只生成一个最关键的问题
    - 问题内容与用户已提供的信息相关联
    """
    
    def __init__(self, llm_client: Optional[OpenAI] = None):
        self.llm_client = llm_client
    
    def analyze_and_generate_question(
        self,
        intent_result: IntentResult,
        collected_answers: Dict[str, Any] = None,
        original_query: str = "",
        history: List[Dict] = None
    ) -> MissingInfoAnalysis:
        """
        分析缺失信息并动态生成下一个问题
        
        Args:
            intent_result: 意图识别结果
            collected_answers: 已收集的答案
            original_query: 用户原始问题
            history: 对话历史
        
        Returns:
            MissingInfoAnalysis: 分析结果，包含下一个问题（如果需要）
        """
        collected_answers = collected_answers or {}
        history = history or []
        
        if not self.llm_client:
            # 无 LLM 时回退到基于规则的简单逻辑
            return self._rule_based_analysis(intent_result, collected_answers)
        
        return self._llm_based_analysis(
            intent_result, collected_answers, original_query, history
        )
    
    def _llm_based_analysis(
        self,
        intent_result: IntentResult,
        collected_answers: Dict[str, Any],
        original_query: str,
        history: List[Dict]
    ) -> MissingInfoAnalysis:
        """使用 LLM 分析并生成问题"""
        
        # 构建已知信息
        known_info = {
            "intent": intent_result.intent_type.value,
            "entities": intent_result.entities,
            "scenarios": intent_result.scenario_ids,
            "keywords": intent_result.matched_keywords,
            "collected_answers": collected_answers,
        }
        
        # 如果有上下文充分性分析结果，也包含进来
        if intent_result.context_sufficiency:
            known_info["extracted_context"] = intent_result.context_sufficiency.extracted_context
        
        known_info_text = json.dumps(known_info, ensure_ascii=False, indent=2)
        
        # 构建对话历史
        history_text = "无"
        if history:
            history_lines = [
                f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')[:100]}"
                for m in history[-5:]
            ]
            history_text = "\n".join(history_lines)
        
        prompt = f"""分析用户意图，判断是否需要收集更多信息，如果需要则生成一个问题。

用户原始问题: {original_query}
意图类型: {intent_result.intent_type.value}
已知信息:
{known_info_text}

对话历史:
{history_text}

任务说明:
1. 判断是否已经有足够的信息来执行用户请求
2. 如果信息不足，确定最关键的缺失信息是什么
3. 生成一个与上下文相关的问题（不是通用问题）

生成问题的规则:
- 问题要与用户原始问题相关联
- 如果用户问"工控安全案例"，不要问"请选择行业"（因为已经说了工控）
- 问题应该简洁明了
- 提供的选项应该与用户上下文相关
- 每次只问一个最关键的问题

请以 JSON 格式返回:
{{
    "can_proceed": true/false,
    "reason": "判断理由",
    "missing_fields": [
        {{"field": "字段名", "importance": "required/optional", "description": "为什么需要"}}
    ],
    "optimized_query": "如果可以继续，用于检索的优化查询",
    "next_question": {{
        "field_id": "字段ID",
        "question": "问题文本（与上下文相关）",
        "question_type": "single/multi/input/confirm",
        "options": [
            {{"id": "选项ID", "label": "选项文本"}}
        ],
        "placeholder": "输入类型的占位符",
        "reason": "为什么问这个问题"
    }}
}}

如果 can_proceed=true，next_question 可以为 null。
只返回 JSON，不要其他内容。"""

        try:
            response = self.llm_client.chat.completions.create(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"Dynamic question generation: {content[:300]}...")
            
            import re
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                result = json.loads(json_match.group())
                
                can_proceed = result.get("can_proceed", True)
                missing_fields = result.get("missing_fields", [])
                optimized_query = result.get("optimized_query", original_query)
                
                next_question = None
                if not can_proceed and result.get("next_question"):
                    q = result["next_question"]
                    options = [
                        QuestionOption(id=opt["id"], label=opt["label"], icon=opt.get("icon"))
                        for opt in q.get("options", [])
                    ]
                    next_question = DynamicQuestion(
                        field_id=q.get("field_id", "unknown"),
                        question=q.get("question", ""),
                        question_type=QuestionType(q.get("question_type", "single")),
                        options=options,
                        placeholder=q.get("placeholder", ""),
                        reason=q.get("reason", "")
                    )
                
                return MissingInfoAnalysis(
                    can_proceed=can_proceed,
                    missing_fields=missing_fields,
                    next_question=next_question,
                    optimized_query=optimized_query,
                    collected_context=intent_result.context_sufficiency.extracted_context 
                        if intent_result.context_sufficiency else {}
                )
                
        except Exception as e:
            logger.warning(f"LLM dynamic question generation failed: {e}")
        
        # 回退：允许继续
        return MissingInfoAnalysis(
            can_proceed=True,
            optimized_query=original_query
        )
    
    def _rule_based_analysis(
        self,
        intent_result: IntentResult,
        collected_answers: Dict[str, Any]
    ) -> MissingInfoAnalysis:
        """基于规则的简单分析（无 LLM 时使用）"""
        
        intent = intent_result.intent_type
        entities = intent_result.entities
        
        # 案例查询：需要行业或主题
        if intent == IntentType.CASE_STUDY:
            if not intent_result.scenario_ids and "industry" not in collected_answers:
                return MissingInfoAnalysis(
                    can_proceed=False,
                    missing_fields=[{"field": "industry", "importance": "required"}],
                    next_question=DynamicQuestion(
                        field_id="industry",
                        question="您想查找哪个行业的案例？",
                        question_type=QuestionType.SINGLE,
                        options=[
                            QuestionOption(id="automotive", label="汽车电子"),
                            QuestionOption(id="consumer", label="消费电子"),
                            QuestionOption(id="industrial", label="工业控制"),
                            QuestionOption(id="medical", label="医疗器械"),
                            QuestionOption(id="other", label="其他"),
                        ]
                    )
                )
        
        # 报价查询：需要产品信息
        if intent == IntentType.QUOTE:
            if "product" not in entities and "product" not in collected_answers:
                return MissingInfoAnalysis(
                    can_proceed=False,
                    missing_fields=[{"field": "product", "importance": "required"}],
                    next_question=DynamicQuestion(
                        field_id="product",
                        question="您想了解哪款产品的报价？",
                        question_type=QuestionType.INPUT,
                        placeholder="例如：AOI8000"
                    )
                )
        
        # 计算类：需要参数
        if intent == IntentType.CALCULATION:
            required = ["capacity", "power"]
            missing = [p for p in required if p not in entities and p not in collected_answers]
            if missing:
                field = missing[0]
                return MissingInfoAnalysis(
                    can_proceed=False,
                    missing_fields=[{"field": field, "importance": "required"}],
                    next_question=DynamicQuestion(
                        field_id=field,
                        question=f"请输入{field}参数",
                        question_type=QuestionType.INPUT,
                        placeholder="请输入数值"
                    )
                )
        
        # 默认：可以继续
        return MissingInfoAnalysis(
            can_proceed=True,
            optimized_query=""
        )
    
    def format_collected_info_for_display(
        self,
        collected_answers: Dict[str, Any],
        questions_asked: List[DynamicQuestion]
    ) -> str:
        """格式化已收集信息用于显示"""
        if not collected_answers:
            return ""
        
        lines = ["📋 已收集信息："]
        for q in questions_asked:
            if q.field_id in collected_answers:
                answer = collected_answers[q.field_id]
                # 如果是选项类型，转换为标签
                if q.question_type in (QuestionType.SINGLE, QuestionType.MULTI):
                    option_map = {opt.id: opt.label for opt in q.options}
                    if isinstance(answer, list):
                        answer = ", ".join([option_map.get(a, a) for a in answer])
                    else:
                        answer = option_map.get(answer, answer)
                lines.append(f"  • {q.question.rstrip('？?')}: {answer}")
        
        return "\n".join(lines)


# ==================== 便捷函数 ====================

_service_instance: Optional[DynamicInteractionService] = None


def get_dynamic_interaction_service(
    llm_client: Optional[OpenAI] = None
) -> DynamicInteractionService:
    """获取动态交互服务实例"""
    global _service_instance
    
    if _service_instance is None:
        _service_instance = DynamicInteractionService(llm_client)
    elif llm_client and not _service_instance.llm_client:
        _service_instance.llm_client = llm_client
    
    return _service_instance


def analyze_missing_info(
    intent_result: IntentResult,
    collected_answers: Dict[str, Any] = None,
    original_query: str = "",
    history: List[Dict] = None,
    llm_client: Optional[OpenAI] = None
) -> MissingInfoAnalysis:
    """便捷函数：分析缺失信息并生成问题"""
    service = get_dynamic_interaction_service(llm_client)
    return service.analyze_and_generate_question(
        intent_result, collected_answers, original_query, history
    )

