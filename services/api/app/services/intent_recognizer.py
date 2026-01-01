"""
增强的意图识别器
统一路由核心 - 规则引擎 + LLM 混合识别 + 上下文充分性判断
"""
import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from openai import OpenAI

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """意图类型枚举"""
    SOLUTION_RECOMMENDATION = "solution_recommendation"  # 方案推荐
    TECHNICAL_QA = "technical_qa"                        # 技术问答
    TROUBLESHOOTING = "troubleshooting"                  # 故障诊断
    COMPARISON = "comparison"                            # 对比分析
    BEST_PRACTICE = "best_practice"                      # 最佳实践
    CONCEPT_EXPLAIN = "concept_explain"                  # 概念解释
    HOW_TO = "how_to"                                    # 操作指南
    PARAMETER_QUERY = "parameter_query"                  # 参数查询
    CALCULATION = "calculation"                          # 计算/选型
    CASE_STUDY = "case_study"                            # 案例查询
    QUOTE = "quote"                                      # 报价咨询
    GENERAL = "general"                                  # 通用


class ActionType(str, Enum):
    """路由动作类型"""
    DIRECT_RAG = "direct_rag"           # 直接使用RAG回答
    NEED_INFO = "need_info"             # 需要收集更多信息
    CALCULATE = "calculate"              # 执行计算
    COMPARE = "compare"                  # 执行对比
    CONTRIBUTE = "contribute"            # 引导贡献


class SceneClassification(str, Enum):
    """场景分类：用于检索路由"""
    GENERAL = "general"           # 通用场景，检索所有
    SINGLE_SCENE = "single"       # 单一场景，优先该场景
    MULTI_SCENE = "multi"         # 多场景交叉


@dataclass
class ContextSufficiency:
    """上下文充分性判断结果"""
    is_sufficient: bool                      # 是否有足够信息直接回答
    missing_fields: List[str] = field(default_factory=list)  # 缺失的关键信息
    extracted_context: Dict[str, Any] = field(default_factory=dict)  # 提取的上下文
    optimized_query: str = ""                # 优化后的检索查询
    suggested_action: ActionType = ActionType.DIRECT_RAG
    confidence: float = 0.0


@dataclass
class IntentResult:
    """意图识别结果 - 增强版"""
    intent_type: IntentType
    confidence: float
    scene_classification: SceneClassification = SceneClassification.GENERAL
    scenario_ids: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)  # 实体抽取结果
    needs_clarification: bool = False
    clarification_reason: str = ""
    raw_llm_analysis: Optional[Dict] = None
    # 新增：上下文充分性和路由建议
    context_sufficiency: Optional[ContextSufficiency] = None
    recommended_action: ActionType = ActionType.DIRECT_RAG


# ==================== 意图识别规则库 ====================

INTENT_PATTERNS = {
    IntentType.SOLUTION_RECOMMENDATION: {
        "keywords": ["推荐", "方案", "解决方案", "怎么选", "选型", "建议", "哪个好", "如何实现", "怎么做"],
        "patterns": [
            r"推荐.*方案",
            r"有.*解决方案",
            r"怎么.*实现",
            r"如何.*部署",
            r"选.*还是.*",
            r"需要.*方案",
        ],
        "priority": 8,
    },
    IntentType.PARAMETER_QUERY: {
        "keywords": ["多少", "几", "参数", "规格", "型号", "功率", "精度", "速度", "尺寸", "重量", "价格"],
        "patterns": [
            r"(\S+)(是)?多少",
            r"功率[是有]?(\d+)",
            r"精度[是有]?(\d+)",
            r"(\S+)[有是]?(什么|哪些)参数",
            r"规格(是|有)?",
            r"(\d+)(w|W|瓦|mm|毫米)",
        ],
        "priority": 9,  # 高优先级
    },
    IntentType.CALCULATION: {
        "keywords": ["需要几台", "多少台", "怎么算", "计算", "选型", "配多少", "够不够"],
        "patterns": [
            r"需要(几|多少)台",
            r"产能.*需要",
            r"(\d+)(片|件|个)/.*[，,].*需要",
            r"怎么(计算|算)",
            r"配(多少|几)",
        ],
        "priority": 10,  # 最高优先级
    },
    IntentType.TROUBLESHOOTING: {
        "keywords": ["问题", "故障", "报错", "失败", "不工作", "异常", "错误", "无法", "不行"],
        "patterns": [
            r"遇到.*问题",
            r"出现.*错误",
            r"无法.*",
            r".*不工作",
            r".*失败",
            r"怎么解决",
        ],
        "priority": 7,
    },
    IntentType.COMPARISON: {
        "keywords": ["对比", "比较", "区别", "差异", "vs", "versus", "还是"],
        "patterns": [
            r"(.+)和(.+)(的)?(区别|差异|对比)",
            r"(.+)vs(.+)",
            r"比较(.+)和(.+)",
            r"(.+)还是(.+)好",
        ],
        "priority": 6,
    },
    IntentType.CONCEPT_EXPLAIN: {
        "keywords": ["是什么", "什么是", "定义", "概念", "含义", "意思", "原理"],
        "patterns": [
            r"什么是(.+)",
            r"(.+)是什么",
            r"(.+)的(概念|定义|含义|原理)",
            r"介绍一下(.+)",
        ],
        "priority": 5,
    },
    IntentType.HOW_TO: {
        "keywords": ["怎么", "如何", "步骤", "流程", "操作", "配置", "设置", "教程"],
        "patterns": [
            r"怎么(.+)",
            r"如何(.+)",
            r"(.+)的步骤",
            r"(.+)怎么配置",
            r"(.+)操作流程",
        ],
        "priority": 4,
    },
    IntentType.BEST_PRACTICE: {
        "keywords": ["最佳实践", "规范", "标准", "建议", "经验", "注意事项"],
        "patterns": [
            r"(.+)(最佳实践|规范|标准)",
            r"(.+)有什么(建议|注意)",
            r"(.+)的经验",
        ],
        "priority": 3,
    },
    IntentType.CASE_STUDY: {
        "keywords": ["案例", "实例", "成功案例", "应用案例", "客户", "项目"],
        "patterns": [
            r"(.+)(案例|实例)",
            r"有.*客户",
            r"项目经验",
            r"给我.*案例",
            r"找.*案例",
        ],
        "priority": 7,  # 提高优先级
    },
    IntentType.QUOTE: {
        "keywords": ["价格", "报价", "多少钱", "费用", "成本", "预算", "花费", "投资"],
        "patterns": [
            r"(多少钱|什么价格)",
            r"价格(是|多少)",
            r"报价",
            r"费用(是|多少)",
            r"成本(是|多少)",
            r"预算.*多少",
        ],
        "priority": 8,  # 高优先级
    },
}


# ==================== 场景关键词库 ====================

SCENARIO_KEYWORDS = {
    "aoi_inspection": {
        "keywords": [
            "AOI", "视觉检测", "缺陷检测", "外观检测", "工业视觉", "机器视觉",
            "质量检测", "瑕疵", "SPC", "良率", "误检", "漏检", "过杀",
            "PCB检测", "焊点", "贴片", "SMT", "锡膏", "印刷",
            "深度学习", "图像识别", "边缘检测", "算法", "模型训练",
            "相机", "光源", "镜头", "分辨率", "FOV", "景深",
        ],
        "priority": 10,
    },
    "network_security": {
        "keywords": [
            "网络安全", "防火墙", "入侵", "攻击", "漏洞", "加密", "认证",
            "零信任", "SASE", "VPN", "防护", "安全策略", "合规",
        ],
        "priority": 8,
    },
    "cloud_architecture": {
        "keywords": [
            "云", "AWS", "Azure", "阿里云", "架构", "微服务", "容器", "K8s",
            "Kubernetes", "Docker", "DevOps", "CI/CD",
        ],
        "priority": 7,
    },
    "api_design": {
        "keywords": [
            "API", "RESTful", "接口", "GraphQL", "OpenAPI", "Swagger",
            "HTTP", "请求", "响应", "状态码",
        ],
        "priority": 6,
    },
}


class IntentRecognizer:
    """增强的意图识别器 - 统一路由核心"""
    
    def __init__(self, llm_client: Optional[OpenAI] = None, enable_llm: bool = True):
        self.llm_client = llm_client
        self.enable_llm = enable_llm and llm_client is not None
    
    def recognize(
        self,
        query: str,
        history: List[Dict] = None,
        context: Dict = None,
    ) -> IntentResult:
        """
        识别用户意图（完整版 - 包含上下文充分性判断和路由建议）
        
        Args:
            query: 用户输入
            history: 对话历史
            context: 上下文信息（如当前场景、用户画像等）
        
        Returns:
            IntentResult: 意图识别结果（包含路由建议）
        """
        history = history or []
        context = context or {}
        
        # Step 1: 规则引擎识别
        rule_result = self._rule_based_recognition(query)
        
        # Step 2: 场景识别
        scenario_ids, scenario_confidence = self._identify_scenarios(query)
        
        # Step 3: 实体抽取
        entities = self._extract_entities(query)
        
        # Step 4: 判断场景分类
        scene_classification = self._classify_scene(scenario_ids)
        
        # Step 5: 判断是否需要 LLM 增强
        if self.enable_llm and rule_result.confidence < 0.7:
            llm_result = self._llm_enhanced_recognition(
                query, rule_result, history, context
            )
            if llm_result and llm_result.confidence > rule_result.confidence:
                result = llm_result
            else:
                result = rule_result
        else:
            result = rule_result
        
        # 合并结果
        result.scenario_ids = scenario_ids
        result.scene_classification = scene_classification
        result.entities = entities
        
        # Step 6: 判断是否需要澄清
        needs_clarification, reason = self._check_needs_clarification(
            query, result, entities
        )
        result.needs_clarification = needs_clarification
        result.clarification_reason = reason
        
        # Step 7: 分析上下文充分性并生成路由建议（核心新增）
        if self.enable_llm:
            context_sufficiency = self._analyze_context_sufficiency(
                query, result, entities, history
            )
            result.context_sufficiency = context_sufficiency
            result.recommended_action = context_sufficiency.suggested_action
        else:
            # 无 LLM 时使用规则判断路由
            result.recommended_action = self._rule_based_routing(result, entities)
        
        logger.info(
            f"Intent recognized: {result.intent_type.value} "
            f"(conf={result.confidence:.2f}, scenes={scenario_ids}, "
            f"action={result.recommended_action.value})"
        )
        
        return result
    
    def _analyze_context_sufficiency(
        self,
        query: str,
        intent_result: IntentResult,
        entities: Dict,
        history: List[Dict]
    ) -> ContextSufficiency:
        """
        使用 LLM 分析上下文充分性，决定是否需要收集更多信息
        
        核心逻辑：
        - 如果用户问题已经足够具体（如"工控安全案例"），直接搜索
        - 如果用户问题模糊（如"找个案例"），需要收集更多信息
        """
        if not self.llm_client:
            return ContextSufficiency(
                is_sufficient=True,
                optimized_query=query,
                suggested_action=ActionType.DIRECT_RAG
            )
        
        # 构建历史上下文
        history_text = "无"
        if history:
            history_lines = [
                f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')[:100]}"
                for m in history[-3:]
            ]
            history_text = "\n".join(history_lines)
        
        # 实体信息
        entities_text = json.dumps(entities, ensure_ascii=False) if entities else "无"
        
        prompt = f"""分析用户问题，判断是否有足够的信息可以直接回答或检索。

用户问题: {query}
识别的意图: {intent_result.intent_type.value}
提取的实体: {entities_text}
对话历史: {history_text}

请分析:
1. 用户问的是否足够具体，可以直接进行知识库检索？
2. 是否缺少关键信息，需要先收集更多信息？
3. 提取用于检索的优化查询词

判断规则:
- "有没有工控安全的案例" → 足够具体，直接搜索"工控安全 案例"
- "找个案例" → 不够具体，需要问用户想找什么领域的案例
- "AOI8000的价格" → 足够具体，直接搜索
- "帮我算个报价" → 不够具体，需要收集产品型号、数量等信息
- "对比AOI8000和AOI5000" → 足够具体，直接对比

请以 JSON 格式返回:
{{
    "is_sufficient": true/false,
    "extracted_context": {{
        "topic": "提取的主题/领域",
        "product": "提取的产品（没有则为null）",
        "industry": "提取的行业（没有则为null）",
        "keywords": ["关键词列表"]
    }},
    "optimized_query": "用于检索的优化查询语句",
    "missing_fields": ["缺失的关键信息列表"],
    "suggested_action": "direct_rag/need_info/calculate/compare",
    "confidence": 0.0-1.0,
    "reason": "判断理由"
}}

只返回 JSON，不要其他内容。"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            
            content = response.choices[0].message.content.strip()
            logger.debug(f"Context sufficiency analysis: {content[:200]}...")
            
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                result = json.loads(json_match.group())
                
                action_map = {
                    "direct_rag": ActionType.DIRECT_RAG,
                    "need_info": ActionType.NEED_INFO,
                    "calculate": ActionType.CALCULATE,
                    "compare": ActionType.COMPARE,
                    "contribute": ActionType.CONTRIBUTE,
                }
                
                suggested_action = action_map.get(
                    result.get("suggested_action", "direct_rag"),
                    ActionType.DIRECT_RAG
                )
                
                return ContextSufficiency(
                    is_sufficient=result.get("is_sufficient", True),
                    missing_fields=result.get("missing_fields", []),
                    extracted_context=result.get("extracted_context", {}),
                    optimized_query=result.get("optimized_query", query),
                    suggested_action=suggested_action,
                    confidence=float(result.get("confidence", 0.5))
                )
                
        except Exception as e:
            logger.warning(f"Context sufficiency analysis failed: {e}")
        
        # 回退：默认允许直接搜索
        return ContextSufficiency(
            is_sufficient=True,
            optimized_query=query,
            suggested_action=ActionType.DIRECT_RAG
        )
    
    def _rule_based_routing(
        self,
        intent_result: IntentResult,
        entities: Dict
    ) -> ActionType:
        """基于规则的路由决策（无 LLM 时使用）"""
        intent = intent_result.intent_type
        
        # 对比类意图
        if intent == IntentType.COMPARISON:
            return ActionType.COMPARE
        
        # 计算类意图
        if intent == IntentType.CALCULATION:
            # 检查是否有足够的参数
            required = ["capacity", "power", "device_count"]
            if any(p in entities for p in required):
                return ActionType.CALCULATE
            else:
                return ActionType.NEED_INFO
        
        # 报价类意图
        if intent == IntentType.QUOTE:
            # 检查是否有产品信息
            if "product" in entities or intent_result.scenario_ids:
                return ActionType.DIRECT_RAG
            else:
                return ActionType.NEED_INFO
        
        # 案例查询
        if intent == IntentType.CASE_STUDY:
            # 检查是否有主题/行业信息
            if intent_result.scenario_ids or len(intent_result.matched_keywords) > 0:
                return ActionType.DIRECT_RAG
            else:
                return ActionType.NEED_INFO
        
        # 其他类型默认直接 RAG
        return ActionType.DIRECT_RAG
    
    def _rule_based_recognition(self, query: str) -> IntentResult:
        """基于规则的意图识别"""
        query_lower = query.lower()
        
        best_intent = IntentType.GENERAL
        best_score = 0.0
        matched_keywords = []
        
        for intent_type, config in INTENT_PATTERNS.items():
            score = 0.0
            current_matches = []
            
            # 关键词匹配
            for keyword in config["keywords"]:
                if keyword in query_lower:
                    score += 1.0
                    current_matches.append(keyword)
            
            # 正则模式匹配（更高权重）
            for pattern in config["patterns"]:
                if re.search(pattern, query_lower):
                    score += 2.0
                    current_matches.append(f"pattern:{pattern[:20]}")
            
            # 归一化分数并考虑优先级
            if score > 0:
                normalized_score = min(score / 4.0, 1.0) * (config["priority"] / 10.0)
                
                if normalized_score > best_score:
                    best_score = normalized_score
                    best_intent = intent_type
                    matched_keywords = current_matches
        
        return IntentResult(
            intent_type=best_intent,
            confidence=min(best_score + 0.3, 1.0) if best_score > 0 else 0.3,
            matched_keywords=matched_keywords,
        )
    
    def _identify_scenarios(self, query: str) -> Tuple[List[str], float]:
        """识别相关场景"""
        query_lower = query.lower()
        scenario_scores = {}
        
        for scenario_id, config in SCENARIO_KEYWORDS.items():
            score = 0.0
            for keyword in config["keywords"]:
                if keyword.lower() in query_lower:
                    score += 1.0
            
            if score > 0:
                normalized_score = min(score / 3.0, 1.0) * (config["priority"] / 10.0)
                scenario_scores[scenario_id] = normalized_score
        
        # 返回得分最高的场景（最多3个）
        sorted_scenarios = sorted(
            scenario_scores.items(), key=lambda x: x[1], reverse=True
        )[:3]
        
        if not sorted_scenarios:
            return [], 0.0
        
        return (
            [s[0] for s in sorted_scenarios],
            sorted_scenarios[0][1],
        )
    
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """抽取关键实体"""
        entities = {}
        
        # 数值参数抽取
        # 功率: "200W", "200瓦"
        power_match = re.search(r"(\d+(?:\.\d+)?)\s*[wW瓦]", query)
        if power_match:
            entities["power"] = {"value": float(power_match.group(1)), "unit": "W"}
        
        # 精度: "0.01mm", "10微米"
        precision_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(mm|毫米|um|微米|μm)", query
        )
        if precision_match:
            value = float(precision_match.group(1))
            unit = precision_match.group(2)
            if unit in ("um", "微米", "μm"):
                value = value / 1000  # 转换为 mm
            entities["precision"] = {"value": value, "unit": "mm"}
        
        # 产能: "5000片/小时", "100件/分钟"
        capacity_match = re.search(
            r"(\d+)\s*(片|件|个|pcs)\s*/\s*(小时|h|分钟|min|秒|s)", query
        )
        if capacity_match:
            value = int(capacity_match.group(1))
            unit_count = capacity_match.group(2)
            unit_time = capacity_match.group(3)
            entities["capacity"] = {
                "value": value,
                "unit": f"{unit_count}/{unit_time}",
            }
        
        # 价格: "50万", "100万元"
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*万(元)?", query)
        if price_match:
            entities["price"] = {
                "value": float(price_match.group(1)) * 10000,
                "unit": "CNY",
            }
        
        # 设备数量: "几台", "3台"
        count_match = re.search(r"(\d+|几)\s*台", query)
        if count_match:
            count_str = count_match.group(1)
            entities["device_count"] = {
                "value": None if count_str == "几" else int(count_str),
                "is_query": count_str == "几",
            }
        
        return entities
    
    def _classify_scene(self, scenario_ids: List[str]) -> SceneClassification:
        """分类场景类型"""
        if not scenario_ids:
            return SceneClassification.GENERAL
        elif len(scenario_ids) == 1:
            return SceneClassification.SINGLE_SCENE
        else:
            return SceneClassification.MULTI_SCENE
    
    def _check_needs_clarification(
        self,
        query: str,
        intent_result: IntentResult,
        entities: Dict,
    ) -> Tuple[bool, str]:
        """判断是否需要澄清"""
        
        # 短问题 + 复杂意图需要澄清
        if len(query) < 15 and intent_result.intent_type in (
            IntentType.SOLUTION_RECOMMENDATION,
            IntentType.CALCULATION,
        ):
            return True, "query_too_short"
        
        # 方案推荐但没有明确场景
        if (
            intent_result.intent_type == IntentType.SOLUTION_RECOMMENDATION
            and intent_result.scene_classification == SceneClassification.GENERAL
        ):
            return True, "no_scenario_identified"
        
        # 计算类问题但参数不完整
        if intent_result.intent_type == IntentType.CALCULATION:
            required_params = ["capacity", "power"]
            has_any = any(p in entities for p in required_params)
            if not has_any:
                return True, "missing_calculation_params"
        
        # 包含模糊词汇
        vague_words = ["大概", "差不多", "左右", "一般", "通常"]
        if any(word in query for word in vague_words):
            return True, "vague_expression"
        
        return False, ""
    
    def _llm_enhanced_recognition(
        self,
        query: str,
        rule_result: IntentResult,
        history: List[Dict],
        context: Dict,
    ) -> Optional[IntentResult]:
        """LLM 增强的意图识别"""
        if not self.llm_client:
            return None
        
        intent_types_desc = "\n".join([
            f"- {it.value}: {self._get_intent_description(it)}"
            for it in IntentType
        ])
        
        prompt = f"""分析用户意图。

用户问题: {query}

对话历史（最近3轮）:
{self._format_history(history[-3:]) if history else "无"}

可选意图类型:
{intent_types_desc}

请以JSON格式返回分析结果:
{{
    "intent_type": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "reasoning": "判断理由",
    "key_entities": ["关键实体列表"]
}}

只返回JSON，不要其他内容。"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model="qwen-turbo",  # 使用快速模型
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
            
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                result = json.loads(json_match.group())
                
                intent_type = IntentType(result.get("intent_type", "general"))
                confidence = float(result.get("confidence", 0.5))
                
                return IntentResult(
                    intent_type=intent_type,
                    confidence=confidence,
                    matched_keywords=result.get("key_entities", []),
                    raw_llm_analysis=result,
                )
        except Exception as e:
            logger.warning(f"LLM intent recognition failed: {e}")
        
        return None
    
    def _get_intent_description(self, intent_type: IntentType) -> str:
        """获取意图类型描述"""
        descriptions = {
            IntentType.SOLUTION_RECOMMENDATION: "寻求解决方案或产品推荐",
            IntentType.TECHNICAL_QA: "技术细节问答",
            IntentType.TROUBLESHOOTING: "问题诊断和故障排除",
            IntentType.COMPARISON: "比较多个选项",
            IntentType.BEST_PRACTICE: "寻求最佳实践建议",
            IntentType.CONCEPT_EXPLAIN: "概念解释或定义",
            IntentType.HOW_TO: "操作步骤指南",
            IntentType.PARAMETER_QUERY: "查询具体参数或规格",
            IntentType.CALCULATION: "需要计算或选型",
            IntentType.CASE_STUDY: "寻找案例或实例",
            IntentType.QUOTE: "咨询价格或报价",
            IntentType.GENERAL: "一般性问题",
        }
        return descriptions.get(intent_type, "")
    
    def _format_history(self, history: List[Dict]) -> str:
        """格式化对话历史"""
        if not history:
            return "无"
        
        lines = []
        for msg in history:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:100]
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)


# ==================== 模块级便捷函数 ====================

_default_recognizer: Optional[IntentRecognizer] = None


def get_intent_recognizer(llm_client: Optional[OpenAI] = None) -> IntentRecognizer:
    """获取意图识别器实例"""
    global _default_recognizer
    
    if _default_recognizer is None:
        _default_recognizer = IntentRecognizer(llm_client=llm_client)
    elif llm_client and not _default_recognizer.llm_client:
        _default_recognizer.llm_client = llm_client
        _default_recognizer.enable_llm = True
    
    return _default_recognizer


def recognize_intent(
    query: str,
    history: List[Dict] = None,
    context: Dict = None,
    llm_client: Optional[OpenAI] = None,
) -> IntentResult:
    """便捷函数：识别用户意图"""
    recognizer = get_intent_recognizer(llm_client)
    return recognizer.recognize(query, history, context)

