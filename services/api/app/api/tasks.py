"""Task collaboration API endpoints"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from ..db import get_db
from ..models.user import User
from ..models.task import CollaborationTask
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ==================== Request/Response Models ====================

class CreateTaskRequest(BaseModel):
    task_type: str  # request_info/verify_content/approve_term/review_ku
    title: str
    description: Optional[str] = None
    related_type: Optional[str] = None  # ku/contribution/term/prompt
    related_id: Optional[int] = None
    assignee_id: Optional[int] = None
    priority: str = "normal"  # low/normal/high/urgent
    due_date: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None


class ResolveTaskRequest(BaseModel):
    resolution: str


class TaskResponse(BaseModel):
    id: int
    task_type: str
    title: str
    description: Optional[str]
    related_type: Optional[str]
    related_id: Optional[int]
    assignee_id: Optional[int]
    assignee_name: Optional[str] = None
    requester_id: Optional[int]
    requester_name: Optional[str] = None
    status: str
    priority: str
    resolution: Optional[str]
    resolved_at: Optional[str]
    due_date: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# ==================== API Endpoints ====================

@router.get("")
async def list_tasks(
    status_filter: Optional[str] = None,
    task_type: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    query = db.query(CollaborationTask)
    
    if status_filter:
        query = query.filter(CollaborationTask.status == status_filter)
    
    if task_type:
        query = query.filter(CollaborationTask.task_type == task_type)
    
    if priority:
        query = query.filter(CollaborationTask.priority == priority)
    
    if assignee_id:
        query = query.filter(CollaborationTask.assignee_id == assignee_id)
    
    total = query.count()
    tasks = query.order_by(
        desc(CollaborationTask.created_at)
    ).offset(offset).limit(limit).all()
    
    # Enrich with user names
    result = []
    for task in tasks:
        data = task.to_dict()
        # Get assignee and requester names
        if task.assignee_id:
            assignee = db.query(User).filter(User.id == task.assignee_id).first()
            data["assignee_name"] = assignee.display_name or assignee.username if assignee else None
        if task.requester_id:
            requester = db.query(User).filter(User.id == task.requester_id).first()
            data["requester_name"] = requester.display_name or requester.username if requester else None
        result.append(data)
    
    return {
        "total": total,
        "tasks": result
    }


@router.get("/mine")
async def get_my_tasks(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的任务（分配给我的或我创建的）"""
    query = db.query(CollaborationTask).filter(
        or_(
            CollaborationTask.assignee_id == user.id,
            CollaborationTask.requester_id == user.id
        )
    )
    
    if status_filter:
        query = query.filter(CollaborationTask.status == status_filter)
    
    total = query.count()
    tasks = query.order_by(
        desc(CollaborationTask.created_at)
    ).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "tasks": [t.to_dict() for t in tasks]
    }


@router.post("", response_model=TaskResponse)
async def create_task(
    body: CreateTaskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建任务"""
    # Validate task type
    valid_types = ["request_info", "verify_content", "approve_term", "review_ku"]
    if body.task_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task_type. Must be one of: {valid_types}"
        )
    
    # Validate priority
    valid_priorities = ["low", "normal", "high", "urgent"]
    if body.priority not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Must be one of: {valid_priorities}"
        )
    
    # Parse due_date
    due = None
    if body.due_date:
        try:
            due = datetime.fromisoformat(body.due_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid due_date format. Use ISO format."
            )
    
    task = CollaborationTask(
        task_type=body.task_type,
        title=body.title,
        description=body.description,
        related_type=body.related_type,
        related_id=body.related_id,
        assignee_id=body.assignee_id,
        requester_id=user.id,
        priority=body.priority,
        due_date=due,
        status="open"
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return TaskResponse(**task.to_dict())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取任务详情"""
    task = db.query(CollaborationTask).filter(
        CollaborationTask.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    data = task.to_dict()
    
    # Get user names
    if task.assignee_id:
        assignee = db.query(User).filter(User.id == task.assignee_id).first()
        data["assignee_name"] = assignee.display_name or assignee.username if assignee else None
    if task.requester_id:
        requester = db.query(User).filter(User.id == task.requester_id).first()
        data["requester_name"] = requester.display_name or requester.username if requester else None
    
    return TaskResponse(**data)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: UpdateTaskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新任务"""
    task = db.query(CollaborationTask).filter(
        CollaborationTask.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Only requester, assignee, or admin can update
    if task.requester_id != user.id and task.assignee_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this task"
        )
    
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.assignee_id is not None:
        task.assignee_id = body.assignee_id
    if body.priority is not None:
        valid_priorities = ["low", "normal", "high", "urgent"]
        if body.priority not in valid_priorities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid priority. Must be one of: {valid_priorities}"
            )
        task.priority = body.priority
    if body.status is not None:
        valid_statuses = ["open", "in_progress", "resolved", "cancelled"]
        if body.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        task.status = body.status
    if body.due_date is not None:
        try:
            task.due_date = datetime.fromisoformat(body.due_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid due_date format. Use ISO format."
            )
    
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    
    return TaskResponse(**task.to_dict())


@router.post("/{task_id}/resolve", response_model=TaskResponse)
async def resolve_task(
    task_id: int,
    body: ResolveTaskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """完成任务"""
    task = db.query(CollaborationTask).filter(
        CollaborationTask.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if task.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already resolved"
        )
    
    # Only assignee or admin can resolve
    if task.assignee_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assignee can resolve this task"
        )
    
    task.status = "resolved"
    task.resolution = body.resolution
    task.resolved_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(task)
    
    return TaskResponse(**task.to_dict())


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消任务"""
    task = db.query(CollaborationTask).filter(
        CollaborationTask.id == task_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if task.status in ["resolved", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is already {task.status}"
        )
    
    # Only requester or admin can cancel
    if task.requester_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requester can cancel this task"
        )
    
    task.status = "cancelled"
    task.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": "Task cancelled", "task_id": task_id}


# ==================== Stats ====================

@router.get("/stats/summary")
async def get_task_stats(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取任务统计"""
    from sqlalchemy import func
    
    # Count by status
    status_counts = db.query(
        CollaborationTask.status,
        func.count(CollaborationTask.id)
    ).group_by(CollaborationTask.status).all()
    
    by_status = {s: c for s, c in status_counts}
    
    # Count by type
    type_counts = db.query(
        CollaborationTask.task_type,
        func.count(CollaborationTask.id)
    ).filter(
        CollaborationTask.status.in_(["open", "in_progress"])
    ).group_by(CollaborationTask.task_type).all()
    
    by_type = {t: c for t, c in type_counts}
    
    # Overdue tasks
    now = datetime.now(timezone.utc)
    overdue = db.query(func.count(CollaborationTask.id)).filter(
        CollaborationTask.status.in_(["open", "in_progress"]),
        CollaborationTask.due_date < now
    ).scalar() or 0
    
    return {
        "by_status": by_status,
        "by_type": by_type,
        "overdue": overdue,
        "total_open": by_status.get("open", 0) + by_status.get("in_progress", 0)
    }

