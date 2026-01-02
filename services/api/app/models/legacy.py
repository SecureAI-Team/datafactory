"""Legacy models - original data models from the core system"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from ..db import Base


# ==================== KU 类型常量 ====================
class KUType:
    CORE = "core"           # 核心产品信息（参数、功能、规格）
    CASE = "case"           # 客户案例/成功故事
    QUOTE = "quote"         # 报价单/价格信息
    SOLUTION = "solution"   # 解决方案/方案书
    WHITEPAPER = "whitepaper"  # 白皮书/技术文档
    FAQ = "faq"             # 常见问题
    
    ALL = [CORE, CASE, QUOTE, SOLUTION, WHITEPAPER, FAQ]
    MERGEABLE = [CORE, WHITEPAPER, FAQ]  # 可合并的类型


class RelationType:
    PARENT_OF = "parent_of"     # 主KU -> 附属KU
    RELATED_TO = "related_to"   # 相关联
    MERGED_FROM = "merged_from" # 合并来源
    SUPERSEDES = "supersedes"   # 替代（新版本）


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    uploader = Column(String, nullable=False)
    mime = Column(String)
    size = Column(Integer)
    hash = Column(String)
    minio_uri = Column(String)
    status = Column(String, default="uploaded")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedText(Base):
    __tablename__ = "extracted_texts"
    id = Column(Integer, primary_key=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"))
    tika_text = Column(Text)
    metadata_json = Column(JSON)
    unstructured_elements_json = Column(JSON)
    status = Column(String, default="pending")

class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"
    id = Column(Integer, primary_key=True)
    version = Column(Integer, default=1)
    status = Column(String, default="draft")
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    body_markdown = Column(Text, nullable=False)
    sections_json = Column(JSON)
    tags_json = Column(JSON)
    glossary_terms_json = Column(JSON)
    evidence_map_json = Column(JSON)
    source_refs_json = Column(JSON)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Phase 6 新增字段 - 多资料处理
    ku_type = Column(String(20), default="core")  # core/case/quote/solution/whitepaper/faq
    parent_ku_id = Column(String(50), nullable=True)  # 关联到主KU
    product_id = Column(String(100), nullable=True)  # 产品标识
    is_primary = Column(Boolean, default=False)  # 是否为该产品的主KU
    merge_source_ids = Column(JSONB, default=[])  # 合并来源 KU IDs
    industry_tags = Column(JSONB, default=[])  # 行业标签
    use_case_tags = Column(JSONB, default=[])  # 使用场景标签
    
    # Pipeline integration fields
    source_file = Column(String(500), nullable=True)  # 原始文件路径
    scenario_tags = Column(JSONB, default=[])  # 场景标签
    key_points_json = Column(JSONB, default=[])  # 关键点
    params_json = Column(JSONB, default=[])  # 结构化参数

class KUReview(Base):
    __tablename__ = "ku_reviews"
    id = Column(Integer, primary_key=True)
    ku_id = Column(Integer, ForeignKey("knowledge_units.id"))
    reviewer = Column(String)
    decision = Column(String)
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    channel = Column(String, default="web")
    user_id = Column(String)
    scenario_id = Column(String)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    message_id = Column(String)
    rating = Column(Integer)
    reason_enum = Column(String)
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ScenarioPrompt(Base):
    __tablename__ = "scenario_prompts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    template = Column(Text, nullable=False)
    input_schema_json = Column(JSON)
    output_schema_json = Column(JSON)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DQRun(Base):
    __tablename__ = "dq_runs"
    id = Column(Integer, primary_key=True)
    batch_id = Column(String)
    suite_name = Column(String)
    passed = Column(Boolean)
    report_uri = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(Integer, primary_key=True)
    dag_id = Column(String)
    run_id = Column(String)
    status = Column(String)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    error = Column(Text)


# ==================== Phase 6 新增模型 ====================

class KURelation(Base):
    """KU 关联关系表"""
    __tablename__ = "ku_relations"
    id = Column(Integer, primary_key=True)
    source_ku_id = Column(String(50), nullable=False)  # 源 KU ID
    target_ku_id = Column(String(50), nullable=False)  # 目标 KU ID
    relation_type = Column(String(30), nullable=False)  # parent_of, related_to, merged_from, supersedes
    relation_metadata = Column(JSONB, default={})  # Renamed from 'metadata' (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    """产品维度管理表"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    product_id = Column(String(100), unique=True, nullable=False)  # 产品唯一标识
    name = Column(String(200), nullable=False)  # 产品名称
    category = Column(String(100))  # 产品分类
    description = Column(Text)  # 产品描述
    primary_ku_id = Column(Integer, nullable=True)  # 主 KU ID
    extra_data = Column(JSONB, default={})  # Renamed from 'metadata' (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DedupGroup(Base):
    """重复检测结果组"""
    __tablename__ = "dedup_groups"
    id = Column(Integer, primary_key=True)
    group_id = Column(String(50), unique=True, nullable=False)
    ku_ids = Column(JSONB, nullable=False)  # 该组包含的 KU IDs
    similarity_score = Column(Float)  # 相似度分数
    status = Column(String(20), default="pending")  # pending, merged, dismissed
    merge_result_ku_id = Column(Integer, nullable=True)  # 合并后的 KU ID
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

