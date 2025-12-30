"""Conversation and message models"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class ConversationV2(Base):
    """对话表 (扩展版本)
    
    注意：原有 Conversation 模型保留在 models.py 中用于兼容
    此模型为新增字段的扩展视图
    """
    __tablename__ = "conversations"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(50), unique=True)  # UUID 格式
    channel = Column(String, default="web")
    user_id = Column(String)
    scenario_id = Column(String)
    title = Column(String(200))
    summary = Column(Text)
    
    # 状态
    status = Column(String(20), default='active')  # active/archived/deleted
    is_pinned = Column(Boolean, default=False)
    
    # 统计
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True))
    
    # 元数据
    tags = Column(JSONB, default=[])
    conv_metadata = Column(JSONB, default={})
    
    # 时间
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    shares = relationship("ConversationShare", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation {self.conversation_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "is_pinned": self.is_pinned,
            "message_count": self.message_count,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "tags": self.tags,
            "scenario_id": self.scenario_id,
            "created_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConversationMessage(Base):
    """对话消息表"""
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(50), ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    message_id = Column(String(50), unique=True, nullable=False)
    
    # 消息内容
    role = Column(String(20), nullable=False)  # user/assistant/system
    content = Column(Text, nullable=False)
    
    # 检索上下文（assistant消息）
    retrieved_context = Column(JSONB)  # 检索到的 KU 列表
    sources = Column(JSONB, default=[])  # 来源引用
    
    # 反馈
    feedback = Column(String(10))  # positive/negative
    feedback_text = Column(Text)
    
    # 元数据
    tokens_used = Column(Integer)
    model_used = Column(String(50))
    latency_ms = Column(Integer)
    msg_metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("ConversationV2", back_populates="messages")
    
    def __repr__(self):
        return f"<Message {self.message_id} ({self.role})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "feedback": self.feedback,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationShare(Base):
    """对话分享表"""
    __tablename__ = "conversation_shares"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(50), ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    share_token = Column(String(100), unique=True, nullable=False)
    shared_by = Column(Integer, ForeignKey('users.id'))
    
    # 权限
    allow_copy = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))  # NULL = 永不过期
    
    # 统计
    view_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("ConversationV2", back_populates="shares")
    
    def __repr__(self):
        return f"<Share {self.share_token}>"
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

