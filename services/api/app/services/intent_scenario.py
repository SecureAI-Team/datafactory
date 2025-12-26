"""
意图识别和场景匹配服务
"""
import re
import json
import logging
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """意图类型"""
    SOLUTION_RECOMMENDATION = "solution_recommendation"  # 方案推荐
    TECHNICAL_QA = "technical_qa"                        # 技术问答
    TROUBLESHOOTING = "troubleshooting"                  # 故障诊断
    COMPARISON = "comparison"                            # 对比分析
    BEST_PRACTICE = "best_practice"                      # 最佳实践
    CONCEPT_EXPLAIN = "concept_explain"                  # 概念解释
    HOW_TO = "how_to"                                    # 操作指南
    GENERAL = "general"                                  # 通用


@dataclass
class IntentResult:
    """意图识别结果"""
    intent_type: IntentType
    confidence: float
    scenario_id: Optional[str] = None
    matched_keywords: List[str] = None
    context: Dict[str, Any] = None


@dataclass
class ScenarioConfig:
    """场景配置"""
    id: str
    name: str
    domain: str
    keywords: List[str]
    intents: List[IntentType]
    prompt_template: str
    retrieval_config: Dict


# ==================== 意图识别规则 ====================

INTENT_RULES = {
    IntentType.SOLUTION_RECOMMENDATION: {
        "keywords": ["推荐", "方案", "解决方案", "怎么选", "选型", "建议", "哪个好", "如何实现"],
        "patterns": [
            r"推荐.*方案",
            r"有.*解决方案",
            r"怎么.*实现",
            r"如何.*部署",
            r"选.*还是.*",
        ],
        "examples": [
            "推荐一个网络安全方案",
            "有什么好的纵深防御解决方案",
            "零信任和SASE哪个更适合我们",
        ]
    },
    IntentType.TROUBLESHOOTING: {
        "keywords": ["问题", "故障", "报错", "失败", "不工作", "异常", "错误", "无法"],
        "patterns": [
            r"遇到.*问题",
            r"出现.*错误",
            r"无法.*",
            r".*不工作",
        ],
        "examples": [
            "防火墙配置后无法访问",
            "VPN连接失败怎么办",
        ]
    },
    IntentType.COMPARISON: {
        "keywords": ["对比", "比较", "区别", "差异", "vs", "versus", "和.*区别"],
        "patterns": [
            r"(.+)和(.+)(的)?(区别|差异|对比)",
            r"(.+)vs(.+)",
            r"比较(.+)和(.+)",
        ],
        "examples": [
            "零信任和传统VPN的区别",
            "SASE vs CASB",
        ]
    },
    IntentType.CONCEPT_EXPLAIN: {
        "keywords": ["是什么", "什么是", "定义", "概念", "含义", "意思"],
        "patterns": [
            r"什么是(.+)",
            r"(.+)是什么",
            r"(.+)的(概念|定义|含义)",
        ],
        "examples": [
            "什么是纵深防御",
            "零信任是什么意思",
        ]
    },
    IntentType.HOW_TO: {
        "keywords": ["怎么", "如何", "步骤", "流程", "操作", "配置", "设置"],
        "patterns": [
            r"怎么(.+)",
            r"如何(.+)",
            r"(.+)的步骤",
            r"(.+)怎么配置",
        ],
        "examples": [
            "怎么配置防火墙规则",
            "如何部署零信任架构",
        ]
    },
    IntentType.BEST_PRACTICE: {
        "keywords": ["最佳实践", "规范", "标准", "建议", "经验", "注意事项"],
        "patterns": [
            r"(.+)(最佳实践|规范|标准)",
            r"(.+)有什么(建议|注意)",
        ],
        "examples": [
            "网络安全最佳实践",
            "API设计规范",
        ]
    },
}


# ==================== 场景配置 ====================

SCENARIO_CONFIGS = {
    "network_security": ScenarioConfig(
        id="network_security",
        name="网络安全",
        domain="安全",
        keywords=["网络安全", "防火墙", "入侵", "攻击", "漏洞", "加密", "认证", "授权"],
        intents=[IntentType.SOLUTION_RECOMMENDATION, IntentType.TECHNICAL_QA, IntentType.TROUBLESHOOTING],
        prompt_template="""你是一位资深的网络安全专家，擅长为企业提供安全解决方案咨询。

在回答时请注意：
1. 优先考虑安全性和合规性要求
2. 结合企业实际情况给出可落地的建议
3. 说明方案的优缺点和适用场景
4. 提供成本和复杂度的参考
5. 引用具体的安全标准或最佳实践""",
        retrieval_config={
            "boost_fields": {"solution_name": 2.0, "security_level": 1.5},
            "filter_tags": ["security", "network"],
        }
    ),
    
    "aoi_inspection": ScenarioConfig(
        id="aoi_inspection",
        name="工业AOI视觉检测",
        domain="工业智能",
        keywords=[
            "AOI", "视觉检测", "缺陷检测", "外观检测", "工业视觉", "机器视觉",
            "质量检测", "瑕疵", "SPC", "良率", "误检", "漏检", "过杀",
            "PCB检测", "焊点", "贴片", "SMT", "锡膏", "印刷",
            "深度学习", "图像识别", "边缘检测", "算法", "模型训练",
            "相机", "光源", "镜头", "分辨率", "FOV", "景深",
        ],
        intents=[IntentType.SOLUTION_RECOMMENDATION, IntentType.TECHNICAL_QA, IntentType.TROUBLESHOOTING, IntentType.HOW_TO],
        prompt_template="""你是一位工业AOI视觉检测专家，精通机器视觉系统设计和缺陷检测算法。

在回答时请注意：
1. 结合具体产品类型（PCB、电子元器件、外观件等）给出针对性建议
2. 考虑检测精度、速度、成本之间的平衡
3. 区分传统图像处理算法和深度学习方案的适用场景
4. 包含硬件选型建议（相机、光源、镜头）
5. 关注误检率、漏检率、过杀率等关键指标
6. 提供可落地的实施步骤和注意事项
7. 引用具体的行业标准（如IPC标准）""",
        retrieval_config={
            "boost_fields": {"product_type": 2.0, "defect_type": 1.5, "algorithm": 1.3},
            "filter_tags": ["aoi", "vision", "inspection", "industrial"],
        }
    ),
    
    "cloud_architecture": ScenarioConfig(
        id="cloud_architecture",
        name="云架构",
        domain="云计算",
        keywords=["云", "AWS", "Azure", "阿里云", "架构", "微服务", "容器", "K8s"],
        intents=[IntentType.SOLUTION_RECOMMENDATION, IntentType.HOW_TO, IntentType.BEST_PRACTICE],
        prompt_template="""你是一位云架构专家，熟悉主流云平台和现代架构设计。

在回答时请注意：
1. 考虑可扩展性、高可用和成本优化
2. 说明不同云平台的差异
3. 提供架构图或关键组件说明
4. 给出迁移或实施的建议步骤""",
        retrieval_config={
            "boost_fields": {"cloud_provider": 1.5},
            "filter_tags": ["cloud", "architecture"],
        }
    ),
    
    "api_design": ScenarioConfig(
        id="api_design",
        name="API设计",
        domain="开发",
        keywords=["API", "RESTful", "接口", "GraphQL", "OpenAPI", "Swagger"],
        intents=[IntentType.CONCEPT_EXPLAIN, IntentType.BEST_PRACTICE, IntentType.HOW_TO],
        prompt_template="""你是一位 API 设计专家，精通 RESTful、GraphQL 等 API 设计规范。

在回答时请注意：
1. 遵循 API 设计最佳实践
2. 提供具体的示例代码或规范
3. 说明不同设计选择的权衡
4. 考虑安全性、版本控制、文档化""",
        retrieval_config={
            "boost_fields": {"api_standard": 1.5},
            "filter_tags": ["api", "development"],
        }
    ),
}


# ==================== 场景化 Prompt 模板库 ====================

PROMPT_TEMPLATES = {
    # 方案推荐场景
    (IntentType.SOLUTION_RECOMMENDATION, "network_security"): {
        "system_prompt": """你是一位网络安全解决方案顾问。用户正在寻找安全解决方案。

请基于用户需求和知识库内容，推荐合适的解决方案，包括：
1. 推荐的方案名称和概述
2. 方案的核心能力和特点
3. 适用场景和目标用户
4. 部署复杂度和成本估算
5. 与其他方案的对比优势

如果有多个可选方案，请分别介绍并给出选择建议。""",
        
        "context_template": """【用户需求】
{user_query}

【用户上下文】
{user_context}

【可选解决方案】
{solutions}

【相关材料摘要】
{materials}""",
        
        "output_format": """请按以下格式回答：

## 推荐方案

### 方案一：{方案名称}
- **概述**: 
- **核心能力**: 
- **适用场景**: 
- **部署复杂度**: 低/中/高
- **成本估算**: 

### 方案二：... (如有)

## 选择建议
基于您的需求，建议选择...

## 参考材料
- [材料1]
- [材料2]"""
    },
    
    # 技术问答场景
    (IntentType.TECHNICAL_QA, "default"): {
        "system_prompt": """你是一位技术专家。请基于知识库内容准确回答技术问题。

回答要求：
1. 准确引用知识库内容
2. 给出清晰的解释和示例
3. 如有不确定，请明确说明
4. 建议进一步学习的资源""",
        
        "context_template": """【技术问题】
{user_query}

【相关知识】
{retrieved_context}""",
    },
    
    # 对比分析场景
    (IntentType.COMPARISON, "default"): {
        "system_prompt": """你是一位技术分析专家。请对用户提出的多个技术/方案进行客观对比。

对比维度：
1. 功能特性
2. 技术架构
3. 适用场景
4. 优缺点
5. 成本和复杂度
6. 成熟度和生态

请保持客观中立，不偏向任何一方。""",
        
        "output_format": """## 对比分析：{A} vs {B}

| 维度 | {A} | {B} |
|------|-----|-----|
| 功能特性 | | |
| 技术架构 | | |
| 适用场景 | | |
| 优点 | | |
| 缺点 | | |
| 成本 | | |

## 总结建议
根据您的具体需求..."""
    },
    
    # 故障诊断场景
    (IntentType.TROUBLESHOOTING, "default"): {
        "system_prompt": """你是一位技术支持专家。请帮助用户诊断和解决技术问题。

诊断步骤：
1. 理解问题现象
2. 分析可能原因
3. 提供排查步骤
4. 给出解决方案
5. 预防措施建议

请一步步引导用户解决问题。""",
        
        "output_format": """## 问题诊断

### 问题描述
{用户描述的问题}

### 可能原因
1. 
2. 
3. 

### 排查步骤
1. 首先检查...
2. 然后验证...
3. 

### 解决方案
根据排查结果，建议...

### 预防措施
为避免类似问题..."""
    },
    
    # ==================== 工业AOI视觉检测场景 ====================
    
    # AOI 方案推荐
    (IntentType.SOLUTION_RECOMMENDATION, "aoi_inspection"): {
        "system_prompt": """你是一位工业AOI视觉检测解决方案专家。用户正在寻找视觉检测方案。

请基于用户需求和知识库内容，推荐合适的AOI解决方案，包括：
1. 检测方案概述（传统算法/深度学习/混合方案）
2. 硬件配置建议（相机型号、光源类型、镜头规格）
3. 软件/算法方案（检测算法、数据标注、模型训练）
4. 关键性能指标（检测精度、速度、误检率/漏检率）
5. 部署方案和成本估算
6. 与其他方案的对比

请结合具体的产品类型和缺陷类型给出针对性建议。""",
        
        "context_template": """【检测需求】
{user_query}

【产品信息】
{user_context}

【可选检测方案】
{solutions}

【相关技术文档】
{materials}""",
        
        "output_format": """## AOI检测方案推荐

### 需求分析
- 产品类型：
- 检测项目：
- 精度要求：
- 节拍要求：

### 推荐方案

#### 方案一：{方案名称}
- **算法方案**: 传统图像处理 / 深度学习 / 混合
- **硬件配置**: 
  - 相机：
  - 光源：
  - 镜头：
- **检测能力**: 
- **预估指标**: 误检率 < X%, 漏检率 < Y%
- **部署周期**: 
- **成本估算**: 

#### 方案二：... (如有)

### 选型建议
根据您的需求特点，建议选择...

### 实施步骤
1. 样品测试
2. 算法开发
3. 硬件集成
4. 产线验证
5. 量产部署

### 参考案例
- [案例1]
- [案例2]"""
    },
    
    # AOI 故障诊断
    (IntentType.TROUBLESHOOTING, "aoi_inspection"): {
        "system_prompt": """你是一位AOI设备维护专家。请帮助用户诊断和解决AOI检测中的问题。

常见问题类型：
1. 误检过高（过杀）- 将良品判为不良
2. 漏检 - 未检出真实缺陷
3. 图像质量问题 - 模糊、曝光异常
4. 检测速度问题 - 节拍不达标
5. 软件/算法问题 - 程序异常、模型失效

请结合具体现象给出排查建议。""",
        
        "output_format": """## AOI问题诊断

### 问题现象
{问题描述}

### 可能原因分析
| 原因类别 | 具体原因 | 可能性 |
|---------|---------|-------|
| 硬件 | | |
| 光源 | | |
| 算法 | | |
| 环境 | | |

### 排查步骤
1. 检查图像质量...
2. 验证光源状态...
3. 确认算法参数...
4. 

### 解决方案
根据排查结果，建议...

### 预防措施
- 定期校准...
- 参数备份..."""
    },
    
    # AOI 操作指南
    (IntentType.HOW_TO, "aoi_inspection"): {
        "system_prompt": """你是一位AOI应用工程师。请提供AOI系统的操作和配置指南。

回答时请注意：
1. 步骤清晰，有先后顺序
2. 包含关键参数设置
3. 说明注意事项和常见错误
4. 提供验证方法""",
        
        "output_format": """## 操作指南：{操作主题}

### 前置条件
- 
- 

### 操作步骤
1. **步骤一**: 
   - 具体操作：
   - 参数设置：
   - 注意事项：

2. **步骤二**: 
   ...

### 验证方法
- 

### 常见问题
Q: 
A: """
    },
}


# ==================== 意图识别服务 ====================

class IntentRecognizer:
    """意图识别器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.rules = INTENT_RULES
    
    def recognize(self, query: str, context: Dict = None) -> IntentResult:
        """
        识别用户意图
        先用规则匹配，如果不确定则用 LLM
        """
        # 1. 规则匹配
        rule_result = self._match_by_rules(query)
        
        if rule_result.confidence >= 0.7:
            return rule_result
        
        # 2. LLM 增强（如果规则置信度不够）
        if self.llm_client and rule_result.confidence < 0.5:
            llm_result = self._recognize_by_llm(query, context)
            if llm_result.confidence > rule_result.confidence:
                return llm_result
        
        return rule_result
    
    def _match_by_rules(self, query: str) -> IntentResult:
        """基于规则匹配意图"""
        best_match = None
        best_score = 0
        matched_keywords = []
        
        for intent_type, rule in self.rules.items():
            score = 0
            keywords_found = []
            
            # 关键词匹配
            for keyword in rule["keywords"]:
                if keyword in query:
                    score += 1
                    keywords_found.append(keyword)
            
            # 正则模式匹配
            for pattern in rule["patterns"]:
                if re.search(pattern, query, re.IGNORECASE):
                    score += 2
            
            # 归一化分数
            max_possible = len(rule["keywords"]) + len(rule["patterns"]) * 2
            normalized_score = score / max_possible if max_possible > 0 else 0
            
            if normalized_score > best_score:
                best_score = normalized_score
                best_match = intent_type
                matched_keywords = keywords_found
        
        if best_match is None:
            best_match = IntentType.GENERAL
            best_score = 0.3
        
        return IntentResult(
            intent_type=best_match,
            confidence=min(best_score, 1.0),
            matched_keywords=matched_keywords,
        )
    
    def _recognize_by_llm(self, query: str, context: Dict = None) -> IntentResult:
        """使用 LLM 识别意图"""
        if not self.llm_client:
            return IntentResult(intent_type=IntentType.GENERAL, confidence=0.3)
        
        intent_descriptions = "\n".join([
            f"- {it.value}: {it.name}" for it in IntentType
        ])
        
        prompt = f"""分析以下用户问题的意图类型。

可选意图类型：
{intent_descriptions}

用户问题：{query}

请返回 JSON 格式：
{{"intent_type": "意图类型", "confidence": 0.0-1.0, "reason": "判断理由"}}"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            result = json.loads(response.choices[0].message.content)
            return IntentResult(
                intent_type=IntentType(result["intent_type"]),
                confidence=result["confidence"],
                context={"reason": result.get("reason")},
            )
        except Exception as e:
            logger.error(f"LLM intent recognition failed: {e}")
            return IntentResult(intent_type=IntentType.GENERAL, confidence=0.3)


# ==================== 场景匹配服务 ====================

class ScenarioMatcher:
    """场景匹配器"""
    
    def __init__(self):
        self.scenarios = SCENARIO_CONFIGS
    
    def match(self, query: str, intent: IntentResult) -> Optional[ScenarioConfig]:
        """根据查询和意图匹配场景"""
        best_match = None
        best_score = 0
        
        for scenario_id, config in self.scenarios.items():
            score = 0
            
            # 检查意图是否适用
            if intent.intent_type in config.intents:
                score += 1
            
            # 关键词匹配
            for keyword in config.keywords:
                if keyword.lower() in query.lower():
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = config
        
        return best_match
    
    def get_prompt_template(self, intent: IntentType, scenario_id: str = None) -> Dict:
        """获取对应的 Prompt 模板"""
        # 优先查找 (意图, 场景) 组合
        key = (intent, scenario_id)
        if key in PROMPT_TEMPLATES:
            return PROMPT_TEMPLATES[key]
        
        # 回退到 (意图, default)
        key = (intent, "default")
        if key in PROMPT_TEMPLATES:
            return PROMPT_TEMPLATES[key]
        
        # 最终回退
        return {
            "system_prompt": "你是一个专业的AI助手，请基于知识库内容回答用户问题。",
            "context_template": "【问题】{user_query}\n【参考内容】{retrieved_context}",
        }


# ==================== 便捷函数 ====================

_recognizer = IntentRecognizer()
_matcher = ScenarioMatcher()


def recognize_intent(query: str, context: Dict = None, llm_client=None) -> IntentResult:
    """识别意图"""
    if llm_client:
        _recognizer.llm_client = llm_client
    return _recognizer.recognize(query, context)


def match_scenario(query: str, intent: IntentResult) -> Optional[ScenarioConfig]:
    """匹配场景"""
    return _matcher.match(query, intent)


def get_prompt_for_intent_scenario(intent: IntentType, scenario_id: str = None) -> Dict:
    """获取 Prompt 模板"""
    return _matcher.get_prompt_template(intent, scenario_id)

