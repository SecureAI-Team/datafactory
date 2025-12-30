"""User and authentication models"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    avatar_url = Column(String(255))
    role = Column(String(20), nullable=False, default='user')  # admin/data_ops/bd_sales/user
    department = Column(String(100))
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    contributions = relationship("Contribution", back_populates="contributor", foreign_keys="Contribution.contributor_id")
    
    def __repr__(self):
        return f"<User {self.username}>"
    
    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'
    
    @property
    def is_data_ops(self) -> bool:
        return self.role in ('admin', 'data_ops')


class Role(Base):
    """角色权限表"""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    permissions = Column(JSONB, default=[])  # ['read:ku', 'write:ku', 'admin:users']
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Role {self.name}>"
    
    def has_permission(self, permission: str) -> bool:
        """检查角色是否有某权限"""
        if '*' in self.permissions:
            return True
        return permission in self.permissions


class UserSession(Base):
    """用户会话表 (JWT Token 管理)"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    token_hash = Column(String(255), nullable=False)
    device_info = Column(JSONB)
    ip_address = Column(String(45))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession user_id={self.user_id}>"
    
    @property
    def is_expired(self) -> bool:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

