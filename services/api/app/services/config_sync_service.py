"""Configuration sync service - .env ↔ Database"""
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from ..models.settings import SystemConfig, ConfigEnvMapping, ConfigChangeLog


class ConfigSyncService:
    """配置同步服务 - 处理 .env 与数据库的同步"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Config CRUD ====================
    
    def get_config(self, group: str, key: str) -> Optional[str]:
        """获取配置值（运行时调用）"""
        config = self.db.query(SystemConfig).filter(
            SystemConfig.config_group == group,
            SystemConfig.config_key == key
        ).first()
        
        if config:
            # 启动必需配置优先从环境变量读取
            if config.is_bootstrap and config.env_var_name:
                env_value = os.getenv(config.env_var_name)
                if env_value:
                    return env_value
            return config.config_value
        
        # 回退到环境变量
        mapping = self.db.query(ConfigEnvMapping).filter(
            ConfigEnvMapping.config_group == group,
            ConfigEnvMapping.config_key == key
        ).first()
        
        if mapping:
            return os.getenv(mapping.env_var_name)
        
        return None
    
    def get_config_typed(self, group: str, key: str) -> Any:
        """获取配置值并转换类型"""
        config = self.db.query(SystemConfig).filter(
            SystemConfig.config_group == group,
            SystemConfig.config_key == key
        ).first()
        
        if config:
            return config.get_value()
        
        return None
    
    def set_config(
        self,
        group: str,
        key: str,
        value: str,
        changed_by: int = None,
        reason: str = None
    ) -> SystemConfig:
        """设置配置值"""
        config = self.db.query(SystemConfig).filter(
            SystemConfig.config_group == group,
            SystemConfig.config_key == key
        ).first()
        
        if config:
            old_value = config.config_value
            config.config_value = value
            config.source = "database"
            config.updated_by = changed_by
            config.updated_at = datetime.now(timezone.utc)
            
            # 记录变更历史
            if old_value != value:
                log = ConfigChangeLog(
                    config_id=config.id,
                    old_value=old_value,
                    new_value=value,
                    changed_by=changed_by,
                    change_reason=reason
                )
                self.db.add(log)
        else:
            config = SystemConfig(
                config_group=group,
                config_key=key,
                config_value=value,
                source="database",
                updated_by=changed_by
            )
            self.db.add(config)
        
        self.db.commit()
        self.db.refresh(config)
        return config
    
    def get_all_configs(self, group: str = None) -> List[SystemConfig]:
        """获取所有配置"""
        query = self.db.query(SystemConfig)
        if group:
            query = query.filter(SystemConfig.config_group == group)
        return query.order_by(SystemConfig.config_group, SystemConfig.config_key).all()
    
    def get_configs_by_group(self) -> Dict[str, List[Dict]]:
        """按分组获取配置"""
        configs = self.get_all_configs()
        grouped = {}
        for config in configs:
            if config.config_group not in grouped:
                grouped[config.config_group] = []
            grouped[config.config_group].append(config.to_dict())
        return grouped
    
    # ==================== Sync Operations ====================
    
    def get_env_mappings(self) -> List[ConfigEnvMapping]:
        """获取所有环境变量映射"""
        return self.db.query(ConfigEnvMapping).all()
    
    def sync_from_env(self, overwrite: bool = False) -> Dict[str, int]:
        """从环境变量同步到数据库
        
        Args:
            overwrite: 是否覆盖数据库中已有的值
        
        Returns:
            统计信息 {"synced": N, "skipped": N}
        """
        mappings = self.get_env_mappings()
        stats = {"synced": 0, "skipped": 0, "errors": 0}
        
        for mapping in mappings:
            env_value = os.getenv(mapping.env_var_name)
            if env_value is None:
                stats["skipped"] += 1
                continue
            
            try:
                config = self.db.query(SystemConfig).filter(
                    SystemConfig.config_group == mapping.config_group,
                    SystemConfig.config_key == mapping.config_key
                ).first()
                
                if config:
                    # 配置已存在
                    if overwrite or config.source == "env":
                        config.config_value = env_value
                        config.source = "synced"
                        config.last_synced_at = datetime.now(timezone.utc)
                        stats["synced"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    # 创建新配置
                    new_config = SystemConfig(
                        config_group=mapping.config_group,
                        config_key=mapping.config_key,
                        config_value=env_value,
                        source="synced",
                        env_var_name=mapping.env_var_name,
                        is_secret=mapping.is_secret,
                        last_synced_at=datetime.now(timezone.utc)
                    )
                    self.db.add(new_config)
                    stats["synced"] += 1
                
                self.db.commit()
            except Exception as e:
                stats["errors"] += 1
                self.db.rollback()
        
        return stats
    
    def export_to_env_format(self, include_secrets: bool = False) -> str:
        """导出配置为 .env 格式
        
        Args:
            include_secrets: 是否包含敏感信息
        
        Returns:
            .env 格式的配置字符串
        """
        configs = self.get_all_configs()
        lines = ["# Generated from database configuration"]
        lines.append(f"# Exported at: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        
        current_group = None
        for config in configs:
            if not config.env_var_name:
                continue
            
            # 添加分组注释
            if config.config_group != current_group:
                current_group = config.config_group
                lines.append(f"# {current_group.upper()}")
            
            # 处理敏感信息
            if config.is_secret and not include_secrets:
                value = "*** REDACTED ***"
            else:
                value = config.config_value or ""
            
            lines.append(f"{config.env_var_name}={value}")
        
        return "\n".join(lines)
    
    def compare_with_env(self) -> List[Dict[str, Any]]:
        """对比数据库配置与环境变量
        
        Returns:
            对比结果列表
        """
        configs = self.get_all_configs()
        comparisons = []
        
        for config in configs:
            if not config.env_var_name:
                continue
            
            env_value = os.getenv(config.env_var_name)
            db_value = config.config_value
            
            # 敏感信息掩码显示
            if config.is_secret:
                env_display = "****" if env_value else None
                db_display = "****" if db_value else None
            else:
                env_display = env_value
                db_display = db_value
            
            comparisons.append({
                "config_key": f"{config.config_group}.{config.config_key}",
                "env_var": config.env_var_name,
                "env_value": env_display,
                "db_value": db_display,
                "source": config.source,
                "in_sync": env_value == db_value if env_value else True
            })
        
        return comparisons
    
    # ==================== Validation ====================
    
    def validate_required_configs(self) -> List[str]:
        """验证必需配置是否存在
        
        Returns:
            缺失的配置列表
        """
        required_configs = [
            ("integration", "opensearch_url"),
            ("integration", "minio_endpoint"),
        ]
        
        missing = []
        for group, key in required_configs:
            value = self.get_config(group, key)
            if not value:
                missing.append(f"{group}.{key}")
        
        return missing
    
    # ==================== Feature Flags ====================
    
    def is_feature_enabled(self, feature_key: str) -> bool:
        """检查功能开关是否启用"""
        value = self.get_config("feature", feature_key)
        if value is None:
            return False
        return value.lower() in ("true", "1", "yes")
    
    def toggle_feature(self, feature_key: str, enabled: bool, changed_by: int = None) -> SystemConfig:
        """切换功能开关"""
        return self.set_config(
            "feature",
            feature_key,
            "true" if enabled else "false",
            changed_by=changed_by,
            reason=f"Feature {'enabled' if enabled else 'disabled'}"
        )

