from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from .db import Base

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
