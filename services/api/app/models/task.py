"""Collaboration task models"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from ..db import Base


class CollaborationTask(Base):
    """协作任务表"""
    __tablename__ = "collaboration_tasks"
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String(30), nullable=False)  # request_info/verify_content/approve_term/review_ku
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # 关联对象
    related_type = Column(String(30))  # ku/contribution/term/prompt
    related_id = Column(Integer)
    
    # 分配
    assignee_id = Column(Integer, ForeignKey('users.id'))
    requester_id = Column(Integer, ForeignKey('users.id'))
    
    # 状态
    status = Column(String(20), default='open')  # open/in_progress/resolved/cancelled
    priority = Column(String(10), default='normal')  # low/normal/high/urgent
    
    # 结果
    resolution = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    
    due_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<CollaborationTask {self.id} ({self.task_type})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "task_type": self.task_type,
            "title": self.title,
            "description": self.description,
            "related_type": self.related_type,
            "related_id": self.related_id,
            "assignee_id": self.assignee_id,
            "requester_id": self.requester_id,
            "status": self.status,
            "priority": self.priority,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

