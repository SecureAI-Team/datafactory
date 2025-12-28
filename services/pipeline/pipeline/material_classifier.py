"""
材料类型分类器
根据文件名和内容识别材料类型，并推断适用的意图类型
增强版：支持 ku_type、product_id、行业标签等
"""
import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class MaterialClassification:
    """材料分类结果"""
    material_type: str
    intent_types: List[str]
    confidence: float
    matched_patterns: List[str]
    
    # Phase 6 新增字段
    ku_type: str = "core"  # core/case/quote/solution/whitepaper/faq
    product_id: Optional[str] = None
    industry_tags: List[str] = field(default_factory=list)
    use_case_tags: List[str] = field(default_factory=list)


# 材料类型定义
class MaterialType:
    WHITEPAPER = "whitepaper"       # 白皮书
    CASE_STUDY = "case_study"       # 客户案例
    TUTORIAL = "tutorial"           # 操作教程
    FAQ = "faq"                     # 常见问题
    COMPARISON = "comparison"       # 对比分析
    ARCHITECTURE = "architecture"   # 架构文档
    DATASHEET = "datasheet"         # 产品规格
    TROUBLESHOOTING = "troubleshooting"  # 故障排除
    GENERAL = "general"             # 通用文档


# 意图类型定义
class IntentType:
    SOLUTION_RECOMMENDATION = "solution_recommendation"
    TECHNICAL_QA = "technical_qa"
    TROUBLESHOOTING = "troubleshooting"
    COMPARISON = "comparison"
    CONCEPT_EXPLAIN = "concept_explain"
    BEST_PRACTICE = "best_practice"
    HOW_TO = "how_to"


# 文件名关键词匹配规则
FILENAME_PATTERNS = {
    MaterialType.WHITEPAPER: [
        r'白皮书', r'whitepaper', r'white_paper', r'技术白皮书',
    ],
    MaterialType.CASE_STUDY: [
        r'案例', r'case', r'case_study', r'客户案例', r'成功案例',
        r'应用案例', r'实践案例',
    ],
    MaterialType.TUTORIAL: [
        r'教程', r'tutorial', r'指南', r'guide', r'手册', r'manual',
        r'入门', r'getting_started', r'quickstart',
    ],
    MaterialType.FAQ: [
        r'faq', r'常见问题', r'问答', r'q\s*&\s*a', r'qa',
    ],
    MaterialType.COMPARISON: [
        r'对比', r'比较', r'comparison', r'compare', r'vs',
        r'选型', r'evaluation',
    ],
    MaterialType.ARCHITECTURE: [
        r'架构', r'architecture', r'设计', r'design', r'拓扑',
        r'部署', r'deployment',
    ],
    MaterialType.DATASHEET: [
        r'规格', r'spec', r'datasheet', r'参数', r'性能',
        r'技术参数', r'产品规格',
    ],
    MaterialType.TROUBLESHOOTING: [
        r'故障', r'troubleshoot', r'排错', r'问题解决',
        r'错误', r'error', r'修复', r'fix',
    ],
}

# 内容关键词匹配规则（权重较低）
CONTENT_PATTERNS = {
    MaterialType.WHITEPAPER: [
        r'摘要[:：]', r'abstract', r'背景介绍', r'市场分析',
        r'技术趋势', r'行业洞察',
    ],
    MaterialType.CASE_STUDY: [
        r'客户背景', r'客户需求', r'解决方案', r'实施效果',
        r'客户收益', r'案例背景', r'项目背景',
    ],
    MaterialType.TUTORIAL: [
        r'第[一二三四五六七八九十\d]+步', r'步骤\s*[1-9]',
        r'操作步骤', r'如何操作', r'使用方法', r'操作指南',
        r'step\s*\d+', r'首先.*然后.*最后',
    ],
    MaterialType.FAQ: [
        r'问[:：]', r'答[:：]', r'q\s*[:：]', r'a\s*[:：]',
        r'常见问题', r'为什么.*\?', r'怎么.*\?', r'如何.*\?',
    ],
    MaterialType.COMPARISON: [
        r'对比分析', r'优缺点', r'区别', r'差异',
        r'方案[一二三AB12]', r'vs\.?', r'比较结果',
    ],
    MaterialType.ARCHITECTURE: [
        r'架构图', r'系统架构', r'部署架构', r'技术架构',
        r'拓扑图', r'组件', r'模块', r'服务层',
    ],
    MaterialType.DATASHEET: [
        r'技术规格', r'产品参数', r'性能指标', r'规格参数',
        r'工作电压', r'功率', r'尺寸', r'重量',
        r'精度', r'分辨率', r'速度',
    ],
    MaterialType.TROUBLESHOOTING: [
        r'故障现象', r'错误信息', r'解决方法', r'排查步骤',
        r'常见故障', r'问题原因', r'修复方案',
    ],
}

# 材料类型到意图类型的映射
MATERIAL_TO_INTENT = {
    MaterialType.WHITEPAPER: [IntentType.SOLUTION_RECOMMENDATION, IntentType.CONCEPT_EXPLAIN],
    MaterialType.CASE_STUDY: [IntentType.SOLUTION_RECOMMENDATION, IntentType.BEST_PRACTICE],
    MaterialType.TUTORIAL: [IntentType.HOW_TO, IntentType.TECHNICAL_QA],
    MaterialType.FAQ: [IntentType.TROUBLESHOOTING, IntentType.TECHNICAL_QA],
    MaterialType.COMPARISON: [IntentType.COMPARISON],
    MaterialType.ARCHITECTURE: [IntentType.CONCEPT_EXPLAIN, IntentType.TECHNICAL_QA],
    MaterialType.DATASHEET: [IntentType.TECHNICAL_QA, IntentType.COMPARISON],
    MaterialType.TROUBLESHOOTING: [IntentType.TROUBLESHOOTING],
    MaterialType.GENERAL: [IntentType.TECHNICAL_QA],
}

# Phase 6: 材料类型到 KU 类型的映射
MATERIAL_TO_KU_TYPE = {
    MaterialType.WHITEPAPER: "whitepaper",
    MaterialType.CASE_STUDY: "case",
    MaterialType.TUTORIAL: "core",
    MaterialType.FAQ: "faq",
    MaterialType.COMPARISON: "core",
    MaterialType.ARCHITECTURE: "core",
    MaterialType.DATASHEET: "core",
    MaterialType.TROUBLESHOOTING: "faq",
    MaterialType.GENERAL: "core",
}

# 报价相关关键词（用于识别 quote 类型）
QUOTE_PATTERNS = [
    r'报价', r'价格', r'price', r'quote', r'quotation',
    r'pricing', r'费用', r'cost', r'定价', r'价目',
    r'折扣', r'discount', r'优惠',
]

# 解决方案关键词（用于识别 solution 类型）
SOLUTION_PATTERNS = [
    r'解决方案', r'solution', r'方案书', r'proposal',
    r'实施方案', r'技术方案', r'整体方案',
]

# 行业关键词映射
INDUSTRY_KEYWORDS = {
    "金融": ["金融", "银行", "证券", "保险", "基金", "finance", "banking"],
    "制造": ["制造", "工厂", "生产", "manufacturing", "factory", "产线"],
    "医疗": ["医疗", "医院", "健康", "医药", "healthcare", "medical"],
    "零售": ["零售", "电商", "商超", "retail", "ecommerce"],
    "能源": ["能源", "电力", "石油", "电网", "energy", "power"],
    "交通": ["交通", "物流", "运输", "logistics", "transport"],
    "教育": ["教育", "学校", "培训", "education", "school"],
    "政府": ["政府", "政务", "公安", "government", "public"],
    "通信": ["通信", "电信", "运营商", "telecom", "carrier"],
    "互联网": ["互联网", "IT", "软件", "internet", "tech"],
}

# 使用场景关键词映射
USE_CASE_KEYWORDS = {
    "质量检测": ["质检", "检测", "AOI", "缺陷", "inspection", "quality"],
    "安全防护": ["安全", "防护", "监控", "security", "protection"],
    "数据分析": ["数据分析", "BI", "报表", "analytics", "dashboard"],
    "自动化": ["自动化", "RPA", "机器人", "automation"],
    "智能客服": ["客服", "问答", "chatbot", "support"],
    "运维监控": ["运维", "监控", "告警", "ops", "monitor"],
    "供应链": ["供应链", "采购", "库存", "supply", "inventory"],
    "研发": ["研发", "开发", "设计", "R&D", "development"],
}


def classify_by_filename(filename: str) -> Tuple[Optional[str], List[str], float]:
    """
    根据文件名分类
    
    Returns:
        (材料类型, 匹配的模式, 置信度)
    """
    filename_lower = filename.lower()
    
    for material_type, patterns in FILENAME_PATTERNS.items():
        matched = []
        for pattern in patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                matched.append(pattern)
        
        if matched:
            # 文件名匹配置信度较高
            confidence = min(0.9, 0.6 + 0.1 * len(matched))
            return material_type, matched, confidence
    
    return None, [], 0.0


def classify_by_content(content: str, max_length: int = 5000) -> Tuple[Optional[str], List[str], float]:
    """
    根据内容分类
    
    Returns:
        (材料类型, 匹配的模式, 置信度)
    """
    # 只检查前N个字符
    content_sample = content[:max_length].lower()
    
    scores = {}
    matched_patterns = {}
    
    for material_type, patterns in CONTENT_PATTERNS.items():
        matched = []
        for pattern in patterns:
            matches = re.findall(pattern, content_sample, re.IGNORECASE)
            if matches:
                matched.extend(matches[:3])  # 最多记录3个匹配
        
        if matched:
            # 根据匹配数量计算分数
            scores[material_type] = len(matched)
            matched_patterns[material_type] = matched
    
    if not scores:
        return None, [], 0.0
    
    # 选择得分最高的类型
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    
    # 内容匹配置信度较低
    confidence = min(0.7, 0.3 + 0.1 * best_score)
    
    return best_type, matched_patterns[best_type], confidence


def classify_material(
    filename: str,
    content: str = "",
    metadata: dict = None,
    filepath: str = ""
) -> MaterialClassification:
    """
    综合分类材料类型
    
    Args:
        filename: 文件名
        content: 文件内容（可选）
        metadata: 元数据（可选，包含手动标注）
        filepath: 文件路径（可选，用于提取产品信息）
        
    Returns:
        MaterialClassification 分类结果
    """
    # 优先使用元数据中的手动标注
    if metadata and metadata.get("material_type"):
        manual_type = metadata["material_type"]
        intent_types = MATERIAL_TO_INTENT.get(manual_type, [IntentType.TECHNICAL_QA])
        ku_type = metadata.get("ku_type") or determine_ku_type(manual_type, content)
        product_id = metadata.get("product_id") or extract_product_id(filename, filepath, content)
        industry_tags = metadata.get("industry_tags") or extract_industry_tags(content, filename)
        use_case_tags = metadata.get("use_case_tags") or extract_use_case_tags(content, filename)
        
        return MaterialClassification(
            material_type=manual_type,
            intent_types=intent_types,
            confidence=1.0,
            matched_patterns=["manual_annotation"],
            ku_type=ku_type,
            product_id=product_id,
            industry_tags=industry_tags,
            use_case_tags=use_case_tags
        )
    
    # 文件名分类
    filename_type, filename_patterns, filename_conf = classify_by_filename(filename)
    
    # 内容分类
    content_type, content_patterns, content_conf = classify_by_content(content) if content else (None, [], 0.0)
    
    # 合并结果
    if filename_type and filename_conf >= content_conf:
        # 文件名优先
        final_type = filename_type
        final_conf = filename_conf
        final_patterns = filename_patterns
    elif content_type:
        # 内容分类
        final_type = content_type
        final_conf = content_conf
        final_patterns = content_patterns
    else:
        # 默认类型
        final_type = MaterialType.GENERAL
        final_conf = 0.5
        final_patterns = []
    
    # 获取意图类型
    intent_types = MATERIAL_TO_INTENT.get(final_type, [IntentType.TECHNICAL_QA])
    
    # Phase 6: 提取增强字段
    ku_type = determine_ku_type(final_type, content)
    product_id = extract_product_id(filename, filepath, content)
    industry_tags = extract_industry_tags(content, filename)
    use_case_tags = extract_use_case_tags(content, filename)
    
    return MaterialClassification(
        material_type=final_type,
        intent_types=intent_types,
        confidence=final_conf,
        matched_patterns=final_patterns,
        ku_type=ku_type,
        product_id=product_id,
        industry_tags=industry_tags,
        use_case_tags=use_case_tags
    )


def extract_product_id(filename: str, filepath: str = "", content: str = "") -> Optional[str]:
    """
    从文件名、路径或内容中提取产品ID
    
    策略:
    1. 从路径提取: /产品A/xxx.pdf -> 产品A
    2. 从文件名提取: 产品A_白皮书.pdf -> 产品A
    3. 从内容提取产品名称
    """
    product_id = None
    
    # 1. 从路径提取（假设格式: .../products/产品名/...）
    if filepath:
        path_parts = filepath.replace("\\", "/").split("/")
        for i, part in enumerate(path_parts):
            if part.lower() in ["products", "产品", "product"]:
                if i + 1 < len(path_parts):
                    product_id = path_parts[i + 1]
                    break
    
    # 2. 从文件名提取（格式: 产品名_类型.pdf 或 产品名-类型.pdf）
    if not product_id:
        # 去掉扩展名
        name_without_ext = re.sub(r'\.[^.]+$', '', filename)
        # 尝试分割
        parts = re.split(r'[_\-\s]+', name_without_ext)
        if len(parts) >= 2:
            # 检查是否有明确的类型后缀
            type_suffixes = ['白皮书', '案例', '报价', '方案', '规格', 'whitepaper', 'case', 'quote', 'datasheet']
            for suffix in type_suffixes:
                if parts[-1].lower() == suffix.lower() or suffix in parts[-1].lower():
                    # 产品名是除了类型后缀外的部分
                    product_id = '_'.join(parts[:-1])
                    break
    
    # 3. 从内容提取（查找"产品名称"或类似模式）
    if not product_id and content:
        content_sample = content[:2000]
        patterns = [
            r'产品名称[：:]\s*([^\n\r,，]{2,30})',
            r'Product\s*Name[：:]\s*([^\n\r,，]{2,30})',
            r'型号[：:]\s*([A-Za-z0-9\-_]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content_sample, re.IGNORECASE)
            if match:
                product_id = match.group(1).strip()
                break
    
    return product_id


def extract_industry_tags(content: str, filename: str = "") -> List[str]:
    """从内容和文件名中提取行业标签"""
    tags = set()
    text_to_check = (filename + " " + content[:3000]).lower()
    
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_to_check:
                tags.add(industry)
                break
    
    return list(tags)


def extract_use_case_tags(content: str, filename: str = "") -> List[str]:
    """从内容和文件名中提取使用场景标签"""
    tags = set()
    text_to_check = (filename + " " + content[:3000]).lower()
    
    for use_case, keywords in USE_CASE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_to_check:
                tags.add(use_case)
                break
    
    return list(tags)


def determine_ku_type(material_type: str, content: str = "") -> str:
    """
    确定 KU 类型
    
    优先检查是否是报价或解决方案类型
    """
    content_lower = content[:3000].lower() if content else ""
    
    # 检查是否是报价类型
    for pattern in QUOTE_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return "quote"
    
    # 检查是否是解决方案类型
    for pattern in SOLUTION_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return "solution"
    
    # 使用默认映射
    return MATERIAL_TO_KU_TYPE.get(material_type, "core")


def estimate_applicability_score(
    scenario_from_path: Optional[str],
    content: str = ""
) -> float:
    """
    估算通用性评分
    
    Args:
        scenario_from_path: 从路径提取的场景ID
        content: 文件内容
        
    Returns:
        0-1 的通用性评分，0=专属场景，1=完全通用
    """
    # 如果在common目录下，完全通用
    if scenario_from_path == "common":
        return 1.0
    
    # 如果没有明确场景，可能较通用
    if not scenario_from_path:
        return 0.7
    
    # 检查内容中的通用性指标
    content_lower = content[:3000].lower() if content else ""
    
    # 通用性关键词
    general_keywords = [
        r'通用', r'适用于.*多种', r'广泛应用', r'跨.*场景',
        r'行业标准', r'最佳实践', r'基础知识',
    ]
    
    # 专属性关键词
    specific_keywords = [
        r'仅适用于', r'专用', r'定制', r'针对.*场景',
        r'特定', r'专属',
    ]
    
    general_count = sum(1 for kw in general_keywords if re.search(kw, content_lower))
    specific_count = sum(1 for kw in specific_keywords if re.search(kw, content_lower))
    
    # 基础分（有明确场景归属）
    base_score = 0.5
    
    # 调整分数
    score = base_score + 0.1 * general_count - 0.1 * specific_count
    
    return max(0.0, min(1.0, score))


# 测试代码
if __name__ == "__main__":
    test_cases = [
        ("AOI检测白皮书.pdf", "本白皮书介绍了AOI技术的发展趋势..."),
        ("客户案例-华为.docx", "客户背景：华为技术有限公司..."),
        ("操作指南.pdf", "第一步：打开设备电源...第二步：..."),
        ("常见问题FAQ.md", "问：如何解决连接失败？答：请检查..."),
        ("AOI vs 人工检测对比.pdf", "本文对比分析了AOI和人工检测的优缺点..."),
        ("系统架构设计.docx", "系统架构图如下...包含以下模块..."),
        ("产品规格书.pdf", "技术规格：精度0.01mm，功率200W..."),
        ("故障排除手册.pdf", "常见故障及解决方法..."),
        ("普通文档.txt", "这是一个普通的文档内容..."),
    ]
    
    for filename, content in test_cases:
        result = classify_material(filename, content)
        print(f"\n文件: {filename}")
        print(f"  类型: {result.material_type}")
        print(f"  意图: {result.intent_types}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  匹配: {result.matched_patterns}")

