"""Contribution management API endpoints"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..db import get_db
from ..models.user import User
from ..models.contribution import Contribution, ContributionStats, CitationRecord
from ..clients.minio_client import get_client as get_minio_client
from .auth import get_current_user

router = APIRouter(prefix="/api/contribute", tags=["contribute"])


# ==================== Request/Response Models ====================

class DraftKURequest(BaseModel):
    title: str
    description: Optional[str] = None
    content_json: Optional[dict] = None
    ku_type_code: str
    product_id: Optional[str] = None
    tags: Optional[List[str]] = []
    visibility: str = "internal"
    expiry_date: Optional[str] = None
    conversation_id: Optional[str] = None
    query_text: Optional[str] = None
    trigger_type: Optional[str] = None


class SignalRequest(BaseModel):
    title: str
    description: str
    content_json: dict
    product_id: Optional[str] = None
    tags: Optional[List[str]] = []
    conversation_id: Optional[str] = None
    query_text: Optional[str] = None


class UpdateContributionRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content_json: Optional[dict] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None


class SupplementInfoRequest(BaseModel):
    """Request to supplement a contribution that needs more info"""
    additional_info: str  # Text response to reviewer's questions
    content_json: Optional[dict] = None  # Optional: additional structured content
    file_path: Optional[str] = None  # Optional: path to newly uploaded file


class ContributionResponse(BaseModel):
    id: int
    contributor_id: int
    contribution_type: str
    title: Optional[str]
    description: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    ku_type_code: Optional[str]
    product_id: Optional[str]
    tags: List
    visibility: str
    expiry_date: Optional[str]
    trigger_type: Optional[str]
    conversation_id: Optional[str]
    status: str
    processed_ku_id: Optional[int]
    reviewer_id: Optional[int]
    review_comment: Optional[str]
    reviewed_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class ContributionStatsResponse(BaseModel):
    total_contributions: int
    approved_count: int
    rejected_count: int
    pending_count: int
    citation_count: int
    achievements: List
    streak_days: int


class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    display_name: Optional[str]
    total_contributions: int
    approved_count: int
    citation_count: int


# ==================== API Endpoints ====================

@router.post("/upload", response_model=ContributionResponse)
async def upload_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    ku_type_code: str = Form(...),
    product_id: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    visibility: str = Form("internal"),
    conversation_id: Optional[str] = Form(None),
    query_text: Optional[str] = Form(None),
    trigger_type: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传文件贡献"""
    import json
    
    # Parse tags
    try:
        parsed_tags = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        parsed_tags = []
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"contributions/{user.id}/{uuid.uuid4()}{file_ext}"
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Upload to MinIO
    try:
        minio_client = get_minio_client()
        from io import BytesIO
        minio_client.put_object(
            "uploads",
            unique_filename,
            BytesIO(file_content),
            file_size,
            content_type=file.content_type or "application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    
    # Create contribution record
    contribution = Contribution(
        contributor_id=user.id,
        contribution_type="file_upload",
        title=title or file.filename,
        description=description,
        file_name=file.filename,
        file_path=unique_filename,
        file_size=file_size,
        mime_type=file.content_type,
        ku_type_code=ku_type_code,
        product_id=product_id,
        tags=parsed_tags,
        visibility=visibility,
        trigger_type=trigger_type,
        conversation_id=conversation_id,
        query_text=query_text,
        status="pending"
    )
    
    db.add(contribution)
    
    # Update user stats
    _update_contribution_stats(db, user.id, increment_pending=True)
    
    db.commit()
    db.refresh(contribution)
    
    return ContributionResponse(**contribution.to_dict())


@router.post("/draft", response_model=ContributionResponse)
async def save_draft(
    body: DraftKURequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """保存草稿 KU"""
    from datetime import date
    
    expiry = None
    if body.expiry_date:
        try:
            expiry = date.fromisoformat(body.expiry_date)
        except ValueError:
            pass
    
    contribution = Contribution(
        contributor_id=user.id,
        contribution_type="draft_ku",
        title=body.title,
        description=body.description,
        content_json=body.content_json,
        ku_type_code=body.ku_type_code,
        product_id=body.product_id,
        tags=body.tags or [],
        visibility=body.visibility,
        expiry_date=expiry,
        trigger_type=body.trigger_type,
        conversation_id=body.conversation_id,
        query_text=body.query_text,
        status="pending"
    )
    
    db.add(contribution)
    _update_contribution_stats(db, user.id, increment_pending=True)
    db.commit()
    db.refresh(contribution)
    
    return ContributionResponse(**contribution.to_dict())


@router.post("/signal", response_model=ContributionResponse)
async def save_signal(
    body: SignalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """保存对话信号（高价值信息）"""
    contribution = Contribution(
        contributor_id=user.id,
        contribution_type="signal",
        title=body.title,
        description=body.description,
        content_json=body.content_json,
        ku_type_code="field.signal",
        product_id=body.product_id,
        tags=body.tags or [],
        visibility="internal",
        trigger_type="high_value_signal",
        conversation_id=body.conversation_id,
        query_text=body.query_text,
        status="pending"
    )
    
    db.add(contribution)
    _update_contribution_stats(db, user.id, increment_pending=True)
    db.commit()
    db.refresh(contribution)
    
    return ContributionResponse(**contribution.to_dict())


@router.get("/mine")
async def get_my_contributions(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的贡献列表"""
    query = db.query(Contribution).filter(
        Contribution.contributor_id == user.id
    )
    
    if status_filter:
        query = query.filter(Contribution.status == status_filter)
    
    total = query.count()
    contributions = query.order_by(
        desc(Contribution.created_at)
    ).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "contributions": [c.to_dict() for c in contributions]
    }


@router.get("/stats", response_model=ContributionStatsResponse)
async def get_my_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的贡献统计"""
    stats = db.query(ContributionStats).filter(
        ContributionStats.user_id == user.id
    ).first()
    
    if not stats:
        # Create empty stats
        return ContributionStatsResponse(
            total_contributions=0,
            approved_count=0,
            rejected_count=0,
            pending_count=0,
            citation_count=0,
            achievements=[],
            streak_days=0
        )
    
    return ContributionStatsResponse(**stats.to_dict())


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取贡献排行榜"""
    from ..models.user import User as UserModel
    
    # Join stats with users
    results = db.query(
        ContributionStats,
        UserModel.username,
        UserModel.display_name
    ).join(
        UserModel, ContributionStats.user_id == UserModel.id
    ).order_by(
        desc(ContributionStats.approved_count),
        desc(ContributionStats.citation_count)
    ).limit(limit).all()
    
    leaderboard = []
    for stats, username, display_name in results:
        leaderboard.append({
            "user_id": stats.user_id,
            "username": username,
            "display_name": display_name,
            "total_contributions": stats.total_contributions,
            "approved_count": stats.approved_count,
            "citation_count": stats.citation_count
        })
    
    return {"leaderboard": leaderboard}


@router.get("/{contribution_id}", response_model=ContributionResponse)
async def get_contribution(
    contribution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取贡献详情"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    # Only contributor or admin can view
    if contribution.contributor_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this contribution"
        )
    
    return ContributionResponse(**contribution.to_dict())


@router.put("/{contribution_id}", response_model=ContributionResponse)
async def update_contribution(
    contribution_id: int,
    body: UpdateContributionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新贡献"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id,
        Contribution.contributor_id == user.id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    # Can only update pending contributions
    if contribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update pending contributions"
        )
    
    if body.title is not None:
        contribution.title = body.title
    if body.description is not None:
        contribution.description = body.description
    if body.content_json is not None:
        contribution.content_json = body.content_json
    if body.tags is not None:
        contribution.tags = body.tags
    if body.visibility is not None:
        contribution.visibility = body.visibility
    
    contribution.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contribution)
    
    return ContributionResponse(**contribution.to_dict())


@router.delete("/{contribution_id}")
async def delete_contribution(
    contribution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """撤回贡献"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id,
        Contribution.contributor_id == user.id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    # Can only delete pending contributions
    if contribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete pending contributions"
        )
    
    # Update stats
    _update_contribution_stats(db, user.id, decrement_pending=True)
    
    db.delete(contribution)
    db.commit()
    
    return {"message": "Contribution deleted"}


@router.put("/{contribution_id}/supplement", response_model=ContributionResponse)
async def supplement_contribution(
    contribution_id: int,
    body: SupplementInfoRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    补充贡献信息 - 响应审核员的补充请求
    
    只能对 status='needs_info' 的贡献进行补充
    补充后状态变为 'pending'，重新进入审核队列
    """
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id,
        Contribution.contributor_id == user.id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    # Can only supplement contributions that need info
    if contribution.status != "needs_info":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只能补充状态为'需补充信息'的贡献，当前状态: {contribution.status}"
        )
    
    # Update the contribution with supplementary info
    # Append the additional info to the existing description
    original_review_comment = contribution.review_comment or ""
    supplement_note = f"\n\n--- 补充信息 ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}) ---\n{body.additional_info}"
    
    if contribution.description:
        contribution.description = contribution.description + supplement_note
    else:
        contribution.description = body.additional_info
    
    # Update content_json if provided
    if body.content_json:
        if contribution.content_json:
            # Merge with existing content
            contribution.content_json = {
                **contribution.content_json,
                "supplementary": body.content_json
            }
        else:
            contribution.content_json = body.content_json
    
    # Update file path if a new file was uploaded
    if body.file_path:
        contribution.file_path = body.file_path
    
    # Reset status to pending for re-review
    contribution.status = "pending"
    contribution.review_comment = f"{original_review_comment}\n\n[用户已补充信息]"
    contribution.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(contribution)
    
    return ContributionResponse(**contribution.to_dict())


# ==================== Helper Functions ====================

def _update_contribution_stats(
    db: Session,
    user_id: int,
    increment_pending: bool = False,
    decrement_pending: bool = False,
    increment_approved: bool = False,
    increment_rejected: bool = False
):
    """Update user contribution statistics"""
    stats = db.query(ContributionStats).filter(
        ContributionStats.user_id == user_id
    ).first()
    
    if not stats:
        stats = ContributionStats(
            user_id=user_id,
            total_contributions=0,
            approved_count=0,
            rejected_count=0,
            pending_count=0,
            citation_count=0,
            achievements=[],
            streak_days=0
        )
        db.add(stats)
    
    if increment_pending:
        stats.total_contributions += 1
        stats.pending_count += 1
        stats.last_contribution_at = datetime.now(timezone.utc)
    
    if decrement_pending:
        stats.total_contributions = max(0, stats.total_contributions - 1)
        stats.pending_count = max(0, stats.pending_count - 1)
    
    if increment_approved:
        stats.approved_count += 1
        stats.pending_count = max(0, stats.pending_count - 1)
    
    if increment_rejected:
        stats.rejected_count += 1
        stats.pending_count = max(0, stats.pending_count - 1)
    
    stats.updated_at = datetime.now(timezone.utc)

