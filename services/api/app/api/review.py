"""Review management API endpoints"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db
from ..models.user import User
from ..models.contribution import Contribution, ContributionStats
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/review", tags=["review"])


# ==================== Request/Response Models ====================

class ReviewDecisionRequest(BaseModel):
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str


class RequestInfoRequest(BaseModel):
    questions: str


class BatchReviewRequest(BaseModel):
    contribution_ids: List[int]
    action: str  # approve/reject
    comment: Optional[str] = None


class ContributionReviewResponse(BaseModel):
    id: int
    contributor_id: int
    contributor_name: Optional[str]
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
    trigger_type: Optional[str]
    conversation_id: Optional[str]
    query_text: Optional[str]
    status: str
    review_comment: Optional[str]
    reviewed_at: Optional[str]
    created_at: Optional[str]


# ==================== API Endpoints ====================

@router.get("/queue")
async def get_review_queue(
    status_filter: str = "pending",
    contribution_type: Optional[str] = None,
    ku_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取待审核队列"""
    from ..models.user import User as UserModel
    
    query = db.query(Contribution, UserModel.username, UserModel.display_name).join(
        UserModel, Contribution.contributor_id == UserModel.id
    )
    
    if status_filter:
        query = query.filter(Contribution.status == status_filter)
    
    if contribution_type:
        query = query.filter(Contribution.contribution_type == contribution_type)
    
    if ku_type:
        query = query.filter(Contribution.ku_type_code == ku_type)
    
    total = query.count()
    results = query.order_by(
        desc(Contribution.created_at)
    ).offset(offset).limit(limit).all()
    
    contributions = []
    for contrib, username, display_name in results:
        data = contrib.to_dict()
        data["contributor_name"] = display_name or username
        contributions.append(data)
    
    return {
        "total": total,
        "contributions": contributions
    }


@router.get("/{contribution_id}")
async def get_review_detail(
    contribution_id: int,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取审核详情"""
    from ..models.user import User as UserModel
    
    result = db.query(Contribution, UserModel.username, UserModel.display_name).join(
        UserModel, Contribution.contributor_id == UserModel.id
    ).filter(
        Contribution.id == contribution_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    contrib, username, display_name = result
    data = contrib.to_dict()
    data["contributor_name"] = display_name or username
    
    # Include content_json for draft KUs
    if contrib.content_json:
        data["content_json"] = contrib.content_json
    
    return data


@router.post("/{contribution_id}/approve")
async def approve_contribution(
    contribution_id: int,
    body: ReviewDecisionRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """批准贡献"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    if contribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution is already {contribution.status}"
        )
    
    # Update contribution status
    contribution.status = "approved"
    contribution.reviewer_id = admin.id
    contribution.review_comment = body.comment
    contribution.reviewed_at = datetime.now(timezone.utc)
    
    # Update contributor stats
    _update_stats_on_review(db, contribution.contributor_id, approved=True)
    
    db.commit()
    
    return {
        "message": "Contribution approved",
        "contribution_id": contribution_id
    }


@router.post("/{contribution_id}/reject")
async def reject_contribution(
    contribution_id: int,
    body: RejectRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """拒绝贡献"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    if contribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution is already {contribution.status}"
        )
    
    # Update contribution status
    contribution.status = "rejected"
    contribution.reviewer_id = admin.id
    contribution.review_comment = body.reason
    contribution.reviewed_at = datetime.now(timezone.utc)
    
    # Update contributor stats
    _update_stats_on_review(db, contribution.contributor_id, rejected=True)
    
    db.commit()
    
    return {
        "message": "Contribution rejected",
        "contribution_id": contribution_id
    }


@router.post("/{contribution_id}/request-info")
async def request_more_info(
    contribution_id: int,
    body: RequestInfoRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """请求补充信息"""
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()
    
    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found"
        )
    
    if contribution.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution is already {contribution.status}"
        )
    
    # Update contribution with info request
    contribution.status = "needs_info"
    contribution.reviewer_id = admin.id
    contribution.review_comment = f"需要补充信息: {body.questions}"
    contribution.reviewed_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {
        "message": "Information requested",
        "contribution_id": contribution_id
    }


@router.post("/batch")
async def batch_review(
    body: BatchReviewRequest,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """批量审核"""
    if body.action not in ["approve", "reject"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approve' or 'reject'"
        )
    
    contributions = db.query(Contribution).filter(
        Contribution.id.in_(body.contribution_ids),
        Contribution.status == "pending"
    ).all()
    
    if not contributions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending contributions found"
        )
    
    processed = 0
    for contribution in contributions:
        if body.action == "approve":
            contribution.status = "approved"
            _update_stats_on_review(db, contribution.contributor_id, approved=True)
        else:
            contribution.status = "rejected"
            _update_stats_on_review(db, contribution.contributor_id, rejected=True)
        
        contribution.reviewer_id = admin.id
        contribution.review_comment = body.comment
        contribution.reviewed_at = datetime.now(timezone.utc)
        processed += 1
    
    db.commit()
    
    return {
        "message": f"Batch review completed",
        "processed": processed,
        "action": body.action
    }


# ==================== Stats Endpoints ====================

@router.get("/stats/summary")
async def get_review_stats(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取审核统计概览"""
    from sqlalchemy import func
    
    # Count by status
    status_counts = db.query(
        Contribution.status,
        func.count(Contribution.id)
    ).group_by(Contribution.status).all()
    
    stats = {s: 0 for s in ["pending", "approved", "rejected", "needs_info"]}
    for status_val, count in status_counts:
        if status_val in stats:
            stats[status_val] = count
    
    # Count by type
    type_counts = db.query(
        Contribution.contribution_type,
        func.count(Contribution.id)
    ).filter(
        Contribution.status == "pending"
    ).group_by(Contribution.contribution_type).all()
    
    pending_by_type = {t: c for t, c in type_counts}
    
    return {
        "total_pending": stats["pending"],
        "total_approved": stats["approved"],
        "total_rejected": stats["rejected"],
        "needs_info": stats["needs_info"],
        "pending_by_type": pending_by_type
    }


# ==================== Helper Functions ====================

def _update_stats_on_review(
    db: Session,
    contributor_id: int,
    approved: bool = False,
    rejected: bool = False
):
    """Update contributor stats after review"""
    stats = db.query(ContributionStats).filter(
        ContributionStats.user_id == contributor_id
    ).first()
    
    if not stats:
        return
    
    if approved:
        stats.approved_count += 1
        stats.pending_count = max(0, stats.pending_count - 1)
    
    if rejected:
        stats.rejected_count += 1
        stats.pending_count = max(0, stats.pending_count - 1)
    
    stats.updated_at = datetime.now(timezone.utc)

