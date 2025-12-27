"""
澄清问卷引擎
根据意图和场景动态生成澄清问题
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .intent_recognizer import IntentType, IntentResult, SceneClassification

logger = logging.getLogger(__name__)


@dataclass
class ClarificationOption:
    """澄清选项"""
    id: str
    label: str
    value: Any
    description: str = ""


@dataclass
class ClarificationQuestion:
    """澄清问题"""
    id: str
    question: str
    options: List[ClarificationOption]
    required: bool = True
    multi_select: bool = False
    allow_free_text: bool = True


@dataclass
class ClarificationQuestionnaire:
    """澄清问卷"""
    questions: List[ClarificationQuestion]
    intro_message: str = ""
    outro_message: str = ""


class ClarificationEngine:
    """澄清问卷引擎"""
    
    def __init__(self):
        # 预定义的问题模板
        self.question_templates = self._build_question_templates()
        # 场景-意图 -> 问题列表 映射
        self.questionnaire_rules = self._build_questionnaire_rules()
    
    def _build_question_templates(self) -> Dict[str, ClarificationQuestion]:
        """构建问题模板库"""
        return {
            # === 通用问题 ===
            "enterprise_scale": ClarificationQuestion(
                id="enterprise_scale",
                question="您的企业规模是？",
                options=[
                    ClarificationOption("small", "小型企业", {"employees": "<100"}, "员工少于100人"),
                    ClarificationOption("medium", "中型企业", {"employees": "100-1000"}, "员工100-1000人"),
                    ClarificationOption("large", "大型企业", {"employees": ">1000"}, "员工超过1000人"),
                ],
            ),
            "budget_range": ClarificationQuestion(
                id="budget_range",
                question="您的预算范围是？",
                options=[
                    ClarificationOption("limited", "有限", {"budget": "<50万"}, "预算50万以下"),
                    ClarificationOption("medium", "中等", {"budget": "50-200万"}, "预算50-200万"),
                    ClarificationOption("sufficient", "充足", {"budget": ">200万"}, "预算200万以上"),
                ],
            ),
            "tech_capability": ClarificationQuestion(
                id="tech_capability",
                question="您的技术团队能力如何？",
                options=[
                    ClarificationOption("basic", "基础", {"level": "basic"}, "有基础IT运维能力"),
                    ClarificationOption("intermediate", "中等", {"level": "intermediate"}, "有专业技术团队"),
                    ClarificationOption("advanced", "专业", {"level": "advanced"}, "有专家级技术团队"),
                ],
            ),
            "urgency": ClarificationQuestion(
                id="urgency",
                question="项目紧急程度？",
                options=[
                    ClarificationOption("low", "不急", {"urgency": "low"}, "可以慢慢评估"),
                    ClarificationOption("medium", "一般", {"urgency": "medium"}, "近期需要落地"),
                    ClarificationOption("high", "紧急", {"urgency": "high"}, "需要尽快上线"),
                ],
            ),
            
            # === AOI 视觉检测相关 ===
            "aoi_product_type": ClarificationQuestion(
                id="aoi_product_type",
                question="您需要检测的产品类型是？",
                options=[
                    ClarificationOption("pcb", "PCB电路板", {"product": "pcb"}, "印刷电路板检测"),
                    ClarificationOption("smt", "SMT贴片", {"product": "smt"}, "贴片元器件检测"),
                    ClarificationOption("appearance", "外观件", {"product": "appearance"}, "产品外观检测"),
                    ClarificationOption("semiconductor", "半导体", {"product": "semiconductor"}, "晶圆/芯片检测"),
                    ClarificationOption("other", "其他", {"product": "other"}, "其他类型产品"),
                ],
            ),
            "aoi_defect_type": ClarificationQuestion(
                id="aoi_defect_type",
                question="您主要关注哪类缺陷检测？",
                options=[
                    ClarificationOption("solder", "焊接缺陷", {"defect": "solder"}, "虚焊、桥连、少锡等"),
                    ClarificationOption("placement", "贴装缺陷", {"defect": "placement"}, "偏移、缺件、极性反等"),
                    ClarificationOption("surface", "表面缺陷", {"defect": "surface"}, "划痕、污染、变色等"),
                    ClarificationOption("dimension", "尺寸缺陷", {"defect": "dimension"}, "尺寸偏差、变形等"),
                ],
                multi_select=True,
            ),
            "aoi_capacity": ClarificationQuestion(
                id="aoi_capacity",
                question="您的产线节拍要求是？",
                options=[
                    ClarificationOption("low", "低速", {"capacity": "<1000"}, "每小时1000件以下"),
                    ClarificationOption("medium", "中速", {"capacity": "1000-5000"}, "每小时1000-5000件"),
                    ClarificationOption("high", "高速", {"capacity": ">5000"}, "每小时5000件以上"),
                ],
            ),
            "aoi_precision": ClarificationQuestion(
                id="aoi_precision",
                question="您需要的检测精度是？",
                options=[
                    ClarificationOption("standard", "标准精度", {"precision": "0.1mm"}, "0.1mm级别"),
                    ClarificationOption("high", "高精度", {"precision": "0.05mm"}, "0.05mm级别"),
                    ClarificationOption("ultra", "超高精度", {"precision": "<0.01mm"}, "0.01mm以下"),
                ],
            ),
            
            # === 网络安全相关 ===
            "security_concern": ClarificationQuestion(
                id="security_concern",
                question="您最关心的安全问题是？",
                options=[
                    ClarificationOption("data_leak", "数据泄露", {"concern": "data_leak"}, "防止数据外泄"),
                    ClarificationOption("intrusion", "入侵攻击", {"concern": "intrusion"}, "防止黑客入侵"),
                    ClarificationOption("compliance", "合规要求", {"concern": "compliance"}, "满足等保要求"),
                    ClarificationOption("insider", "内部威胁", {"concern": "insider"}, "防止内部人员风险"),
                ],
                multi_select=True,
            ),
            "current_security": ClarificationQuestion(
                id="current_security",
                question="您当前的安全建设情况？",
                options=[
                    ClarificationOption("none", "基本没有", {"current": "none"}, "安全措施很少"),
                    ClarificationOption("basic", "基础防护", {"current": "basic"}, "有防火墙等基础设施"),
                    ClarificationOption("advanced", "较为完善", {"current": "advanced"}, "有完整的安全体系"),
                ],
            ),
            
            # === 对比分析相关 ===
            "comparison_dimension": ClarificationQuestion(
                id="comparison_dimension",
                question="您最关注哪些对比维度？",
                options=[
                    ClarificationOption("cost", "成本", {"dim": "cost"}, "采购和运维成本"),
                    ClarificationOption("performance", "性能", {"dim": "performance"}, "功能和性能表现"),
                    ClarificationOption("ease", "易用性", {"dim": "ease"}, "部署和使用难度"),
                    ClarificationOption("security", "安全性", {"dim": "security"}, "安全防护能力"),
                    ClarificationOption("scalability", "扩展性", {"dim": "scalability"}, "未来扩展能力"),
                ],
                multi_select=True,
            ),
        }
    
    def _build_questionnaire_rules(self) -> Dict[Tuple, List[str]]:
        """构建问卷规则：(场景, 意图) -> 问题ID列表"""
        return {
            # AOI 方案推荐
            ("aoi_inspection", IntentType.SOLUTION_RECOMMENDATION): [
                "aoi_product_type",
                "aoi_defect_type",
                "aoi_capacity",
                "budget_range",
            ],
            # AOI 计算选型
            ("aoi_inspection", IntentType.CALCULATION): [
                "aoi_product_type",
                "aoi_capacity",
                "aoi_precision",
            ],
            # AOI 参数查询
            ("aoi_inspection", IntentType.PARAMETER_QUERY): [
                "aoi_product_type",
            ],
            
            # 网络安全方案推荐
            ("network_security", IntentType.SOLUTION_RECOMMENDATION): [
                "enterprise_scale",
                "security_concern",
                "current_security",
                "budget_range",
            ],
            
            # 通用方案推荐
            ("default", IntentType.SOLUTION_RECOMMENDATION): [
                "enterprise_scale",
                "budget_range",
                "tech_capability",
            ],
            
            # 对比分析
            ("default", IntentType.COMPARISON): [
                "comparison_dimension",
            ],
            
            # 操作指南
            ("default", IntentType.HOW_TO): [
                "tech_capability",
            ],
        }
    
    def generate_questionnaire(
        self,
        intent_result: IntentResult,
        existing_context: Dict[str, Any] = None,
    ) -> Optional[ClarificationQuestionnaire]:
        """
        根据意图生成澄清问卷
        
        Args:
            intent_result: 意图识别结果
            existing_context: 已有上下文（用于过滤已回答的问题）
        
        Returns:
            ClarificationQuestionnaire 或 None（如果不需要澄清）
        """
        existing_context = existing_context or {}
        
        if not intent_result.needs_clarification:
            return None
        
        # 获取问题列表
        question_ids = self._get_question_ids(intent_result)
        
        if not question_ids:
            return None
        
        # 过滤已回答的问题
        unanswered_ids = [
            qid for qid in question_ids
            if qid not in existing_context
        ]
        
        if not unanswered_ids:
            return None
        
        # 构建问卷
        questions = [
            self.question_templates[qid]
            for qid in unanswered_ids[:3]  # 最多3个问题
            if qid in self.question_templates
        ]
        
        if not questions:
            return None
        
        # 生成介绍语
        intro = self._generate_intro(intent_result)
        outro = "💡 您也可以直接描述具体需求，我会尽力理解。"
        
        return ClarificationQuestionnaire(
            questions=questions,
            intro_message=intro,
            outro_message=outro,
        )
    
    def _get_question_ids(self, intent_result: IntentResult) -> List[str]:
        """获取适用的问题ID列表"""
        # 尝试精确匹配 (scenario, intent)
        for scenario_id in intent_result.scenario_ids or ["default"]:
            key = (scenario_id, intent_result.intent_type)
            if key in self.questionnaire_rules:
                return self.questionnaire_rules[key]
        
        # 尝试匹配 (default, intent)
        key = ("default", intent_result.intent_type)
        if key in self.questionnaire_rules:
            return self.questionnaire_rules[key]
        
        return []
    
    def _generate_intro(self, intent_result: IntentResult) -> str:
        """生成问卷介绍语"""
        intent_intros = {
            IntentType.SOLUTION_RECOMMENDATION: "🤔 为了给您更精准的方案推荐，请先告诉我：",
            IntentType.CALCULATION: "🤔 为了帮您准确计算，需要了解以下信息：",
            IntentType.PARAMETER_QUERY: "🤔 为了查询准确的参数，请确认：",
            IntentType.COMPARISON: "🤔 为了更好地进行对比分析，请告诉我：",
            IntentType.HOW_TO: "🤔 为了给您更实用的指南，请补充：",
            IntentType.TROUBLESHOOTING: "🤔 为了帮您诊断问题，请描述：",
        }
        
        return intent_intros.get(
            intent_result.intent_type,
            "🤔 为了更好地帮助您，请回答以下问题："
        )
    
    def format_questionnaire(
        self,
        questionnaire: ClarificationQuestionnaire,
    ) -> str:
        """将问卷格式化为用户友好的文本"""
        lines = [questionnaire.intro_message, ""]
        
        for i, question in enumerate(questionnaire.questions, 1):
            lines.append(f"**{i}. {question.question}**")
            lines.append("")
            
            for j, option in enumerate(question.options, 1):
                emoji = self._get_option_emoji(j)
                desc = f" - {option.description}" if option.description else ""
                lines.append(f"{emoji} {option.label}{desc}")
            
            lines.append("")
        
        if questionnaire.outro_message:
            lines.append("---")
            lines.append(questionnaire.outro_message)
        
        return "\n".join(lines)
    
    def _get_option_emoji(self, index: int) -> str:
        """获取选项表情符号"""
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        return emojis[index - 1] if index <= len(emojis) else f"{index}."
    
    def parse_response(
        self,
        response: str,
        questionnaire: ClarificationQuestionnaire,
    ) -> Dict[str, Any]:
        """
        解析用户对问卷的回复
        
        Args:
            response: 用户回复
            questionnaire: 原始问卷
        
        Returns:
            解析后的上下文字典
        """
        parsed = {}
        response = response.strip()
        
        # 尝试解析数字选择
        # 支持格式: "1", "1,2", "1 2 3", "1、2、3"
        import re
        numbers = re.findall(r'\d+', response)
        
        if numbers and len(questionnaire.questions) == 1:
            # 单问题场景
            question = questionnaire.questions[0]
            selected_indices = [int(n) for n in numbers if 1 <= int(n) <= len(question.options)]
            
            if selected_indices:
                if question.multi_select:
                    # 多选
                    for idx in selected_indices:
                        option = question.options[idx - 1]
                        parsed[question.id] = parsed.get(question.id, [])
                        parsed[question.id].append(option.value)
                else:
                    # 单选
                    option = question.options[selected_indices[0] - 1]
                    parsed[question.id] = option.value
                
                return parsed
        
        # 尝试解析多问题场景
        # 支持格式: "1-2, 2-1" (问题编号-选项编号)
        multi_pattern = re.findall(r'(\d+)[^\d]+(\d+)', response)
        if multi_pattern:
            for q_idx_str, o_idx_str in multi_pattern:
                q_idx = int(q_idx_str) - 1
                o_idx = int(o_idx_str) - 1
                
                if 0 <= q_idx < len(questionnaire.questions):
                    question = questionnaire.questions[q_idx]
                    if 0 <= o_idx < len(question.options):
                        option = question.options[o_idx]
                        parsed[question.id] = option.value
            
            if parsed:
                return parsed
        
        # 自由文本回复 - 存储原始文本
        parsed["free_text"] = response
        
        # 尝试从自由文本中提取关键信息
        parsed.update(self._extract_from_free_text(response, questionnaire))
        
        return parsed
    
    def _extract_from_free_text(
        self,
        text: str,
        questionnaire: ClarificationQuestionnaire,
    ) -> Dict[str, Any]:
        """从自由文本中提取信息"""
        extracted = {}
        text_lower = text.lower()
        
        # 关键词到选项的映射
        keyword_mappings = {
            "enterprise_scale": {
                "小": "small", "小型": "small", "100人以下": "small",
                "中": "medium", "中型": "medium", "几百人": "medium",
                "大": "large", "大型": "large", "上千人": "large", "千人以上": "large",
            },
            "budget_range": {
                "有限": "limited", "不多": "limited", "50万以下": "limited",
                "中等": "medium", "一般": "medium",
                "充足": "sufficient", "足够": "sufficient", "不差钱": "sufficient",
            },
            "aoi_product_type": {
                "pcb": "pcb", "电路板": "pcb", "线路板": "pcb",
                "smt": "smt", "贴片": "smt",
                "外观": "appearance", "表面": "appearance",
                "半导体": "semiconductor", "晶圆": "semiconductor", "芯片": "semiconductor",
            },
        }
        
        for question in questionnaire.questions:
            if question.id in keyword_mappings:
                mappings = keyword_mappings[question.id]
                for keyword, option_id in mappings.items():
                    if keyword in text_lower:
                        # 找到对应的选项值
                        for option in question.options:
                            if option.id == option_id:
                                extracted[question.id] = option.value
                                break
                        break
        
        return extracted


# ==================== 模块级便捷函数 ====================

_default_engine: Optional[ClarificationEngine] = None


def get_clarification_engine() -> ClarificationEngine:
    """获取澄清引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = ClarificationEngine()
    return _default_engine


def generate_clarification(
    intent_result: IntentResult,
    existing_context: Dict[str, Any] = None,
) -> Optional[str]:
    """
    便捷函数：生成澄清问卷文本
    
    Returns:
        格式化的问卷文本，或 None（不需要澄清）
    """
    engine = get_clarification_engine()
    questionnaire = engine.generate_questionnaire(intent_result, existing_context)
    
    if questionnaire:
        return engine.format_questionnaire(questionnaire)
    
    return None


def parse_clarification_response(
    response: str,
    intent_result: IntentResult,
) -> Dict[str, Any]:
    """
    便捷函数：解析用户对问卷的回复
    """
    engine = get_clarification_engine()
    questionnaire = engine.generate_questionnaire(intent_result)
    
    if questionnaire:
        return engine.parse_response(response, questionnaire)
    
    return {"free_text": response}

