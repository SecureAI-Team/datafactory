"""
重复检测与合并 API
"""
import json
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from ..db import get_db
from ..models import DedupGroup, KnowledgeUnit, KURelation
from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/dedup", tags=["dedup"])


class DedupGroupResponse(BaseModel):
    group_id: str
    ku_ids: List[str]
    similarity_score: float
    status: str
    merge_result_ku_id: Optional[int] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str


class ApproveRequest(BaseModel):
    group_id: str
    reviewer: str


class DismissRequest(BaseModel):
    group_id: str
    reviewer: str
    reason: Optional[str] = None


class MergeRequest(BaseModel):
    ku_ids: List[str]
    merger: str
    strategy: str = "comprehensive"  # comprehensive, newest


@router.get("/pending", response_model=List[DedupGroupResponse])
async def get_pending_groups(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    """获取待处理的重复组"""
    try:
        groups = db.query(DedupGroup).filter(
            DedupGroup.status == "pending"
        ).order_by(DedupGroup.created_at.desc()).limit(limit).all()
        
        return [
            DedupGroupResponse(
                group_id=g.group_id,
                ku_ids=g.ku_ids if isinstance(g.ku_ids, list) else json.loads(g.ku_ids),
                similarity_score=g.similarity_score or 0,
                status=g.status,
                merge_result_ku_id=g.merge_result_ku_id,
                reviewed_by=g.reviewed_by,
                reviewed_at=g.reviewed_at.isoformat() if g.reviewed_at else None,
                created_at=g.created_at.isoformat() if g.created_at else "",
            )
            for g in groups
        ]
    except Exception as e:
        logger.error(f"Get pending groups error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=List[DedupGroupResponse])
async def get_all_groups(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    """获取所有重复组"""
    try:
        query = db.query(DedupGroup)
        if status:
            query = query.filter(DedupGroup.status == status)
        
        groups = query.order_by(DedupGroup.created_at.desc()).limit(limit).all()
        
        return [
            DedupGroupResponse(
                group_id=g.group_id,
                ku_ids=g.ku_ids if isinstance(g.ku_ids, list) else json.loads(g.ku_ids),
                similarity_score=g.similarity_score or 0,
                status=g.status,
                merge_result_ku_id=g.merge_result_ku_id,
                reviewed_by=g.reviewed_by,
                reviewed_at=g.reviewed_at.isoformat() if g.reviewed_at else None,
                created_at=g.created_at.isoformat() if g.created_at else "",
            )
            for g in groups
        ]
    except Exception as e:
        logger.error(f"Get all groups error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve")
async def approve_merge(
    request: ApproveRequest,
    db=Depends(get_db),
):
    """批准合并（将由 Airflow DAG 执行）"""
    try:
        group = db.query(DedupGroup).filter(
            DedupGroup.group_id == request.group_id
        ).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        if group.status != "pending":
            raise HTTPException(status_code=400, detail=f"Group is not pending, current status: {group.status}")
        
        group.status = "approved"
        group.reviewed_by = request.reviewer
        group.reviewed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Group {request.group_id} approved for merge",
            "group_id": request.group_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve merge error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dismiss")
async def dismiss_group(
    request: DismissRequest,
    db=Depends(get_db),
):
    """忽略/驳回重复组（标记为误判）"""
    try:
        group = db.query(DedupGroup).filter(
            DedupGroup.group_id == request.group_id
        ).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        if group.status != "pending":
            raise HTTPException(status_code=400, detail=f"Group is not pending, current status: {group.status}")
        
        group.status = "dismissed"
        group.reviewed_by = request.reviewer
        group.reviewed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Group {request.group_id} dismissed",
            "group_id": request.group_id,
            "reason": request.reason,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dismiss group error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dedup_stats(db=Depends(get_db)):
    """获取重复检测统计"""
    try:
        from sqlalchemy import func
        
        total = db.query(func.count(DedupGroup.id)).scalar() or 0
        pending = db.query(func.count(DedupGroup.id)).filter(
            DedupGroup.status == "pending"
        ).scalar() or 0
        approved = db.query(func.count(DedupGroup.id)).filter(
            DedupGroup.status == "approved"
        ).scalar() or 0
        merged = db.query(func.count(DedupGroup.id)).filter(
            DedupGroup.status == "merged"
        ).scalar() or 0
        dismissed = db.query(func.count(DedupGroup.id)).filter(
            DedupGroup.status == "dismissed"
        ).scalar() or 0
        
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "merged": merged,
            "dismissed": dismissed,
        }
        
    except Exception as e:
        logger.error(f"Get dedup stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group/{group_id}/details")
async def get_group_details(
    group_id: str,
    db=Depends(get_db),
):
    """获取重复组详情，包括各 KU 的内容预览"""
    try:
        group = db.query(DedupGroup).filter(
            DedupGroup.group_id == group_id
        ).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        ku_ids = group.ku_ids if isinstance(group.ku_ids, list) else json.loads(group.ku_ids)
        
        # 获取各 KU 详情
        kus = db.query(KnowledgeUnit).filter(
            KnowledgeUnit.id.in_([int(id) for id in ku_ids])
        ).all()
        
        ku_details = []
        for ku in kus:
            ku_details.append({
                "id": str(ku.id),
                "title": ku.title,
                "summary": ku.summary[:500] if ku.summary else "",
                "ku_type": ku.ku_type,
                "product_id": ku.product_id,
                "version": ku.version,
                "status": ku.status,
            })
        
        return {
            "group_id": group.group_id,
            "similarity_score": group.similarity_score,
            "status": group.status,
            "kus": ku_details,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get group details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

