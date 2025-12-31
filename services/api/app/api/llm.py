"""LLM Configuration API endpoints - Providers, Models, Assignments"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db
from ..models.user import User
from ..models.llm import LLMProvider, LLMModel, LLMModelAssignment
from .auth import require_role

router = APIRouter(prefix="/api/config/llm", tags=["llm-config"])


# ==================== Request Models ====================

class ProviderCreateRequest(BaseModel):
    provider_code: str
    provider_name: str
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    config: Optional[dict] = {}


class ProviderUpdateRequest(BaseModel):
    provider_name: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    config: Optional[dict] = None


class ModelCreateRequest(BaseModel):
    provider_id: int
    model_code: str
    model_name: str
    model_type: str  # chat/embedding/vision/audio
    capabilities: Optional[List[str]] = []
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None
    is_active: bool = True
    is_default: bool = False
    config: Optional[dict] = {}


class ModelUpdateRequest(BaseModel):
    model_name: Optional[str] = None
    model_type: Optional[str] = None
    capabilities: Optional[List[str]] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    config: Optional[dict] = None


class AssignmentUpdateRequest(BaseModel):
    model_id: int
    fallback_model_id: Optional[int] = None
    config_override: Optional[dict] = {}


class LLMTestRequest(BaseModel):
    model_code: str
    prompt: str
    max_tokens: Optional[int] = 100


# ==================== Provider Endpoints ====================

@router.get("/providers")
async def list_providers(
    active_only: bool = False,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取 LLM 提供商列表"""
    query = db.query(LLMProvider)
    
    if active_only:
        query = query.filter(LLMProvider.is_active == True)
    
    providers = query.order_by(LLMProvider.provider_code).all()
    
    return {"providers": [p.to_dict() for p in providers]}


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: int,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取提供商详情"""
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    return provider.to_dict()


@router.post("/providers")
async def create_provider(
    body: ProviderCreateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """创建 LLM 提供商"""
    existing = db.query(LLMProvider).filter(
        LLMProvider.provider_code == body.provider_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{body.provider_code}' already exists"
        )
    
    # If setting as default, unset other defaults
    if body.is_default:
        db.query(LLMProvider).filter(
            LLMProvider.is_default == True
        ).update({"is_default": False})
    
    provider = LLMProvider(
        provider_code=body.provider_code,
        provider_name=body.provider_name,
        api_base_url=body.api_base_url,
        api_key_encrypted=body.api_key,  # TODO: Encrypt this
        is_active=body.is_active,
        is_default=body.is_default,
        config=body.config or {}
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    return {"message": "Provider created", "provider": provider.to_dict()}


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: int,
    body: ProviderUpdateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """更新 LLM 提供商"""
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # If setting as default, unset other defaults
    if body.is_default:
        db.query(LLMProvider).filter(
            LLMProvider.id != provider_id,
            LLMProvider.is_default == True
        ).update({"is_default": False})
    
    if body.provider_name is not None:
        provider.provider_name = body.provider_name
    if body.api_base_url is not None:
        provider.api_base_url = body.api_base_url
    if body.api_key is not None:
        provider.api_key_encrypted = body.api_key  # TODO: Encrypt this
    if body.is_active is not None:
        provider.is_active = body.is_active
    if body.is_default is not None:
        provider.is_default = body.is_default
    if body.config is not None:
        provider.config = body.config
    
    provider.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(provider)
    
    return {"message": "Provider updated", "provider": provider.to_dict()}


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除 LLM 提供商"""
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Check if provider has models
    model_count = db.query(LLMModel).filter(
        LLMModel.provider_id == provider_id
    ).count()
    
    if model_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete provider with {model_count} models. Delete models first."
        )
    
    db.delete(provider)
    db.commit()
    
    return {"message": "Provider deleted", "provider_id": provider_id}


@router.post("/providers/{provider_id}/test")
async def test_provider_connection(
    provider_id: int,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """测试 LLM 提供商连接"""
    import httpx
    import os
    
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Get API key - from provider config or environment
    api_key = provider.api_key_encrypted
    if not api_key:
        # Try to get from environment based on provider code
        env_keys = {
            "qwen": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
        }
        env_var = env_keys.get(provider.provider_code)
        if env_var:
            api_key = os.getenv(env_var)
    
    if not api_key:
        return {
            "provider_id": provider_id,
            "provider_code": provider.provider_code,
            "success": False,
            "message": "API Key 未配置"
        }
    
    # Test connection by listing models or making a simple request
    api_base = provider.api_base_url
    if not api_base:
        return {
            "provider_id": provider_id,
            "provider_code": provider.provider_code,
            "success": False,
            "message": "API Base URL 未配置"
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to list models endpoint (works for most OpenAI-compatible APIs)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Different providers have different endpoints
            if provider.provider_code == "qwen":
                # DashScope uses a different endpoint
                test_url = f"{api_base}/models"
            else:
                test_url = f"{api_base}/models"
            
            response = await client.get(test_url, headers=headers)
            
            if response.status_code == 200:
                return {
                    "provider_id": provider_id,
                    "provider_code": provider.provider_code,
                    "success": True,
                    "message": "连接成功"
                }
            elif response.status_code == 401:
                return {
                    "provider_id": provider_id,
                    "provider_code": provider.provider_code,
                    "success": False,
                    "message": "认证失败，请检查 API Key"
                }
            else:
                return {
                    "provider_id": provider_id,
                    "provider_code": provider.provider_code,
                    "success": False,
                    "message": f"请求失败: HTTP {response.status_code}"
                }
    except httpx.TimeoutException:
        return {
            "provider_id": provider_id,
            "provider_code": provider.provider_code,
            "success": False,
            "message": "连接超时，请检查网络或 API 地址"
        }
    except httpx.ConnectError:
        return {
            "provider_id": provider_id,
            "provider_code": provider.provider_code,
            "success": False,
            "message": "无法连接到服务器，请检查 API 地址"
        }
    except Exception as e:
        return {
            "provider_id": provider_id,
            "provider_code": provider.provider_code,
            "success": False,
            "message": f"测试失败: {str(e)}"
        }


# ==================== Model Endpoints ====================

@router.get("/models")
async def list_models(
    provider_id: Optional[int] = None,
    model_type: Optional[str] = None,
    active_only: bool = False,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取 LLM 模型列表"""
    query = db.query(LLMModel)
    
    if provider_id:
        query = query.filter(LLMModel.provider_id == provider_id)
    
    if model_type:
        query = query.filter(LLMModel.model_type == model_type)
    
    if active_only:
        query = query.filter(LLMModel.is_active == True)
    
    models = query.order_by(LLMModel.model_code).all()
    
    # Include provider info
    result = []
    for model in models:
        data = model.to_dict()
        if model.provider:
            data["provider_code"] = model.provider.provider_code
            data["provider_name"] = model.provider.provider_name
        result.append(data)
    
    return {"models": result}


@router.get("/models/{model_id}")
async def get_model(
    model_id: int,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取模型详情"""
    model = db.query(LLMModel).filter(
        LLMModel.id == model_id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    data = model.to_dict()
    if model.provider:
        data["provider_code"] = model.provider.provider_code
        data["provider_name"] = model.provider.provider_name
    
    return data


@router.post("/models")
async def create_model(
    body: ModelCreateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """创建 LLM 模型"""
    # Verify provider exists
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == body.provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Check for duplicate
    existing = db.query(LLMModel).filter(
        LLMModel.provider_id == body.provider_id,
        LLMModel.model_code == body.model_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{body.model_code}' already exists for this provider"
        )
    
    valid_types = ["chat", "embedding", "vision", "audio"]
    if body.model_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model_type. Must be one of: {valid_types}"
        )
    
    # If setting as default, unset other defaults of same type
    if body.is_default:
        db.query(LLMModel).filter(
            LLMModel.model_type == body.model_type,
            LLMModel.is_default == True
        ).update({"is_default": False})
    
    model = LLMModel(
        provider_id=body.provider_id,
        model_code=body.model_code,
        model_name=body.model_name,
        model_type=body.model_type,
        capabilities=body.capabilities or [],
        context_window=body.context_window,
        max_output_tokens=body.max_output_tokens,
        cost_per_1k_input=body.cost_per_1k_input,
        cost_per_1k_output=body.cost_per_1k_output,
        is_active=body.is_active,
        is_default=body.is_default,
        config=body.config or {}
    )
    
    db.add(model)
    db.commit()
    db.refresh(model)
    
    return {"message": "Model created", "model": model.to_dict()}


@router.put("/models/{model_id}")
async def update_model(
    model_id: int,
    body: ModelUpdateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """更新 LLM 模型"""
    model = db.query(LLMModel).filter(
        LLMModel.id == model_id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # If setting as default, unset other defaults of same type
    if body.is_default:
        db.query(LLMModel).filter(
            LLMModel.id != model_id,
            LLMModel.model_type == model.model_type,
            LLMModel.is_default == True
        ).update({"is_default": False})
    
    if body.model_name is not None:
        model.model_name = body.model_name
    if body.model_type is not None:
        valid_types = ["chat", "embedding", "vision", "audio"]
        if body.model_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model_type. Must be one of: {valid_types}"
            )
        model.model_type = body.model_type
    if body.capabilities is not None:
        model.capabilities = body.capabilities
    if body.context_window is not None:
        model.context_window = body.context_window
    if body.max_output_tokens is not None:
        model.max_output_tokens = body.max_output_tokens
    if body.cost_per_1k_input is not None:
        model.cost_per_1k_input = body.cost_per_1k_input
    if body.cost_per_1k_output is not None:
        model.cost_per_1k_output = body.cost_per_1k_output
    if body.is_active is not None:
        model.is_active = body.is_active
    if body.is_default is not None:
        model.is_default = body.is_default
    if body.config is not None:
        model.config = body.config
    
    model.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(model)
    
    return {"message": "Model updated", "model": model.to_dict()}


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除 LLM 模型"""
    model = db.query(LLMModel).filter(
        LLMModel.id == model_id
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Check if model is used in assignments
    assignment_count = db.query(LLMModelAssignment).filter(
        (LLMModelAssignment.model_id == model_id) |
        (LLMModelAssignment.fallback_model_id == model_id)
    ).count()
    
    if assignment_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete model used in {assignment_count} assignments"
        )
    
    db.delete(model)
    db.commit()
    
    return {"message": "Model deleted", "model_id": model_id}


# ==================== Assignment Endpoints ====================

@router.get("/assignments")
async def list_assignments(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取模型使用场景分配"""
    assignments = db.query(LLMModelAssignment).order_by(
        LLMModelAssignment.use_case
    ).all()
    
    # Enrich with model info
    result = []
    for assignment in assignments:
        data = assignment.to_dict()
        
        if assignment.model_id:
            model = db.query(LLMModel).filter(LLMModel.id == assignment.model_id).first()
            if model:
                data["model_code"] = model.model_code
                data["model_name"] = model.model_name
        
        if assignment.fallback_model_id:
            fallback = db.query(LLMModel).filter(LLMModel.id == assignment.fallback_model_id).first()
            if fallback:
                data["fallback_model_code"] = fallback.model_code
                data["fallback_model_name"] = fallback.model_name
        
        result.append(data)
    
    return {"assignments": result}


@router.get("/assignments/{use_case}")
async def get_assignment(
    use_case: str,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取特定场景的模型分配"""
    assignment = db.query(LLMModelAssignment).filter(
        LLMModelAssignment.use_case == use_case
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment for '{use_case}' not found"
        )
    
    data = assignment.to_dict()
    
    if assignment.model_id:
        model = db.query(LLMModel).filter(LLMModel.id == assignment.model_id).first()
        if model:
            data["model_code"] = model.model_code
            data["model_name"] = model.model_name
    
    return data


@router.put("/assignments/{use_case}")
async def update_assignment(
    use_case: str,
    body: AssignmentUpdateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """更新模型使用场景分配"""
    # Verify model exists
    model = db.query(LLMModel).filter(LLMModel.id == body.model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Verify fallback model if provided
    if body.fallback_model_id:
        fallback = db.query(LLMModel).filter(LLMModel.id == body.fallback_model_id).first()
        if not fallback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fallback model not found"
            )
    
    assignment = db.query(LLMModelAssignment).filter(
        LLMModelAssignment.use_case == use_case
    ).first()
    
    if not assignment:
        # Create new assignment
        assignment = LLMModelAssignment(
            use_case=use_case,
            model_id=body.model_id,
            fallback_model_id=body.fallback_model_id,
            config_override=body.config_override or {},
            is_active=True
        )
        db.add(assignment)
    else:
        assignment.model_id = body.model_id
        assignment.fallback_model_id = body.fallback_model_id
        if body.config_override is not None:
            assignment.config_override = body.config_override
        assignment.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(assignment)
    
    return {"message": "Assignment updated", "assignment": assignment.to_dict()}


# ==================== Test Endpoint ====================

@router.post("/test")
async def test_llm_call(
    body: LLMTestRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """测试 LLM 调用"""
    import httpx
    import os
    import time
    
    # Find the model
    model = db.query(LLMModel).filter(
        LLMModel.model_code == body.model_code
    ).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{body.model_code}' not found"
        )
    
    if not model.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{body.model_code}' is not active"
        )
    
    # Get provider
    provider = db.query(LLMProvider).filter(
        LLMProvider.id == model.provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found for this model"
        )
    
    # Get API key
    api_key = provider.api_key_encrypted
    if not api_key:
        env_keys = {
            "qwen": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
        }
        env_var = env_keys.get(provider.provider_code)
        if env_var:
            api_key = os.getenv(env_var)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key not configured for this provider"
        )
    
    api_base = provider.api_base_url
    if not api_base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Base URL not configured for this provider"
        )
    
    # Make test LLM call
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            request_body = {
                "model": body.model_code,
                "messages": [
                    {"role": "user", "content": body.prompt}
                ],
                "max_tokens": body.max_tokens or 100,
                "temperature": 0.7
            }
            
            response = await client.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=request_body
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                
                return {
                    "model_code": body.model_code,
                    "prompt": body.prompt,
                    "success": True,
                    "response": content,
                    "tokens_used": usage.get("total_tokens", 0),
                    "latency_ms": latency_ms
                }
            else:
                error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                return {
                    "model_code": body.model_code,
                    "prompt": body.prompt,
                    "success": False,
                    "response": f"请求失败: {error_msg}",
                    "tokens_used": 0,
                    "latency_ms": latency_ms
                }
    except httpx.TimeoutException:
        return {
            "model_code": body.model_code,
            "prompt": body.prompt,
            "success": False,
            "response": "请求超时",
            "tokens_used": 0,
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    except Exception as e:
        return {
            "model_code": body.model_code,
            "prompt": body.prompt,
            "success": False,
            "response": f"调用失败: {str(e)}",
            "tokens_used": 0,
            "latency_ms": int((time.time() - start_time) * 1000)
        }

