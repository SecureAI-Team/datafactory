"""System configuration and settings models"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from ..db import Base


class SystemConfig(Base):
    """系统配置主表"""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True)
    config_group = Column(String(50), nullable=False)  # llm/search/storage/pipeline/notification/security
    config_key = Column(String(100), nullable=False)
    config_value = Column(Text)
    value_type = Column(String(20), default='string')  # string/number/boolean/json/secret
    description = Column(Text)
    is_secret = Column(Boolean, default=False)
    is_editable = Column(Boolean, default=True)
    validation_rule = Column(JSONB)
    default_value = Column(Text)
    source = Column(String(20), default='database')  # env/database/synced
    env_var_name = Column(String(100))  # 对应的环境变量名
    is_bootstrap = Column(Boolean, default=False)  # 是否启动必需配置
    last_synced_at = Column(DateTime(timezone=True))
    updated_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemConfig {self.config_group}.{self.config_key}>"
    
    def get_value(self):
        """获取配置值，根据类型转换"""
        if self.config_value is None:
            return self.default_value
        
        if self.value_type == 'number':
            try:
                if '.' in self.config_value:
                    return float(self.config_value)
                return int(self.config_value)
            except ValueError:
                return self.config_value
        elif self.value_type == 'boolean':
            return self.config_value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'json':
            import json
            try:
                return json.loads(self.config_value)
            except json.JSONDecodeError:
                return self.config_value
        elif self.value_type == 'secret':
            # 敏感信息返回掩码
            return '******' if self.config_value else None
        return self.config_value
    
    def get_raw_value(self):
        """获取原始值（包括敏感信息，需要权限）"""
        return self.config_value
    
    def to_dict(self, include_secret=False):
        return {
            "id": self.id,
            "config_group": self.config_group,
            "config_key": self.config_key,
            "config_value": self.get_raw_value() if include_secret else self.get_value(),
            "value_type": self.value_type,
            "description": self.description,
            "is_secret": self.is_secret,
            "is_editable": self.is_editable,
            "default_value": self.default_value,
            "source": self.source,
            "env_var_name": self.env_var_name,
            "is_bootstrap": self.is_bootstrap,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConfigChangeLog(Base):
    """配置变更历史"""
    __tablename__ = "config_change_logs"
    
    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey('system_configs.id', ondelete='CASCADE'))
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(Integer, ForeignKey('users.id'))
    change_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ConfigChangeLog config_id={self.config_id}>"


class ConfigEnvMapping(Base):
    """配置映射表（.env 变量名 → 数据库配置）"""
    __tablename__ = "config_env_mapping"
    
    id = Column(Integer, primary_key=True)
    env_var_name = Column(String(100), unique=True, nullable=False)  # DASHSCOPE_API_KEY
    config_group = Column(String(50), nullable=False)  # llm
    config_key = Column(String(100), nullable=False)  # api_key
    transform_rule = Column(String(50))  # none/decrypt/parse_json
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ConfigEnvMapping {self.env_var_name}>"

