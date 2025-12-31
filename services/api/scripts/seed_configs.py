#!/usr/bin/env python3
"""
Seed script to initialize configuration data in the database.
Migrates hardcoded scenarios, prompts, intent patterns, and KU types.

Usage:
    python scripts/seed_configs.py
    
Or from Docker:
    docker exec -it datafactory-api python scripts/seed_configs.py
"""
import os
import sys
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db import SessionLocal, engine
from app.models.config import ScenarioConfig, PromptTemplate, KUTypeDefinition, ParameterDefinition, CalculationRule


# ==================== Scenarios ====================

SCENARIOS = [
    {
        "scenario_id": "param",
        "name": "参数查询",
        "description": "查询产品技术参数、规格型号等信息",
        "icon": "BookOpen",
        "intent_patterns": [
            {"keywords": ["多少", "几", "参数", "规格", "型号", "功率", "精度", "速度", "尺寸", "重量", "价格"]},
            {"patterns": [r"(\S+)(是)?多少", r"参数[是有]?", r"规格(是|有)?"]}
        ],
        "retrieval_config": {"top_k": 5, "min_score": 0.3, "ku_types": ["core.tech_spec", "core.product_feature"]},
        "quick_commands": [{"cmd": "/参数", "description": "快速查询产品参数"}],
        "is_active": True,
        "sort_order": 1
    },
    {
        "scenario_id": "case",
        "name": "案例检索",
        "description": "检索客户成功案例、行业应用案例",
        "icon": "Users",
        "intent_patterns": [
            {"keywords": ["案例", "实例", "成功案例", "应用案例", "客户", "项目"]},
            {"patterns": [r"(.+)(案例|实例)", r"有.*客户", r"项目经验"]}
        ],
        "retrieval_config": {"top_k": 5, "min_score": 0.3, "ku_types": ["case.customer_story", "case.public_reference"]},
        "quick_commands": [{"cmd": "/案例", "description": "快速检索客户案例"}],
        "is_active": True,
        "sort_order": 2
    },
    {
        "scenario_id": "quote",
        "name": "报价测算",
        "description": "产品报价查询、成本测算",
        "icon": "Calculator",
        "intent_patterns": [
            {"keywords": ["价格", "报价", "多少钱", "费用", "成本", "预算", "花费"]},
            {"patterns": [r"(多少钱|什么价格)", r"报价", r"费用(是|多少)"]}
        ],
        "retrieval_config": {"top_k": 3, "min_score": 0.4, "ku_types": ["quote.pricebook"]},
        "quick_commands": [{"cmd": "/报价", "description": "快速查询报价信息"}],
        "is_active": True,
        "sort_order": 3
    },
    {
        "scenario_id": "solution",
        "name": "方案生成",
        "description": "生成解决方案建议、技术方案",
        "icon": "FileText",
        "intent_patterns": [
            {"keywords": ["推荐", "方案", "解决方案", "怎么选", "选型", "建议", "如何实现"]},
            {"patterns": [r"推荐.*方案", r"有.*解决方案", r"怎么.*实现"]}
        ],
        "retrieval_config": {"top_k": 5, "min_score": 0.3, "ku_types": ["solution.industry", "solution.proposal"]},
        "quick_commands": [{"cmd": "/方案", "description": "快速生成解决方案"}],
        "is_active": True,
        "sort_order": 4
    },
    {
        "scenario_id": "compare",
        "name": "对比分析",
        "description": "产品对比、竞品分析",
        "icon": "Zap",
        "intent_patterns": [
            {"keywords": ["对比", "比较", "区别", "差异", "vs", "versus", "还是"]},
            {"patterns": [r"(.+)和(.+)(的)?(区别|差异|对比)", r"(.+)vs(.+)", r"比较(.+)和(.+)"]}
        ],
        "retrieval_config": {"top_k": 6, "min_score": 0.3, "ku_types": ["sales.competitor", "core.tech_spec"]},
        "response_template": "使用表格格式对比，列出关键差异点",
        "quick_commands": [{"cmd": "/对比", "description": "快速对比产品"}],
        "is_active": True,
        "sort_order": 5
    },
    {
        "scenario_id": "talk",
        "name": "话术应对",
        "description": "销售话术、异议应对技巧",
        "icon": "MessageSquare",
        "intent_patterns": [
            {"keywords": ["话术", "怎么说", "如何回应", "怎么回答", "应对", "客户说"]},
            {"patterns": [r"怎么回(应|答)", r"客户说.*怎么", r"话术"]}
        ],
        "retrieval_config": {"top_k": 5, "min_score": 0.3, "ku_types": ["sales.playbook"]},
        "quick_commands": [{"cmd": "/话术", "description": "快速获取应对话术"}],
        "is_active": True,
        "sort_order": 6
    },
]


# ==================== Prompts ====================

PROMPTS = [
    {
        "name": "RAG 系统提示词",
        "type": "system",
        "scenario_id": None,  # 通用
        "template": """你是一个专业的知识助手。请基于以下检索到的知识内容回答用户问题。

{{context}}

回答要求：
1. 基于上述内容准确回答，不要编造信息
2. 在适当位置引用来源，格式如【来源: xxx】
3. 如果检索内容不足以回答问题，请如实说明
4. 使用专业但易懂的语言

格式化输出要求（使用 Markdown）：
- **对比类问题**：使用 Markdown 表格展示，如 | 参数 | A产品 | B产品 |
- **多步骤/流程**：使用有序列表 1. 2. 3.
- **多要点**：使用无序列表 - 或 *
- **代码/配置**：使用代码块 ```语言名
- **重点内容**：使用 **加粗** 或 `行内代码`
- **流程图**：可使用 Mermaid 语法 ```mermaid

表格示例：
| 对比项 | 产品A | 产品B |
|--------|-------|-------|
| 精度   | 0.01mm | 0.02mm |
| 产能   | 5000片/h | 3500片/h |""",
        "variables": [{"name": "context", "description": "检索到的上下文内容"}],
        "is_active": True
    },
    {
        "name": "无结果系统提示词",
        "type": "system",
        "scenario_id": None,
        "template": """你是一个专业的知识助手。当前知识库未找到相关内容。
请告知用户暂无相关资料，并询问是否可以提供更多信息帮助完善知识库。""",
        "variables": [],
        "is_active": True
    },
    {
        "name": "意图识别提示词",
        "type": "intent",
        "scenario_id": None,
        "template": """分析用户问题的意图类型。

可能的意图类型：
- solution_recommendation: 方案推荐
- technical_qa: 技术问答
- troubleshooting: 故障诊断
- comparison: 对比分析
- parameter_query: 参数查询
- calculation: 计算/选型
- case_study: 案例查询
- quote: 报价咨询
- general: 通用问题

用户问题: {{query}}

返回JSON格式：
{
  "intent_type": "xxx",
  "confidence": 0.8,
  "entities": {"product": "xxx", "parameter": "xxx"}
}""",
        "variables": [{"name": "query", "description": "用户问题"}],
        "is_active": True
    },
    {
        "name": "对比分析专用提示词",
        "type": "response",
        "scenario_id": "compare",
        "template": """基于检索到的内容，对比分析用户询问的产品/方案。

{{context}}

要求：
1. 使用表格形式展示对比结果
2. 列出主要对比维度：规格参数、适用场景、优缺点、价格区间
3. 给出选择建议

用户问题: {{query}}""",
        "variables": [
            {"name": "context", "description": "检索内容"},
            {"name": "query", "description": "用户问题"}
        ],
        "is_active": True
    },
    {
        "name": "材料分类提示词",
        "type": "classification",
        "scenario_id": None,
        "template": """分析以下文件内容，判断其类型和分类。

文件名: {{filename}}
内容摘要:
{{content}}

可选的知识单元类型：
- core.product_feature: 产品功能说明
- core.tech_spec: 技术规格
- core.delivery_guide: 实施指南
- solution.industry: 行业解决方案
- solution.proposal: 方案书
- case.customer_story: 客户案例
- case.public_reference: 公开证据
- quote.pricebook: 报价单
- sales.competitor: 竞品分析
- sales.playbook: 销售话术
- delivery.sop: 交付SOP
- support.troubleshooting: 故障排查
- enablement.training: 培训材料
- field.signal: 现场信号

返回JSON格式：
{
  "ku_type_code": "case.customer_story",
  "product_id": "AOI8000",
  "tags": ["PCB检测", "汽车行业"],
  "confidence": 0.85,
  "reason": "文档包含客户名称、项目背景、解决方案描述，符合客户案例特征"
}""",
        "variables": [
            {"name": "filename", "description": "文件名"},
            {"name": "content", "description": "文件内容摘要"}
        ],
        "is_active": True
    },
]


# ==================== KU Types ====================

KU_TYPES = [
    # 产品与技术类
    {"type_code": "core.product_feature", "category": "product", "display_name": "产品功能说明", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Package", "sort_order": 1},
    {"type_code": "core.tech_spec", "category": "product", "display_name": "技术规格", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Settings", "sort_order": 2},
    {"type_code": "core.delivery_guide", "category": "product", "display_name": "实施指南", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "BookOpen", "sort_order": 3},
    {"type_code": "core.integration", "category": "product", "display_name": "API/集成文档", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Link", "sort_order": 4},
    {"type_code": "core.release_notes", "category": "product", "display_name": "版本说明", "merge_strategy": "independent", "requires_expiry": True, "requires_approval": True, "visibility_default": "internal", "icon": "FileText", "sort_order": 5},
    
    # 解决方案与售前
    {"type_code": "solution.industry", "category": "solution", "display_name": "行业解决方案", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Briefcase", "sort_order": 10},
    {"type_code": "solution.proposal", "category": "solution", "display_name": "方案书", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "FileText", "sort_order": 11},
    {"type_code": "solution.poc", "category": "solution", "display_name": "PoC方案", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Beaker", "sort_order": 12},
    {"type_code": "sales.competitor", "category": "sales", "display_name": "竞品分析", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Target", "sort_order": 13},
    {"type_code": "sales.playbook", "category": "sales", "display_name": "销售话术", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "MessageSquare", "sort_order": 14},
    
    # 案例与证据类
    {"type_code": "case.customer_story", "category": "case", "display_name": "客户案例", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Award", "sort_order": 20},
    {"type_code": "case.public_reference", "category": "case", "display_name": "公开证据", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "public", "icon": "ExternalLink", "sort_order": 21},
    
    # 商务与交易类
    {"type_code": "quote.pricebook", "category": "quote", "display_name": "报价单", "merge_strategy": "independent", "requires_expiry": True, "requires_approval": True, "visibility_default": "confidential", "icon": "DollarSign", "sort_order": 30},
    {"type_code": "biz.contract_sla", "category": "biz", "display_name": "合同/SLA", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "confidential", "icon": "FileContract", "sort_order": 31},
    {"type_code": "bid.rfp_response", "category": "biz", "display_name": "投标材料", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "confidential", "icon": "Clipboard", "sort_order": 32},
    {"type_code": "compliance.certification", "category": "biz", "display_name": "资质认证", "merge_strategy": "independent", "requires_expiry": True, "requires_approval": True, "visibility_default": "internal", "icon": "Shield", "sort_order": 33},
    
    # 交付与运营类
    {"type_code": "delivery.sop", "category": "delivery", "display_name": "交付SOP", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "CheckSquare", "sort_order": 40},
    {"type_code": "support.troubleshooting", "category": "delivery", "display_name": "故障排查", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Tool", "sort_order": 41},
    {"type_code": "enablement.training", "category": "delivery", "display_name": "培训材料", "merge_strategy": "smart_merge", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "GraduationCap", "sort_order": 42},
    
    # 过程型增量
    {"type_code": "field.signal", "category": "field", "display_name": "现场信号", "merge_strategy": "independent", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Radio", "sort_order": 50},
    {"type_code": "eval.dataset", "category": "field", "display_name": "评测数据", "merge_strategy": "append", "requires_expiry": False, "requires_approval": True, "visibility_default": "internal", "icon": "Database", "sort_order": 51},
]


# ==================== Parameter Definitions ====================

PARAMETERS = [
    {"name": "检测精度", "code": "detection_accuracy", "data_type": "number", "unit": "mm", "category": "performance", "synonyms": ["精度", "准确度", "accuracy"], "description": "设备检测的精度指标"},
    {"name": "检测速度", "code": "detection_speed", "data_type": "number", "unit": "片/小时", "category": "performance", "synonyms": ["速度", "产能", "UPH", "throughput"], "description": "单位时间内处理的产品数量"},
    {"name": "分辨率", "code": "resolution", "data_type": "number", "unit": "μm", "category": "optical", "synonyms": ["像素", "pixel"], "description": "光学系统分辨率"},
    {"name": "视野范围", "code": "fov", "data_type": "string", "unit": "mm", "category": "optical", "synonyms": ["FOV", "视野", "field of view"], "description": "相机视野范围"},
    {"name": "光源类型", "code": "light_source", "data_type": "string", "unit": None, "category": "optical", "synonyms": ["光源", "照明", "lighting"], "description": "使用的光源类型"},
    {"name": "支持板尺寸", "code": "board_size", "data_type": "string", "unit": "mm", "category": "capability", "synonyms": ["板子尺寸", "PCB尺寸"], "description": "可处理的PCB板最大尺寸"},
    {"name": "误检率", "code": "false_positive_rate", "data_type": "number", "unit": "%", "category": "quality", "synonyms": ["误报率", "过杀率", "FPR"], "description": "误报为缺陷的比例"},
    {"name": "漏检率", "code": "false_negative_rate", "data_type": "number", "unit": "%", "category": "quality", "synonyms": ["漏报率", "FNR"], "description": "漏报缺陷的比例"},
]


# ==================== Calculation Rules ====================

CALC_RULES = [
    {
        "name": "设备数量计算",
        "code": "equipment_count",
        "description": "根据产能需求计算所需设备数量",
        "formula": "import math\nresult = math.ceil(daily_output / (uph * working_hours * efficiency))",
        "input_schema": {
            "daily_output": {"type": "number", "description": "日产量目标"},
            "uph": {"type": "number", "description": "单台设备UPH"},
            "working_hours": {"type": "number", "description": "日工作时长", "default": 20},
            "efficiency": {"type": "number", "description": "设备效率", "default": 0.85}
        },
        "output_schema": {"type": "number", "description": "所需设备数量"},
        "output_type": "number",
        "input_params": [
            {"name": "daily_output", "type": "number", "required": True},
            {"name": "uph", "type": "number", "required": True},
            {"name": "working_hours", "type": "number", "required": False, "default": 20},
            {"name": "efficiency", "type": "number", "required": False, "default": 0.85}
        ],
        "examples": [
            {"input": {"daily_output": 50000, "uph": 3000, "working_hours": 20, "efficiency": 0.85}, "output": 1}
        ],
        "is_active": True
    },
    {
        "name": "ROI计算",
        "code": "roi_calculation",
        "description": "计算设备投资回报率",
        "formula": "labor_cost_saved = labor_count * avg_salary * 12\nannual_benefit = labor_cost_saved + quality_improvement_value\nroi = (annual_benefit - equipment_cost) / equipment_cost * 100\nresult = round(roi, 2)",
        "input_schema": {
            "equipment_cost": {"type": "number", "description": "设备投资成本"},
            "labor_count": {"type": "number", "description": "可替代人工数量"},
            "avg_salary": {"type": "number", "description": "人均月薪", "default": 8000},
            "quality_improvement_value": {"type": "number", "description": "质量提升价值", "default": 0}
        },
        "output_schema": {"type": "number", "description": "ROI百分比"},
        "output_type": "number",
        "input_params": [
            {"name": "equipment_cost", "type": "number", "required": True},
            {"name": "labor_count", "type": "number", "required": True},
            {"name": "avg_salary", "type": "number", "required": False, "default": 8000},
            {"name": "quality_improvement_value", "type": "number", "required": False, "default": 0}
        ],
        "is_active": True
    },
]


def seed_scenarios(db: Session):
    """Seed scenario configurations"""
    print("Seeding scenarios...")
    count = 0
    for scenario_data in SCENARIOS:
        existing = db.query(ScenarioConfig).filter(
            ScenarioConfig.scenario_id == scenario_data["scenario_id"]
        ).first()
        
        if not existing:
            scenario = ScenarioConfig(**scenario_data)
            db.add(scenario)
            count += 1
            print(f"  Added scenario: {scenario_data['name']}")
        else:
            # Update existing
            for key, value in scenario_data.items():
                setattr(existing, key, value)
            print(f"  Updated scenario: {scenario_data['name']}")
    
    db.commit()
    print(f"  Total: {count} scenarios added")


def seed_prompts(db: Session):
    """Seed prompt templates"""
    print("Seeding prompts...")
    count = 0
    for prompt_data in PROMPTS:
        existing = db.query(PromptTemplate).filter(
            PromptTemplate.name == prompt_data["name"],
            PromptTemplate.type == prompt_data["type"]
        ).first()
        
        if not existing:
            prompt = PromptTemplate(**prompt_data)
            db.add(prompt)
            count += 1
            print(f"  Added prompt: {prompt_data['name']}")
        else:
            # Update existing
            for key, value in prompt_data.items():
                setattr(existing, key, value)
            print(f"  Updated prompt: {prompt_data['name']}")
    
    db.commit()
    print(f"  Total: {count} prompts added")


def seed_ku_types(db: Session):
    """Seed KU type definitions"""
    print("Seeding KU types...")
    count = 0
    for ku_type_data in KU_TYPES:
        existing = db.query(KUTypeDefinition).filter(
            KUTypeDefinition.type_code == ku_type_data["type_code"]
        ).first()
        
        if not existing:
            ku_type = KUTypeDefinition(**ku_type_data)
            db.add(ku_type)
            count += 1
            print(f"  Added KU type: {ku_type_data['display_name']}")
        else:
            # Update existing
            for key, value in ku_type_data.items():
                setattr(existing, key, value)
            print(f"  Updated KU type: {ku_type_data['display_name']}")
    
    db.commit()
    print(f"  Total: {count} KU types added")


def seed_parameters(db: Session):
    """Seed parameter definitions"""
    print("Seeding parameters...")
    count = 0
    for param_data in PARAMETERS:
        existing = db.query(ParameterDefinition).filter(
            ParameterDefinition.code == param_data["code"]
        ).first()
        
        if not existing:
            param = ParameterDefinition(**param_data)
            db.add(param)
            count += 1
            print(f"  Added parameter: {param_data['name']}")
        else:
            # Update existing
            for key, value in param_data.items():
                setattr(existing, key, value)
            print(f"  Updated parameter: {param_data['name']}")
    
    db.commit()
    print(f"  Total: {count} parameters added")


def seed_calc_rules(db: Session):
    """Seed calculation rules"""
    print("Seeding calculation rules...")
    count = 0
    for rule_data in CALC_RULES:
        existing = db.query(CalculationRule).filter(
            CalculationRule.code == rule_data["code"]
        ).first()
        
        if not existing:
            rule = CalculationRule(**rule_data)
            db.add(rule)
            count += 1
            print(f"  Added calculation rule: {rule_data['name']}")
        else:
            # Update existing
            for key, value in rule_data.items():
                setattr(existing, key, value)
            print(f"  Updated calculation rule: {rule_data['name']}")
    
    db.commit()
    print(f"  Total: {count} calculation rules added")


def main():
    """Main seed function"""
    print("=" * 60)
    print("Configuration Seed Script")
    print("=" * 60)
    print()
    
    db = SessionLocal()
    try:
        seed_scenarios(db)
        print()
        seed_prompts(db)
        print()
        seed_ku_types(db)
        print()
        seed_parameters(db)
        print()
        seed_calc_rules(db)
        print()
        print("=" * 60)
        print("Seeding completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

