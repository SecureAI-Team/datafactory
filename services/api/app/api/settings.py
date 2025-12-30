"""System settings API endpoints"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User
from ..models.settings import SystemConfig, ConfigChangeLog
from ..services.config_sync_service import ConfigSyncService
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/config", tags=["settings"])


# ==================== Request/Response Models ====================

class UpdateConfigRequest(BaseModel):
    value: str
    reason: Optional[str] = None


class ConfigResponse(BaseModel):
    id: int
    config_group: str
    config_key: str
    config_value: Any
    value_type: str
    description: Optional[str]
    is_secret: bool
    is_editable: bool
    default_value: Optional[str]
    source: str
    env_var_name: Optional[str]
    is_bootstrap: bool


class ConfigGroupResponse(BaseModel):
    group: str
    configs: List[ConfigResponse]


class SyncRequest(BaseModel):
    overwrite: bool = False


class SyncResponse(BaseModel):
    synced: int
    skipped: int
    errors: int


class CompareItem(BaseModel):
    config_key: str
    env_var: str
    env_value: Optional[str]
    db_value: Optional[str]
    source: str
    in_sync: bool


class FeatureToggleRequest(BaseModel):
    enabled: bool


# ==================== System Config Endpoints ====================

@router.get("/system")
async def get_all_configs(
    group: Optional[str] = None,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取所有系统配置（按分组）"""
    service = ConfigSyncService(db)
    configs = service.get_all_configs(group)
    
    grouped = {}
    for config in configs:
        if config.config_group not in grouped:
            grouped[config.config_group] = []
        grouped[config.config_group].append(config.to_dict())
    
    return {"configs": grouped}


@router.get("/system/{group}")
async def get_config_group(
    group: str,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取指定分组配置"""
    service = ConfigSyncService(db)
    configs = service.get_all_configs(group)
    
    if not configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config group '{group}' not found"
        )
    
    return {"group": group, "configs": [c.to_dict() for c in configs]}


@router.put("/system/{group}/{key}")
async def update_config(
    group: str,
    key: str,
    body: UpdateConfigRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """更新配置项"""
    # 检查配置是否存在且可编辑
    config = db.query(SystemConfig).filter(
        SystemConfig.config_group == group,
        SystemConfig.config_key == key
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config '{group}.{key}' not found"
        )
    
    if not config.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config '{group}.{key}' is not editable"
        )
    
    if config.is_bootstrap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bootstrap config '{group}.{key}' cannot be changed at runtime. Please modify .env and restart."
        )
    
    service = ConfigSyncService(db)
    updated = service.set_config(
        group, key, body.value,
        changed_by=admin.id,
        reason=body.reason
    )
    
    return {"message": "Config updated", "config": updated.to_dict()}


@router.get("/system/history/{config_id}")
async def get_config_history(
    config_id: int,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取配置变更历史"""
    logs = db.query(ConfigChangeLog).filter(
        ConfigChangeLog.config_id == config_id
    ).order_by(ConfigChangeLog.created_at.desc()).limit(50).all()
    
    return {
        "history": [
            {
                "id": log.id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "changed_by": log.changed_by,
                "change_reason": log.change_reason,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    }


# ==================== Sync Endpoints ====================

@router.post("/sync")
async def sync_from_env(
    body: SyncRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """从 .env 同步配置到数据库"""
    service = ConfigSyncService(db)
    stats = service.sync_from_env(overwrite=body.overwrite)
    return SyncResponse(**stats)


@router.get("/sync/compare")
async def compare_configs(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """对比 .env 与数据库配置"""
    service = ConfigSyncService(db)
    comparisons = service.compare_with_env()
    return {"comparisons": comparisons}


@router.get("/export")
async def export_configs(
    include_secrets: bool = False,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """导出配置为 .env 格式"""
    service = ConfigSyncService(db)
    content = service.export_to_env_format(include_secrets=include_secrets)
    return {"content": content}


# ==================== Feature Flags ====================

@router.get("/features")
async def get_features(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取功能开关列表"""
    configs = db.query(SystemConfig).filter(
        SystemConfig.config_group == "feature"
    ).all()
    
    return {
        "features": {
            c.config_key: {
                "enabled": c.config_value.lower() in ("true", "1", "yes") if c.config_value else False,
                "description": c.description
            }
            for c in configs
        }
    }


@router.put("/features/{key}")
async def toggle_feature(
    key: str,
    body: FeatureToggleRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """切换功能开关"""
    service = ConfigSyncService(db)
    config = service.toggle_feature(key, body.enabled, changed_by=admin.id)
    
    return {
        "message": f"Feature '{key}' {'enabled' if body.enabled else 'disabled'}",
        "feature": {
            "key": key,
            "enabled": body.enabled
        }
    }


# ==================== Integrations ====================

@router.get("/integrations")
async def get_integrations_status(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取集成服务状态"""
    service = ConfigSyncService(db)
    
    integrations = {
        "opensearch": {
            "url": service.get_config("integration", "opensearch_url"),
            "status": "unknown"
        },
        "minio": {
            "endpoint": service.get_config("integration", "minio_endpoint"),
            "status": "unknown"
        },
        "redis": {
            "url": service.get_config("integration", "redis_url"),
            "status": "unknown"
        },
        "neo4j": {
            "url": service.get_config("integration", "neo4j_url"),
            "status": "unknown"
        },
        "langfuse": {
            "url": service.get_config("integration", "langfuse_host"),
            "enabled": service.is_feature_enabled("langfuse_enabled"),
            "status": "unknown"
        }
    }
    
    # TODO: 实际检测各服务连接状态
    
    return {"integrations": integrations}


@router.post("/integrations/{service}/test")
async def test_integration(
    service: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """测试集成服务连接"""
    config_service = ConfigSyncService(db)
    
    # TODO: 实现各服务的连接测试
    if service == "opensearch":
        url = config_service.get_config("integration", "opensearch_url")
        # Test connection...
        return {"service": service, "status": "ok", "url": url}
    elif service == "minio":
        endpoint = config_service.get_config("integration", "minio_endpoint")
        return {"service": service, "status": "ok", "endpoint": endpoint}
    elif service == "redis":
        url = config_service.get_config("integration", "redis_url")
        return {"service": service, "status": "ok", "url": url}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service: {service}"
        )

