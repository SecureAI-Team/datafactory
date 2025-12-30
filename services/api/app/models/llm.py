"""LLM Provider and Model configuration models"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class LLMProvider(Base):
    """LLM 提供商表"""
    __tablename__ = "llm_providers"
    
    id = Column(Integer, primary_key=True)
    provider_code = Column(String(50), unique=True, nullable=False)  # qwen/openai/azure/local
    provider_name = Column(String(100), nullable=False)
    api_base_url = Column(String(500))
    api_key_encrypted = Column(String)  # 加密存储
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    config = Column(JSONB, default={})  # 额外配置
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<LLMProvider {self.provider_code}>"
    
    def to_dict(self, include_key=False):
        result = {
            "id": self.id,
            "provider_code": self.provider_code,
            "provider_name": self.provider_name,
            "api_base_url": self.api_base_url,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_key:
            result["api_key"] = self.api_key_encrypted
        else:
            result["has_api_key"] = bool(self.api_key_encrypted)
        return result


class LLMModel(Base):
    """LLM 模型列表"""
    __tablename__ = "llm_models"
    
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey('llm_providers.id', ondelete='CASCADE'))
    model_code = Column(String(100), nullable=False)  # qwen-max/gpt-4/qwen-vl-max
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(30), nullable=False)  # chat/embedding/vision/audio
    capabilities = Column(JSONB, default=[])  # ['text', 'vision', 'function_call']
    context_window = Column(Integer)  # 上下文窗口大小
    max_output_tokens = Column(Integer)
    cost_per_1k_input = Column(Numeric(10, 6))  # 输入成本
    cost_per_1k_output = Column(Numeric(10, 6))  # 输出成本
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    config = Column(JSONB, default={})  # temperature, top_p 等默认值
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    provider = relationship("LLMProvider", back_populates="models")
    
    def __repr__(self):
        return f"<LLMModel {self.model_code}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "model_code": self.model_code,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "capabilities": self.capabilities,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "cost_per_1k_input": float(self.cost_per_1k_input) if self.cost_per_1k_input else None,
            "cost_per_1k_output": float(self.cost_per_1k_output) if self.cost_per_1k_output else None,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "config": self.config,
        }
    
    def has_capability(self, cap: str) -> bool:
        return cap in (self.capabilities or [])


class LLMModelAssignment(Base):
    """模型使用场景映射"""
    __tablename__ = "llm_model_assignments"
    
    id = Column(Integer, primary_key=True)
    use_case = Column(String(50), unique=True, nullable=False)  # chat/expand/summary/intent/embedding/vision
    model_id = Column(Integer, ForeignKey('llm_models.id'))
    fallback_model_id = Column(Integer, ForeignKey('llm_models.id'))
    priority = Column(Integer, default=0)
    config_override = Column(JSONB, default={})  # 覆盖默认配置
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<LLMModelAssignment {self.use_case}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "use_case": self.use_case,
            "model_id": self.model_id,
            "fallback_model_id": self.fallback_model_id,
            "priority": self.priority,
            "config_override": self.config_override,
            "is_active": self.is_active,
        }

