"""Configuration models - Scenarios, Prompts, KU Types"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db import Base


class ScenarioConfig(Base):
    """场景配置表"""
    __tablename__ = "scenario_configs"
    
    id = Column(Integer, primary_key=True)
    scenario_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(50))
    intent_patterns = Column(JSONB, default=[])  # 意图识别规则
    retrieval_config = Column(JSONB, default={})  # 检索策略配置
    response_template = Column(Text)  # 回答模板
    quick_commands = Column(JSONB, default=[])  # 快捷命令
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ScenarioConfig {self.scenario_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "intent_patterns": self.intent_patterns,
            "retrieval_config": self.retrieval_config,
            "response_template": self.response_template,
            "quick_commands": self.quick_commands,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
        }


class PromptTemplate(Base):
    """Prompt 模板表"""
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(30), nullable=False)  # system/user/intent/response/summary
    scenario_id = Column(String(50))  # NULL 表示通用
    template = Column(Text, nullable=False)
    variables = Column(JSONB, default=[])  # 模板变量定义
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    history = relationship("PromptHistory", back_populates="prompt", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PromptTemplate {self.name} v{self.version}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "scenario_id": self.scenario_id,
            "template": self.template,
            "variables": self.variables,
            "version": self.version,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PromptHistory(Base):
    """Prompt 版本历史"""
    __tablename__ = "prompt_history"
    
    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey('prompt_templates.id', ondelete='CASCADE'))
    version = Column(Integer, nullable=False)
    template = Column(Text, nullable=False)
    changed_by = Column(Integer, ForeignKey('users.id'))
    change_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    prompt = relationship("PromptTemplate", back_populates="history")
    
    def __repr__(self):
        return f"<PromptHistory prompt_id={self.prompt_id} v{self.version}>"


class KUTypeDefinition(Base):
    """KU 类型定义表"""
    __tablename__ = "ku_type_definitions"
    
    id = Column(Integer, primary_key=True)
    type_code = Column(String(50), unique=True, nullable=False)  # core.tech_spec
    category = Column(String(30), nullable=False)  # product/solution/case/quote/biz/delivery/field
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    merge_strategy = Column(String(20), default='independent')  # smart_merge/independent/append
    requires_expiry = Column(Boolean, default=False)
    requires_approval = Column(Boolean, default=True)
    visibility_default = Column(String(20), default='internal')
    icon = Column(String(50))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<KUTypeDefinition {self.type_code}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "type_code": self.type_code,
            "category": self.category,
            "display_name": self.display_name,
            "description": self.description,
            "merge_strategy": self.merge_strategy,
            "requires_expiry": self.requires_expiry,
            "requires_approval": self.requires_approval,
            "visibility_default": self.visibility_default,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class ParameterDefinition(Base):
    """参数定义表"""
    __tablename__ = "parameter_definitions"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    data_type = Column(String(30), nullable=False)  # string/number/boolean/array
    unit = Column(String(50))
    category = Column(String(50))
    synonyms = Column(JSONB, default=[])  # 同义词列表
    validation_rules = Column(JSONB, default={})  # 验证规则
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    updated_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ParameterDefinition {self.code}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "data_type": self.data_type,
            "unit": self.unit,
            "category": self.category,
            "synonyms": self.synonyms or [],
            "validation_rules": self.validation_rules or {},
            "description": self.description,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CalculationRule(Base):
    """计算规则表"""
    __tablename__ = "calculation_rules"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    formula = Column(Text, nullable=False)  # 计算公式
    input_schema = Column(JSONB, default={})  # 输入参数定义
    output_schema = Column(JSONB, default={})  # 输出定义
    input_params = Column(JSONB, default=[])  # 输入参数列表
    output_type = Column(String(30), default='number')  # 输出类型
    examples = Column(JSONB, default=[])  # 示例 { input: {}, output: value }
    is_active = Column(Boolean, default=True)
    updated_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<CalculationRule {self.code}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "formula": self.formula,
            "input_schema": self.input_schema or {},
            "output_schema": self.output_schema or {},
            "input_params": self.input_params or [],
            "output_type": self.output_type,
            "examples": self.examples or [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InteractionFlow(Base):
    """交互流程配置表 - 用于结构化问答收集信息"""
    __tablename__ = "interaction_flows"
    
    id = Column(Integer, primary_key=True)
    flow_id = Column(String(50), unique=True, nullable=False)  # quote_calc, case_search
    name = Column(String(100), nullable=False)
    description = Column(Text)
    trigger_patterns = Column(JSONB, default=[])  # 触发关键词/意图
    scenario_id = Column(String(50))  # 关联场景
    steps = Column(JSONB, nullable=False)  # 问题步骤定义
    on_complete = Column(String(30), default='generate')  # calculate/search/generate
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<InteractionFlow {self.flow_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "flow_id": self.flow_id,
            "name": self.name,
            "description": self.description,
            "trigger_patterns": self.trigger_patterns or [],
            "scenario_id": self.scenario_id,
            "steps": self.steps or [],
            "on_complete": self.on_complete,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InteractionSession(Base):
    """交互会话状态表 - 跟踪用户在交互流程中的进度"""
    __tablename__ = "interaction_sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, nullable=False)
    conversation_id = Column(String(50), nullable=False)  # 关联对话
    flow_id = Column(String(50), nullable=False)  # 关联流程
    user_id = Column(Integer, ForeignKey('users.id'))
    current_step = Column(Integer, default=0)
    collected_answers = Column(JSONB, default={})  # 已收集的答案
    status = Column(String(20), default='active')  # active/completed/cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<InteractionSession {self.session_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "flow_id": self.flow_id,
            "current_step": self.current_step,
            "collected_answers": self.collected_answers or {},
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

