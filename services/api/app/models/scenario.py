"""
场景化 Prompt Library 和层级化材料管理的数据模型
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, Float, JSON, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
from ..db import Base


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


class MaterialFormat(str, Enum):
    """材料格式"""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    MD = "md"
    TXT = "txt"
    IMAGE = "image"
    VIDEO = "video"
    JSON = "json"
    OTHER = "other"


class MaterialType(str, Enum):
    """材料类型"""
    WHITEPAPER = "whitepaper"           # 白皮书
    ARCHITECTURE = "architecture"        # 架构文档
    DEPLOYMENT_GUIDE = "deployment"      # 部署指南
    CASE_STUDY = "case_study"            # 案例研究
    COST_ANALYSIS = "cost_analysis"      # 成本分析
    COMPARISON = "comparison"            # 对比分析
    FAQ = "faq"                          # 常见问题
    TUTORIAL = "tutorial"                # 教程
    REFERENCE = "reference"              # 参考资料
    DIAGRAM = "diagram"                  # 图表
    OTHER = "other"


# ==================== 场景管理 ====================

class Scenario(Base):
    """
    场景定义
    例如: 网络安全、云架构、数据治理
    """
    __tablename__ = "scenarios"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(200), nullable=False)           # 场景名称
    description = Column(Text)                            # 场景描述
    domain = Column(String(100))                          # 所属领域
    keywords = Column(JSON, default=list)                 # 关键词列表
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)                 # 优先级
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    prompts = relationship("ScenarioPromptTemplate", back_populates="scenario")
    solutions = relationship("Solution", back_populates="scenario")


class ScenarioPromptTemplate(Base):
    """
    场景化 Prompt 模板
    每个场景可以有多个版本的 Prompt
    """
    __tablename__ = "scenario_prompt_templates"
    
    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), ForeignKey("scenarios.id"), nullable=False)
    intent_type = Column(String(50), nullable=False)      # 适用的意图类型
    version = Column(Integer, default=1)
    name = Column(String(200), nullable=False)
    
    # Prompt 内容
    system_prompt = Column(Text, nullable=False)          # 系统提示词
    context_template = Column(Text)                       # 上下文模板
    output_format = Column(Text)                          # 输出格式要求
    few_shot_examples = Column(JSON, default=list)        # Few-shot 示例
    
    # 配置
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    retrieval_config = Column(JSON, default=dict)         # 检索配置
    
    enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)           # 是否默认模板
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    scenario = relationship("Scenario", back_populates="prompts")


# ==================== 解决方案管理 ====================

class Solution(Base):
    """
    解决方案
    例如: 纵深防御、零信任、SASE
    """
    __tablename__ = "solutions"
    
    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), ForeignKey("scenarios.id"), nullable=False)
    name = Column(String(200), nullable=False)            # 方案名称
    description = Column(Text)                            # 方案描述
    summary = Column(Text)                                # 摘要（用于快速展示）
    
    # 方案特征
    tags = Column(JSON, default=list)                     # 标签
    target_audience = Column(JSON, default=list)          # 目标用户群
    applicable_scenarios = Column(JSON, default=list)     # 适用场景
    
    # 评分和排序
    priority = Column(Integer, default=0)
    maturity_score = Column(Float, default=0)             # 成熟度评分
    cost_level = Column(String(20))                       # 成本级别: low/medium/high
    complexity_level = Column(String(20))                 # 复杂度级别
    
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    scenario = relationship("Scenario", back_populates="solutions")
    materials = relationship("Material", back_populates="solution")


# ==================== 材料管理 ====================

class Material(Base):
    """
    材料/文档
    挂载在解决方案下
    """
    __tablename__ = "materials"
    
    id = Column(String(64), primary_key=True)
    solution_id = Column(String(64), ForeignKey("solutions.id"), nullable=False)
    
    # 基本信息
    name = Column(String(500), nullable=False)            # 材料名称
    description = Column(Text)                            # 描述
    file_path = Column(String(1000))                      # MinIO 路径
    original_filename = Column(String(500))               # 原始文件名
    
    # 分类
    format = Column(String(20))                           # 格式: pdf, docx, etc.
    material_type = Column(String(50))                    # 类型: whitepaper, case_study, etc.
    
    # 元数据
    tags = Column(JSON, default=list)
    language = Column(String(10), default="zh")           # 语言
    version = Column(String(50))                          # 版本号
    author = Column(String(200))                          # 作者
    
    # 内容摘要（用于检索）
    content_summary = Column(Text)                        # 内容摘要
    key_points = Column(JSON, default=list)               # 关键点
    
    # 索引状态
    indexed = Column(Boolean, default=False)              # 是否已索引到 OpenSearch
    index_id = Column(String(100))                        # OpenSearch 文档 ID
    
    # 质量和排序
    quality_score = Column(Float, default=0)              # 质量评分
    relevance_boost = Column(Float, default=1.0)          # 相关性加权
    
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联
    solution = relationship("Solution", back_populates="materials")


# ==================== 意图识别规则 ====================

class IntentRule(Base):
    """
    意图识别规则
    用于将用户问题映射到意图类型
    """
    __tablename__ = "intent_rules"
    
    id = Column(String(64), primary_key=True)
    intent_type = Column(String(50), nullable=False)
    
    # 规则定义
    keywords = Column(JSON, default=list)                 # 关键词列表
    patterns = Column(JSON, default=list)                 # 正则模式
    examples = Column(JSON, default=list)                 # 示例问题
    
    # 置信度阈值
    confidence_threshold = Column(Float, default=0.6)
    
    priority = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

