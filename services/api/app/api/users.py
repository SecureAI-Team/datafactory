"""User management API endpoints"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db
from ..models.user import User
from ..models.contribution import ContributionStats
from ..services.auth_service import AuthService
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/users", tags=["users"])


# ==================== Request/Response Models ====================

class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    role: str = "user"
    department: Optional[str] = None


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    department: Optional[str]
    is_active: bool
    last_login_at: Optional[str]
    created_at: Optional[str]


class UserStatsResponse(BaseModel):
    total_contributions: int
    approved_count: int
    rejected_count: int
    pending_count: int
    citation_count: int
    achievements: List
    streak_days: int


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


# ==================== API Endpoints ====================

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取用户列表（管理员）"""
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_pattern)) |
            (User.email.ilike(search_pattern)) |
            (User.display_name.ilike(search_pattern))
        )
    
    total = query.count()
    users = query.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return UserListResponse(
        users=[UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            role=u.role,
            department=u.department,
            is_active=u.is_active,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            created_at=u.created_at.isoformat() if u.created_at else None
        ) for u in users],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """创建用户（管理员）"""
    auth_service = AuthService(db)
    
    # Check if username exists
    if auth_service.get_user_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email exists
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    user = auth_service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        role=body.role,
        department=body.department
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,
        department=user.department,
        is_active=user.is_active,
        last_login_at=None,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户详情"""
    # 用户只能查看自己的详情，管理员可以查看所有人
    if current_user.id != user_id and current_user.role not in ("admin", "data_ops"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,
        department=user.department,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户"""
    # 用户只能更新自己的部分信息，管理员可以更新所有
    is_self = current_user.id == user_id
    is_admin = current_user.role == "admin"
    
    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 普通用户只能更新显示名称
    if body.display_name is not None:
        user.display_name = body.display_name
    
    # 管理员可以更新更多字段
    if is_admin:
        if body.email is not None:
            # Check email uniqueness
            existing = db.query(User).filter(User.email == body.email, User.id != user_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            user.email = body.email
        if body.role is not None:
            user.role = body.role
        if body.department is not None:
            user.department = body.department
        if body.is_active is not None:
            user.is_active = body.is_active
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,
        department=user.department,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """禁用用户（管理员）"""
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    db.commit()
    
    return {"message": "User disabled"}


@router.get("/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户统计（贡献、使用）"""
    # 用户可以查看自己的统计，管理员可以查看所有人
    if current_user.id != user_id and current_user.role not in ("admin", "data_ops"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's stats"
        )
    
    stats = db.query(ContributionStats).filter(ContributionStats.user_id == user_id).first()
    
    if not stats:
        # 返回默认统计
        return UserStatsResponse(
            total_contributions=0,
            approved_count=0,
            rejected_count=0,
            pending_count=0,
            citation_count=0,
            achievements=[],
            streak_days=0
        )
    
    return UserStatsResponse(
        total_contributions=stats.total_contributions or 0,
        approved_count=stats.approved_count or 0,
        rejected_count=stats.rejected_count or 0,
        pending_count=stats.pending_count or 0,
        citation_count=stats.citation_count or 0,
        achievements=stats.achievements or [],
        streak_days=stats.streak_days or 0
    )

