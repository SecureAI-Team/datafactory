"""Configuration management API endpoints - Scenarios, Prompts, KU Types"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc

from ..db import get_db
from ..models.user import User
from ..models.config import ScenarioConfig, PromptTemplate, PromptHistory, KUTypeDefinition, ParameterDefinition, CalculationRule, InteractionFlow, InteractionSession
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/config", tags=["config"])


# ==================== Scenario Models ====================

class ScenarioCreateRequest(BaseModel):
    scenario_id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    intent_patterns: Optional[List[dict]] = []
    retrieval_config: Optional[dict] = {}
    response_template: Optional[str] = None
    quick_commands: Optional[List[dict]] = []
    is_active: bool = True
    sort_order: int = 0


class ScenarioUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    intent_patterns: Optional[List[dict]] = None
    retrieval_config: Optional[dict] = None
    response_template: Optional[str] = None
    quick_commands: Optional[List[dict]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ==================== Prompt Models ====================

class PromptCreateRequest(BaseModel):
    name: str
    type: str  # system/user/intent/response/summary
    scenario_id: Optional[str] = None
    template: str
    variables: Optional[List[dict]] = []
    is_active: bool = True


class PromptUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    scenario_id: Optional[str] = None
    template: Optional[str] = None
    variables: Optional[List[dict]] = None
    is_active: Optional[bool] = None
    change_reason: Optional[str] = None


class PromptRevertRequest(BaseModel):
    version: int


# ==================== KU Type Models ====================

class KUTypeCreateRequest(BaseModel):
    type_code: str
    category: str
    display_name: str
    description: Optional[str] = None
    merge_strategy: str = "independent"
    requires_expiry: bool = False
    requires_approval: bool = True
    visibility_default: str = "internal"
    icon: Optional[str] = None
    sort_order: int = 0


class KUTypeUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    merge_strategy: Optional[str] = None
    requires_expiry: Optional[bool] = None
    requires_approval: Optional[bool] = None
    visibility_default: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ==================== Scenario Endpoints ====================

@router.get("/scenarios")
async def list_scenarios(
    active_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取场景列表"""
    try:
        query = db.query(ScenarioConfig)
        
        if active_only:
            query = query.filter(ScenarioConfig.is_active == True)
        
        scenarios = query.order_by(ScenarioConfig.sort_order).all()
        
        return {"scenarios": [s.to_dict() for s in scenarios]}
    except Exception:
        # Table may not exist yet
        return {"scenarios": []}


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取场景详情"""
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id
    ).first()
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    return scenario.to_dict()


@router.post("/scenarios")
async def create_scenario(
    body: ScenarioCreateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """创建场景"""
    # Check if scenario_id already exists
    existing = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == body.scenario_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario '{body.scenario_id}' already exists"
        )
    
    scenario = ScenarioConfig(
        scenario_id=body.scenario_id,
        name=body.name,
        description=body.description,
        icon=body.icon,
        intent_patterns=body.intent_patterns,
        retrieval_config=body.retrieval_config,
        response_template=body.response_template,
        quick_commands=body.quick_commands,
        is_active=body.is_active,
        sort_order=body.sort_order,
        created_by=admin.id
    )
    
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    
    return {"message": "Scenario created", "scenario": scenario.to_dict()}


@router.put("/scenarios/{scenario_id}")
async def update_scenario(
    scenario_id: str,
    body: ScenarioUpdateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """更新场景"""
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id
    ).first()
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    if body.name is not None:
        scenario.name = body.name
    if body.description is not None:
        scenario.description = body.description
    if body.icon is not None:
        scenario.icon = body.icon
    if body.intent_patterns is not None:
        scenario.intent_patterns = body.intent_patterns
    if body.retrieval_config is not None:
        scenario.retrieval_config = body.retrieval_config
    if body.response_template is not None:
        scenario.response_template = body.response_template
    if body.quick_commands is not None:
        scenario.quick_commands = body.quick_commands
    if body.is_active is not None:
        scenario.is_active = body.is_active
    if body.sort_order is not None:
        scenario.sort_order = body.sort_order
    
    scenario.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scenario)
    
    return {"message": "Scenario updated", "scenario": scenario.to_dict()}


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除场景"""
    scenario = db.query(ScenarioConfig).filter(
        ScenarioConfig.scenario_id == scenario_id
    ).first()
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    db.delete(scenario)
    db.commit()
    
    return {"message": "Scenario deleted", "scenario_id": scenario_id}


# ==================== Prompt Endpoints ====================

@router.get("/prompts")
async def list_prompts(
    type_filter: Optional[str] = None,
    scenario_id: Optional[str] = None,
    active_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取 Prompt 列表"""
    try:
        query = db.query(PromptTemplate)
        
        if type_filter:
            query = query.filter(PromptTemplate.type == type_filter)
        
        if scenario_id:
            query = query.filter(PromptTemplate.scenario_id == scenario_id)
        
        if active_only:
            query = query.filter(PromptTemplate.is_active == True)
        
        prompts = query.order_by(PromptTemplate.name).all()
        
        return {"prompts": [p.to_dict() for p in prompts]}
    except Exception:
        # Table may not exist yet
        return {"prompts": []}


@router.get("/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取 Prompt 详情"""
    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == prompt_id
    ).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    
    return prompt.to_dict()


@router.post("/prompts")
async def create_prompt(
    body: PromptCreateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """创建 Prompt"""
    valid_types = ["system", "user", "intent", "response", "summary"]
    if body.type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type. Must be one of: {valid_types}"
        )
    
    prompt = PromptTemplate(
        name=body.name,
        type=body.type,
        scenario_id=body.scenario_id,
        template=body.template,
        variables=body.variables,
        version=1,
        is_active=body.is_active,
        created_by=admin.id
    )
    
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    
    return {"message": "Prompt created", "prompt": prompt.to_dict()}


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: int,
    body: PromptUpdateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """更新 Prompt（自动保存历史版本）"""
    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == prompt_id
    ).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    
    # Save history before update if template is changing
    if body.template is not None and body.template != prompt.template:
        history = PromptHistory(
            prompt_id=prompt.id,
            version=prompt.version,
            template=prompt.template,
            changed_by=admin.id,
            change_reason=body.change_reason
        )
        db.add(history)
        prompt.version += 1
    
    if body.name is not None:
        prompt.name = body.name
    if body.type is not None:
        valid_types = ["system", "user", "intent", "response", "summary"]
        if body.type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type. Must be one of: {valid_types}"
            )
        prompt.type = body.type
    if body.scenario_id is not None:
        prompt.scenario_id = body.scenario_id
    if body.template is not None:
        prompt.template = body.template
    if body.variables is not None:
        prompt.variables = body.variables
    if body.is_active is not None:
        prompt.is_active = body.is_active
    
    prompt.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(prompt)
    
    return {"message": "Prompt updated", "prompt": prompt.to_dict()}


@router.get("/prompts/{prompt_id}/history")
async def get_prompt_history(
    prompt_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取 Prompt 历史版本"""
    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == prompt_id
    ).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    
    history = db.query(PromptHistory).filter(
        PromptHistory.prompt_id == prompt_id
    ).order_by(desc(PromptHistory.version)).all()
    
    return {
        "current_version": prompt.version,
        "history": [
            {
                "id": h.id,
                "version": h.version,
                "template": h.template,
                "changed_by": h.changed_by,
                "change_reason": h.change_reason,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in history
        ]
    }


@router.post("/prompts/{prompt_id}/revert")
async def revert_prompt(
    prompt_id: int,
    body: PromptRevertRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """回滚到指定版本"""
    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == prompt_id
    ).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    
    # Find the target version in history
    target = db.query(PromptHistory).filter(
        PromptHistory.prompt_id == prompt_id,
        PromptHistory.version == body.version
    ).first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {body.version} not found"
        )
    
    # Save current version to history
    history = PromptHistory(
        prompt_id=prompt.id,
        version=prompt.version,
        template=prompt.template,
        changed_by=admin.id,
        change_reason=f"Reverted to version {body.version}"
    )
    db.add(history)
    
    # Apply the reverted template
    prompt.template = target.template
    prompt.version += 1
    prompt.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(prompt)
    
    return {"message": f"Reverted to version {body.version}", "prompt": prompt.to_dict()}


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除 Prompt"""
    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == prompt_id
    ).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    
    db.delete(prompt)
    db.commit()
    
    return {"message": "Prompt deleted", "prompt_id": prompt_id}


# ==================== KU Type Endpoints ====================

@router.get("/ku-types")
async def list_ku_types(
    category: Optional[str] = None,
    active_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取 KU 类型列表"""
    try:
        query = db.query(KUTypeDefinition)
        
        if category:
            query = query.filter(KUTypeDefinition.category == category)
        
        if active_only:
            query = query.filter(KUTypeDefinition.is_active == True)
        
        ku_types = query.order_by(
            KUTypeDefinition.category,
            KUTypeDefinition.sort_order
        ).all()
        
        return {"ku_types": [t.to_dict() for t in ku_types]}
    except Exception:
        # Table may not exist yet
        return {"ku_types": []}


@router.get("/ku-types/{type_code}")
async def get_ku_type(
    type_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取 KU 类型详情"""
    ku_type = db.query(KUTypeDefinition).filter(
        KUTypeDefinition.type_code == type_code
    ).first()
    
    if not ku_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KU type not found"
        )
    
    return ku_type.to_dict()


@router.post("/ku-types")
async def create_ku_type(
    body: KUTypeCreateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """创建 KU 类型"""
    existing = db.query(KUTypeDefinition).filter(
        KUTypeDefinition.type_code == body.type_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"KU type '{body.type_code}' already exists"
        )
    
    valid_categories = ["product", "solution", "case", "quote", "biz", "delivery", "field", "sales"]
    if body.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )
    
    ku_type = KUTypeDefinition(
        type_code=body.type_code,
        category=body.category,
        display_name=body.display_name,
        description=body.description,
        merge_strategy=body.merge_strategy,
        requires_expiry=body.requires_expiry,
        requires_approval=body.requires_approval,
        visibility_default=body.visibility_default,
        icon=body.icon,
        sort_order=body.sort_order
    )
    
    db.add(ku_type)
    db.commit()
    db.refresh(ku_type)
    
    return {"message": "KU type created", "ku_type": ku_type.to_dict()}


@router.put("/ku-types/{type_code}")
async def update_ku_type(
    type_code: str,
    body: KUTypeUpdateRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """更新 KU 类型"""
    ku_type = db.query(KUTypeDefinition).filter(
        KUTypeDefinition.type_code == type_code
    ).first()
    
    if not ku_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KU type not found"
        )
    
    if body.display_name is not None:
        ku_type.display_name = body.display_name
    if body.description is not None:
        ku_type.description = body.description
    if body.merge_strategy is not None:
        ku_type.merge_strategy = body.merge_strategy
    if body.requires_expiry is not None:
        ku_type.requires_expiry = body.requires_expiry
    if body.requires_approval is not None:
        ku_type.requires_approval = body.requires_approval
    if body.visibility_default is not None:
        ku_type.visibility_default = body.visibility_default
    if body.icon is not None:
        ku_type.icon = body.icon
    if body.sort_order is not None:
        ku_type.sort_order = body.sort_order
    if body.is_active is not None:
        ku_type.is_active = body.is_active
    
    db.commit()
    db.refresh(ku_type)
    
    return {"message": "KU type updated", "ku_type": ku_type.to_dict()}


@router.delete("/ku-types/{type_code}")
async def delete_ku_type(
    type_code: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除 KU 类型（软删除，设为不活跃）"""
    ku_type = db.query(KUTypeDefinition).filter(
        KUTypeDefinition.type_code == type_code
    ).first()
    
    if not ku_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KU type not found"
        )
    
    # Soft delete - just mark as inactive
    ku_type.is_active = False
    db.commit()
    
    return {"message": "KU type deactivated", "type_code": type_code}


# ==================== Parameter Definition Models ====================

class ParameterCreateRequest(BaseModel):
    name: str
    code: str
    data_type: str  # string/number/boolean/array
    unit: Optional[str] = None
    category: Optional[str] = None
    synonyms: Optional[List[str]] = []
    validation_rules: Optional[dict] = {}
    description: Optional[str] = None
    is_system: bool = False


class ParameterUpdateRequest(BaseModel):
    name: Optional[str] = None
    data_type: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    synonyms: Optional[List[str]] = None
    validation_rules: Optional[dict] = None
    description: Optional[str] = None


# ==================== Parameter Definition Endpoints ====================

@router.get("/parameters")
async def get_parameters(
    category: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取参数定义列表"""
    try:
        query = db.query(ParameterDefinition)
        
        if category:
            query = query.filter(ParameterDefinition.category == category)
        
        parameters = query.order_by(ParameterDefinition.category, ParameterDefinition.name).all()
        
        return {"parameters": [p.to_dict() for p in parameters]}
    except Exception:
        # Table may not exist yet
        return {"parameters": []}


@router.get("/parameters/{param_id}")
async def get_parameter(
    param_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个参数定义"""
    param = db.query(ParameterDefinition).filter(ParameterDefinition.id == param_id).first()
    
    if not param:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parameter not found"
        )
    
    return param.to_dict()


@router.post("/parameters")
async def create_parameter(
    body: ParameterCreateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """创建参数定义"""
    # Check for duplicate code
    existing = db.query(ParameterDefinition).filter(
        ParameterDefinition.code == body.code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parameter code already exists"
        )
    
    param = ParameterDefinition(
        name=body.name,
        code=body.code,
        data_type=body.data_type,
        unit=body.unit,
        category=body.category,
        synonyms=body.synonyms or [],
        validation_rules=body.validation_rules or {},
        description=body.description,
        is_system=body.is_system,
        updated_by=admin.id,
    )
    
    db.add(param)
    db.commit()
    db.refresh(param)
    
    return {"message": "Parameter created", "parameter": param.to_dict()}


@router.put("/parameters/{param_id}")
async def update_parameter(
    param_id: int,
    body: ParameterUpdateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """更新参数定义"""
    param = db.query(ParameterDefinition).filter(ParameterDefinition.id == param_id).first()
    
    if not param:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parameter not found"
        )
    
    # System parameters can only be updated by admin
    if param.is_system and admin.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System parameters can only be modified by admin"
        )
    
    if body.name is not None:
        param.name = body.name
    if body.data_type is not None:
        param.data_type = body.data_type
    if body.unit is not None:
        param.unit = body.unit
    if body.category is not None:
        param.category = body.category
    if body.synonyms is not None:
        param.synonyms = body.synonyms
    if body.validation_rules is not None:
        param.validation_rules = body.validation_rules
    if body.description is not None:
        param.description = body.description
    
    param.updated_by = admin.id
    db.commit()
    db.refresh(param)
    
    return {"message": "Parameter updated", "parameter": param.to_dict()}


@router.delete("/parameters/{param_id}")
async def delete_parameter(
    param_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除参数定义"""
    param = db.query(ParameterDefinition).filter(ParameterDefinition.id == param_id).first()
    
    if not param:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parameter not found"
        )
    
    if param.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system parameters"
        )
    
    db.delete(param)
    db.commit()
    
    return {"message": "Parameter deleted", "id": param_id}


# ==================== Calculation Rule Models ====================

class CalcRuleCreateRequest(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    formula: str
    input_params: Optional[List[str]] = []
    output_type: str = "number"
    examples: Optional[List[dict]] = []
    is_active: bool = True


class CalcRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    formula: Optional[str] = None
    input_params: Optional[List[str]] = None
    output_type: Optional[str] = None
    examples: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class CalcRuleTestRequest(BaseModel):
    inputs: dict


# ==================== Calculation Rule Endpoints ====================

@router.get("/calc-rules")
async def get_calc_rules(
    is_active: Optional[bool] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取计算规则列表"""
    try:
        query = db.query(CalculationRule)
        
        if is_active is not None:
            query = query.filter(CalculationRule.is_active == is_active)
        
        rules = query.order_by(CalculationRule.name).all()
        
        return {"rules": [r.to_dict() for r in rules]}
    except Exception:
        # Table may not exist yet
        return {"rules": []}


@router.get("/calc-rules/{rule_id}")
async def get_calc_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个计算规则"""
    rule = db.query(CalculationRule).filter(CalculationRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation rule not found"
        )
    
    return rule.to_dict()


@router.post("/calc-rules")
async def create_calc_rule(
    body: CalcRuleCreateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """创建计算规则"""
    # Check for duplicate code
    existing = db.query(CalculationRule).filter(
        CalculationRule.code == body.code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calculation rule code already exists"
        )
    
    rule = CalculationRule(
        name=body.name,
        code=body.code,
        description=body.description,
        formula=body.formula,
        input_params=body.input_params or [],
        output_type=body.output_type,
        examples=body.examples or [],
        is_active=body.is_active,
        updated_by=admin.id,
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return {"message": "Calculation rule created", "rule": rule.to_dict()}


@router.put("/calc-rules/{rule_id}")
async def update_calc_rule(
    rule_id: int,
    body: CalcRuleUpdateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """更新计算规则"""
    rule = db.query(CalculationRule).filter(CalculationRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation rule not found"
        )
    
    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    if body.formula is not None:
        rule.formula = body.formula
    if body.input_params is not None:
        rule.input_params = body.input_params
    if body.output_type is not None:
        rule.output_type = body.output_type
    if body.examples is not None:
        rule.examples = body.examples
    if body.is_active is not None:
        rule.is_active = body.is_active
    
    rule.updated_by = admin.id
    db.commit()
    db.refresh(rule)
    
    return {"message": "Calculation rule updated", "rule": rule.to_dict()}


@router.delete("/calc-rules/{rule_id}")
async def delete_calc_rule(
    rule_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除计算规则"""
    rule = db.query(CalculationRule).filter(CalculationRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation rule not found"
        )
    
    db.delete(rule)
    db.commit()
    
    return {"message": "Calculation rule deleted", "id": rule_id}


@router.post("/calc-rules/{rule_id}/test")
async def test_calc_rule(
    rule_id: int,
    body: CalcRuleTestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """测试计算规则"""
    rule = db.query(CalculationRule).filter(CalculationRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation rule not found"
        )
    
    try:
        # Create a namespace with the input values
        namespace = body.inputs.copy()
        
        # Add basic math functions
        import math
        namespace.update({
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'sum': sum,
            'pow': pow,
            'sqrt': math.sqrt,
            'floor': math.floor,
            'ceil': math.ceil,
            'math': math,  # Full math module
        })
        
        # Check if formula is a single expression or multi-statement code
        formula = rule.formula.strip()
        
        # If formula contains assignment or multiple statements, use exec()
        if '\n' in formula or '=' in formula:
            # Multi-statement formula - use exec()
            exec(formula, {"__builtins__": {"round": round, "abs": abs, "min": min, "max": max, "sum": sum, "pow": pow, "int": int, "float": float}}, namespace)
            # Get the result (should be stored in 'result' variable)
            result = namespace.get('result', 'No result variable defined')
        else:
            # Single expression - use eval()
            result = eval(formula, {"__builtins__": {}}, namespace)
        
        return {"success": True, "result": result, "formula": rule.formula, "inputs": body.inputs}
    except Exception as e:
        return {"success": False, "error": str(e), "formula": rule.formula, "inputs": body.inputs}


# ==================== Interaction Flow Models ====================

class InteractionStepOption(BaseModel):
    id: str
    label: str
    icon: Optional[str] = None
    description: Optional[str] = None
    next: Optional[str] = None  # Next step ID for branching


class InteractionStepDependency(BaseModel):
    stepId: str
    values: List[str]


class InteractionStep(BaseModel):
    id: str
    question: str
    type: str  # single/multiple/input
    options: Optional[List[InteractionStepOption]] = None
    inputType: Optional[str] = None  # text/number/date
    placeholder: Optional[str] = None
    validation: Optional[dict] = None
    required: bool = True
    dependsOn: Optional[InteractionStepDependency] = None


class InteractionFlowCreateRequest(BaseModel):
    flow_id: str
    name: str
    description: Optional[str] = None
    trigger_patterns: Optional[List[str]] = []
    scenario_id: Optional[str] = None
    steps: List[InteractionStep]
    on_complete: str = "generate"  # calculate/search/generate
    is_active: bool = True


class InteractionFlowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_patterns: Optional[List[str]] = None
    scenario_id: Optional[str] = None
    steps: Optional[List[InteractionStep]] = None
    on_complete: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== Interaction Flow API ====================

@router.get("/interaction-flows")
async def get_interaction_flows(
    scenario_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取交互流程列表"""
    query = db.query(InteractionFlow)
    
    if scenario_id:
        query = query.filter(InteractionFlow.scenario_id == scenario_id)
    if is_active is not None:
        query = query.filter(InteractionFlow.is_active == is_active)
    
    flows = query.order_by(InteractionFlow.id).all()
    
    return {
        "flows": [flow.to_dict() for flow in flows],
        "total": len(flows)
    }


@router.get("/interaction-flows/{flow_id}")
async def get_interaction_flow(
    flow_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个交互流程"""
    flow = db.query(InteractionFlow).filter(InteractionFlow.flow_id == flow_id).first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction flow not found"
        )
    
    return flow.to_dict()


@router.post("/interaction-flows")
async def create_interaction_flow(
    body: InteractionFlowCreateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """创建交互流程"""
    # Check for duplicate flow_id
    existing = db.query(InteractionFlow).filter(InteractionFlow.flow_id == body.flow_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flow with ID '{body.flow_id}' already exists"
        )
    
    flow = InteractionFlow(
        flow_id=body.flow_id,
        name=body.name,
        description=body.description,
        trigger_patterns=body.trigger_patterns,
        scenario_id=body.scenario_id,
        steps=[step.dict() for step in body.steps],
        on_complete=body.on_complete,
        is_active=body.is_active,
        created_by=admin.id
    )
    
    db.add(flow)
    db.commit()
    db.refresh(flow)
    
    return flow.to_dict()


@router.put("/interaction-flows/{flow_id}")
async def update_interaction_flow(
    flow_id: str,
    body: InteractionFlowUpdateRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """更新交互流程"""
    flow = db.query(InteractionFlow).filter(InteractionFlow.flow_id == flow_id).first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction flow not found"
        )
    
    if body.name is not None:
        flow.name = body.name
    if body.description is not None:
        flow.description = body.description
    if body.trigger_patterns is not None:
        flow.trigger_patterns = body.trigger_patterns
    if body.scenario_id is not None:
        flow.scenario_id = body.scenario_id
    if body.steps is not None:
        flow.steps = [step.dict() for step in body.steps]
    if body.on_complete is not None:
        flow.on_complete = body.on_complete
    if body.is_active is not None:
        flow.is_active = body.is_active
    
    db.commit()
    db.refresh(flow)
    
    return flow.to_dict()


@router.delete("/interaction-flows/{flow_id}")
async def delete_interaction_flow(
    flow_id: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """删除交互流程"""
    flow = db.query(InteractionFlow).filter(InteractionFlow.flow_id == flow_id).first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction flow not found"
        )
    
    db.delete(flow)
    db.commit()
    
    return {"message": f"Flow '{flow_id}' deleted"}


# ==================== Interaction Session API ====================

class StartInteractionRequest(BaseModel):
    flow_id: str


class AnswerInteractionRequest(BaseModel):
    step_id: str
    answer: str | List[str]  # Single value or multiple values for multi-select


@router.post("/interaction-sessions/start")
async def start_interaction(
    conversation_id: str,
    body: StartInteractionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """开始交互流程"""
    import uuid
    
    # Get the flow
    flow = db.query(InteractionFlow).filter(
        InteractionFlow.flow_id == body.flow_id,
        InteractionFlow.is_active == True
    ).first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction flow not found or inactive"
        )
    
    # Check for existing active session
    existing = db.query(InteractionSession).filter(
        InteractionSession.conversation_id == conversation_id,
        InteractionSession.status == 'active'
    ).first()
    
    if existing:
        # Cancel the existing session
        existing.status = 'cancelled'
        db.commit()
    
    # Create new session
    session = InteractionSession(
        session_id=str(uuid.uuid4())[:8],
        conversation_id=conversation_id,
        flow_id=body.flow_id,
        user_id=user.id,
        current_step=0,
        collected_answers={},
        status='active'
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Get first applicable step
    first_step = _get_next_step(flow.steps, {})
    
    return {
        "session": session.to_dict(),
        "flow": {
            "flow_id": flow.flow_id,
            "name": flow.name,
            "total_steps": len([s for s in flow.steps if not s.get('dependsOn')])
        },
        "current_question": first_step
    }


@router.post("/interaction-sessions/{session_id}/answer")
async def answer_interaction(
    session_id: str,
    body: AnswerInteractionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交交互答案，获取下一步"""
    import logging
    logger = logging.getLogger(__name__)
    
    session = db.query(InteractionSession).filter(
        InteractionSession.session_id == session_id,
        InteractionSession.status == 'active'
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active interaction session not found"
        )
    
    # Get the flow
    flow = db.query(InteractionFlow).filter(
        InteractionFlow.flow_id == session.flow_id
    ).first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction flow not found"
        )
    
    logger.info(f"[InteractionAnswer] session_id={session_id}, step_id={body.step_id}, answer={body.answer}")
    logger.info(f"[InteractionAnswer] Before update - collected_answers={session.collected_answers}")
    
    # Update collected answers - use dict copy and flag_modified for JSONB
    answers = dict(session.collected_answers or {})
    answers[body.step_id] = body.answer
    session.collected_answers = answers
    session.current_step += 1
    flag_modified(session, "collected_answers")  # Ensure SQLAlchemy detects JSONB change
    
    logger.info(f"[InteractionAnswer] After update - answers={answers}, keys={list(answers.keys())}")
    logger.info(f"[InteractionAnswer] Flow steps: {[s.get('id') for s in (flow.steps or [])]}")
    
    # Flush to ensure session is updated before any further operations
    db.flush()
    
    # Get next step based on conditions
    next_step = _get_next_step(flow.steps, answers)
    logger.info(f"[InteractionAnswer] next_step={next_step.get('id') if next_step else 'None (completed)'}")
    
    if next_step is None:
        # All questions answered - complete the session
        session.status = 'completed'
        db.commit()
        
        # Generate human-readable labeled answers
        labeled_answers = _format_answers_with_labels(flow.steps, answers)
        
        return {
            "session": session.to_dict(),
            "completed": True,
            "collected_answers": answers,
            "labeled_answers": labeled_answers,  # Human-readable version
            "on_complete": flow.on_complete
        }
    
    db.commit()
    
    # Count remaining steps
    answered_count = len(answers)
    total_applicable = _count_applicable_steps(flow.steps, answers)
    
    return {
        "session": session.to_dict(),
        "completed": False,
        "current_question": next_step,
        "progress": {
            "answered": answered_count,
            "total": total_applicable
        }
    }


@router.post("/interaction-sessions/{session_id}/cancel")
async def cancel_interaction(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消交互流程"""
    session = db.query(InteractionSession).filter(
        InteractionSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction session not found"
        )
    
    session.status = 'cancelled'
    db.commit()
    
    return {"message": "Session cancelled", "session": session.to_dict()}


@router.get("/interaction-sessions/{conversation_id}/active")
async def get_active_session(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话的活跃交互会话"""
    session = db.query(InteractionSession).filter(
        InteractionSession.conversation_id == conversation_id,
        InteractionSession.status == 'active'
    ).first()
    
    if not session:
        return {"session": None}
    
    # Get the flow
    flow = db.query(InteractionFlow).filter(
        InteractionFlow.flow_id == session.flow_id
    ).first()
    
    if not flow:
        return {"session": None}
    
    # Get current question
    next_step = _get_next_step(flow.steps, session.collected_answers or {})
    
    return {
        "session": session.to_dict(),
        "flow": {
            "flow_id": flow.flow_id,
            "name": flow.name
        },
        "current_question": next_step
    }


# ==================== Helper Functions ====================

def _get_next_step(steps: List[dict], answers: dict) -> Optional[dict]:
    """Get the next applicable step based on current answers"""
    for step in steps:
        step_id = step.get('id')
        
        # Skip already answered steps
        if step_id in answers:
            continue
        
        # Check dependency condition
        depends_on = step.get('dependsOn')
        if depends_on:
            dep_step_id = depends_on.get('stepId')
            dep_values = depends_on.get('values', [])
            
            # Get the answer for the dependent step
            dep_answer = answers.get(dep_step_id)
            
            if dep_answer is None:
                # Dependency not answered yet, skip this step for now
                continue
            
            # Check if the answer matches any of the required values
            if isinstance(dep_answer, list):
                # Multiple select - check if any value matches
                if not any(v in dep_values for v in dep_answer):
                    continue
            else:
                # Single select - check if value matches
                if dep_answer not in dep_values:
                    continue
        
        # This step is applicable
        return step
    
    return None


def _count_applicable_steps(steps: List[dict], answers: dict) -> int:
    """Count the total number of steps that would be applicable given current answers"""
    count = 0
    simulated_answers = answers.copy()
    
    for step in steps:
        step_id = step.get('id')
        
        # Check dependency condition
        depends_on = step.get('dependsOn')
        if depends_on:
            dep_step_id = depends_on.get('stepId')
            dep_values = depends_on.get('values', [])
            
            dep_answer = simulated_answers.get(dep_step_id)
            
            if dep_answer is None:
                continue
            
            if isinstance(dep_answer, list):
                if not any(v in dep_values for v in dep_answer):
                    continue
            else:
                if dep_answer not in dep_values:
                    continue
        
        count += 1
    
    return count


def _format_answers_with_labels(steps: List[dict], answers: dict) -> dict:
    """Convert raw answer IDs to human-readable labels"""
    labeled = {}
    
    # Build a lookup map: step_id -> {question, options_map}
    step_map = {}
    for step in steps:
        step_id = step.get('id')
        question = step.get('question', step_id)
        options = step.get('options', [])
        
        # Build option_id -> label map
        option_map = {}
        for opt in options:
            opt_id = opt.get('id') if isinstance(opt, dict) else opt
            opt_label = opt.get('label', opt_id) if isinstance(opt, dict) else opt
            option_map[opt_id] = opt_label
        
        step_map[step_id] = {
            'question': question,
            'options': option_map
        }
    
    # Convert answers
    for step_id, answer in answers.items():
        step_info = step_map.get(step_id)
        if not step_info:
            # Unknown step, use raw values
            labeled[step_id] = answer
            continue
        
        question = step_info['question']
        option_map = step_info['options']
        
        if isinstance(answer, list):
            # Multiple select - convert each option ID to label
            labeled_values = [option_map.get(v, v) for v in answer]
            labeled[question] = labeled_values
        else:
            # Single select or input - convert if in option_map
            labeled[question] = option_map.get(answer, answer)
    
    return labeled

