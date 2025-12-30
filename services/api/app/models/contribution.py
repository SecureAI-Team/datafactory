"""Contribution and citation models"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class Contribution(Base):
    """贡献记录表"""
    __tablename__ = "contributions"
    
    id = Column(Integer, primary_key=True)
    contributor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    contribution_type = Column(String(30), nullable=False)  # file_upload/draft_ku/feedback/correction
    title = Column(String(200))
    description = Column(Text)
    
    # 文件上传相关
    file_name = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # 内容相关
    content_json = Column(JSONB)  # 草稿内容
    ku_type_code = Column(String(50))  # 关联 KU 类型
    product_id = Column(String(100))
    
    # 元数据
    tags = Column(JSONB, default=[])
    visibility = Column(String(20), default='internal')  # public/internal/confidential
    expiry_date = Column(Date)  # 有效期（报价单等）
    
    # 触发上下文
    trigger_type = Column(String(30))  # missing_info/improve_response/high_value_signal
    conversation_id = Column(String(50))  # 关联对话
    query_text = Column(Text)  # 触发问题
    
    # 状态
    status = Column(String(20), default='pending')  # pending/processing/approved/rejected/merged
    processed_ku_id = Column(Integer)  # 处理后生成的 KU ID
    
    # 审核
    reviewer_id = Column(Integer, ForeignKey('users.id'))
    review_comment = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    contributor = relationship("User", back_populates="contributions", foreign_keys=[contributor_id])
    
    def __repr__(self):
        return f"<Contribution {self.id} ({self.contribution_type})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "contributor_id": self.contributor_id,
            "contribution_type": self.contribution_type,
            "title": self.title,
            "description": self.description,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "ku_type_code": self.ku_type_code,
            "product_id": self.product_id,
            "tags": self.tags,
            "visibility": self.visibility,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "trigger_type": self.trigger_type,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "processed_ku_id": self.processed_ku_id,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ContributionStats(Base):
    """贡献统计表（用于排行榜和成就）"""
    __tablename__ = "contribution_stats"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    total_contributions = Column(Integer, default=0)
    approved_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    pending_count = Column(Integer, default=0)
    citation_count = Column(Integer, default=0)  # 被引用次数
    achievements = Column(JSONB, default=[])  # 获得的成就
    streak_days = Column(Integer, default=0)  # 连续贡献天数
    last_contribution_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ContributionStats user_id={self.user_id}>"
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "total_contributions": self.total_contributions,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "pending_count": self.pending_count,
            "citation_count": self.citation_count,
            "achievements": self.achievements,
            "streak_days": self.streak_days,
            "last_contribution_at": self.last_contribution_at.isoformat() if self.last_contribution_at else None,
        }


class CitationRecord(Base):
    """引用记录表（追踪贡献被使用情况）"""
    __tablename__ = "citation_records"
    
    id = Column(Integer, primary_key=True)
    ku_id = Column(Integer, ForeignKey('knowledge_units.id'))
    contribution_id = Column(Integer, ForeignKey('contributions.id'))
    cited_in_conversation = Column(String(50))  # 在哪个对话中被引用
    cited_by_user = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<CitationRecord ku_id={self.ku_id}>"

