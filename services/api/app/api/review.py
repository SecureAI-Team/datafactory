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
    """批准贡献并创建知识单元"""
    from ..models.legacy import KnowledgeUnit, SourceDocument
    from ..models.user import User as UserModel
    
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
    
    # Get contributor info for created_by field
    contributor = db.query(UserModel).filter(
        UserModel.id == contribution.contributor_id
    ).first()
    contributor_name = contributor.display_name or contributor.username if contributor else "unknown"
    
    # Create KnowledgeUnit based on contribution type
    ku = None
    source_doc = None
    
    if contribution.contribution_type == "file_upload":
        # Create SourceDocument for file uploads
        source_doc = SourceDocument(
            filename=contribution.file_name or "unknown",
            uploader=contributor_name,
            mime=contribution.mime_type,
            size=contribution.file_size,
            minio_uri=f"uploads/{contribution.file_path}" if contribution.file_path else None,
            status="processed"
        )
        db.add(source_doc)
        db.flush()  # Get the source_doc.id
        
        # Create KU from file upload
        ku = KnowledgeUnit(
            title=contribution.title or contribution.file_name or "Untitled",
            summary=contribution.description or f"从文件 {contribution.file_name} 导入",
            body_markdown=contribution.description or "",
            status="published",
            ku_type=_map_ku_type_code(contribution.ku_type_code),
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id,
                "source_document_id": source_doc.id,
                "file_name": contribution.file_name
            }],
            created_by=contributor_name
        )
        
    elif contribution.contribution_type == "draft_ku":
        # Create KU directly from draft content
        content = contribution.content_json or {}
        ku = KnowledgeUnit(
            title=contribution.title or content.get("title", "Untitled"),
            summary=content.get("summary", contribution.description or ""),
            body_markdown=content.get("body", content.get("content", contribution.description or "")),
            sections_json=content.get("sections"),
            status="published",
            ku_type=_map_ku_type_code(contribution.ku_type_code),
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            industry_tags=content.get("industry_tags", []),
            use_case_tags=content.get("use_case_tags", []),
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id,
                "draft_content": True
            }],
            created_by=contributor_name
        )
        
    elif contribution.contribution_type == "signal":
        # Create KU from signal (field intelligence)
        content = contribution.content_json or {}
        ku = KnowledgeUnit(
            title=contribution.title or "现场信号",
            summary=contribution.description or "",
            body_markdown=content.get("body", contribution.description or ""),
            status="published",
            ku_type="case",  # Signals are typically case-related
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id,
                "signal_type": "high_value_signal",
                "conversation_id": contribution.conversation_id
            }],
            created_by=contributor_name
        )
    
    if ku:
        db.add(ku)
        db.flush()  # Get the ku.id
        contribution.processed_ku_id = ku.id
    
    # Update contribution status
    contribution.status = "approved"
    contribution.reviewer_id = admin.id
    contribution.review_comment = body.comment
    contribution.reviewed_at = datetime.now(timezone.utc)
    
    # Update contributor stats
    _update_stats_on_review(db, contribution.contributor_id, approved=True)
    
    db.commit()
    
    return {
        "message": "Contribution approved and KU created",
        "contribution_id": contribution_id,
        "ku_id": ku.id if ku else None,
        "source_document_id": source_doc.id if source_doc else None
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
    from ..models.legacy import KnowledgeUnit, SourceDocument
    from ..models.user import User as UserModel
    
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
    kus_created = 0
    
    for contribution in contributions:
        if body.action == "approve":
            contribution.status = "approved"
            _update_stats_on_review(db, contribution.contributor_id, approved=True)
            
            # Create KU for approved contributions
            ku = _create_ku_from_contribution(db, contribution)
            if ku:
                contribution.processed_ku_id = ku.id
                kus_created += 1
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
        "kus_created": kus_created,
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

def _create_ku_from_contribution(db: Session, contribution: Contribution):
    """Create a KnowledgeUnit from an approved contribution"""
    from ..models.legacy import KnowledgeUnit, SourceDocument
    from ..models.user import User as UserModel
    
    # Get contributor info
    contributor = db.query(UserModel).filter(
        UserModel.id == contribution.contributor_id
    ).first()
    contributor_name = contributor.display_name or contributor.username if contributor else "unknown"
    
    ku = None
    
    if contribution.contribution_type == "file_upload":
        # Create SourceDocument for file uploads
        source_doc = SourceDocument(
            filename=contribution.file_name or "unknown",
            uploader=contributor_name,
            mime=contribution.mime_type,
            size=contribution.file_size,
            minio_uri=f"uploads/{contribution.file_path}" if contribution.file_path else None,
            status="processed"
        )
        db.add(source_doc)
        db.flush()
        
        ku = KnowledgeUnit(
            title=contribution.title or contribution.file_name or "Untitled",
            summary=contribution.description or f"从文件 {contribution.file_name} 导入",
            body_markdown=contribution.description or "",
            status="published",
            ku_type=_map_ku_type_code(contribution.ku_type_code),
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id,
                "source_document_id": source_doc.id
            }],
            created_by=contributor_name
        )
        
    elif contribution.contribution_type == "draft_ku":
        content = contribution.content_json or {}
        ku = KnowledgeUnit(
            title=contribution.title or content.get("title", "Untitled"),
            summary=content.get("summary", contribution.description or ""),
            body_markdown=content.get("body", content.get("content", contribution.description or "")),
            sections_json=content.get("sections"),
            status="published",
            ku_type=_map_ku_type_code(contribution.ku_type_code),
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id
            }],
            created_by=contributor_name
        )
        
    elif contribution.contribution_type == "signal":
        content = contribution.content_json or {}
        ku = KnowledgeUnit(
            title=contribution.title or "现场信号",
            summary=contribution.description or "",
            body_markdown=content.get("body", contribution.description or ""),
            status="published",
            ku_type="case",
            product_id=contribution.product_id,
            tags_json=contribution.tags or [],
            source_refs_json=[{
                "type": "contribution",
                "contribution_id": contribution.id,
                "signal_type": "high_value_signal"
            }],
            created_by=contributor_name
        )
    
    if ku:
        db.add(ku)
        db.flush()
    
    return ku


def _map_ku_type_code(ku_type_code: Optional[str]) -> str:
    """Map contribution ku_type_code to legacy KU type"""
    if not ku_type_code:
        return "core"
    
    # Map from detailed type codes to legacy types
    type_mapping = {
        # Product & Tech
        "core.product_feature": "core",
        "core.tech_spec": "core",
        "core.delivery_guide": "whitepaper",
        "core.integration": "whitepaper",
        "core.release_notes": "core",
        # Solutions
        "solution.industry": "solution",
        "solution.proposal": "solution",
        "solution.poc": "solution",
        "sales.competitor": "whitepaper",
        "sales.playbook": "faq",
        # Cases
        "case.customer_story": "case",
        "case.public_reference": "case",
        # Quote & Business
        "quote.pricebook": "quote",
        "biz.contract_sla": "whitepaper",
        "bid.rfp_response": "solution",
        "compliance.certification": "whitepaper",
        # Delivery
        "delivery.sop": "whitepaper",
        "support.troubleshooting": "faq",
        "enablement.training": "whitepaper",
        # Field
        "field.signal": "case",
        "eval.dataset": "core",
    }
    
    return type_mapping.get(ku_type_code, "core")


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

