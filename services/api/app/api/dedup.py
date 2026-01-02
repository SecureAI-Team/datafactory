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
from ..clients.opensearch_client import os_client
from ..config import settings

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


class CreateDedupGroupRequest(BaseModel):
    ku_ids: List[str]
    similarity_score: float = 0.8
    creator: str


@router.post("/create", response_model=DedupGroupResponse)
async def create_dedup_group(
    request: CreateDedupGroupRequest,
    db=Depends(get_db),
):
    """手动创建重复组"""
    import uuid
    
    try:
        if len(request.ku_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 KU IDs required")
        
        # Validate that all KU IDs exist
        for ku_id in request.ku_ids:
            ku = db.query(KnowledgeUnit).filter(KnowledgeUnit.id == int(ku_id)).first()
            if not ku:
                raise HTTPException(status_code=404, detail=f"KU {ku_id} not found")
        
        # Check if any of these KUs are already in a pending dedup group
        existing = db.query(DedupGroup).filter(
            DedupGroup.status == "pending"
        ).all()
        
        for group in existing:
            group_ku_ids = group.ku_ids if isinstance(group.ku_ids, list) else json.loads(group.ku_ids)
            overlap = set(request.ku_ids) & set(group_ku_ids)
            if overlap:
                raise HTTPException(
                    status_code=400, 
                    detail=f"KU(s) {list(overlap)} already in pending group {group.group_id}"
                )
        
        # Create new dedup group
        group_id = f"manual-{uuid.uuid4().hex[:12]}"
        
        new_group = DedupGroup(
            group_id=group_id,
            ku_ids=request.ku_ids,
            similarity_score=request.similarity_score,
            status="pending",
            reviewed_by=request.creator,  # Track who created it
        )
        
        db.add(new_group)
        db.commit()
        db.refresh(new_group)
        
        return DedupGroupResponse(
            group_id=new_group.group_id,
            ku_ids=new_group.ku_ids if isinstance(new_group.ku_ids, list) else json.loads(new_group.ku_ids),
            similarity_score=new_group.similarity_score or 0,
            status=new_group.status,
            merge_result_ku_id=new_group.merge_result_ku_id,
            reviewed_by=new_group.reviewed_by,
            reviewed_at=new_group.reviewed_at.isoformat() if new_group.reviewed_at else None,
            created_at=new_group.created_at.isoformat() if new_group.created_at else "",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create dedup group error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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


class SimilarKUResponse(BaseModel):
    id: str
    title: str
    summary: str
    ku_type: Optional[str] = None
    product_id: Optional[str] = None
    similarity_score: float


@router.get("/similar/{ku_id}", response_model=List[SimilarKUResponse])
async def find_similar_kus(
    ku_id: int,
    min_similarity: float = Query(0.5, ge=0, le=1, description="Minimum similarity score"),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db),
):
    """
    查找与指定 KU 相似的其他 KU
    使用 OpenSearch 的 more_like_this 查询
    """
    try:
        # Get the source KU
        source_ku = db.query(KnowledgeUnit).filter(KnowledgeUnit.id == ku_id).first()
        if not source_ku:
            raise HTTPException(status_code=404, detail="KU not found")
        
        # Prepare text for similarity search
        source_text = f"{source_ku.title or ''} {source_ku.summary or ''}"
        
        if not source_text.strip():
            raise HTTPException(status_code=400, detail="KU has no content for similarity search")
        
        # Build more_like_this query
        mlt_query = {
            "query": {
                "more_like_this": {
                    "fields": ["title", "summary", "full_text"],
                    "like": source_text[:1000],  # Limit text length
                    "min_term_freq": 1,
                    "min_doc_freq": 1,
                    "max_query_terms": 25,
                    "minimum_should_match": "30%",
                }
            },
            "size": limit + 1,  # +1 to exclude self
            "_source": ["title", "summary", "ku_type", "product_id"],
        }
        
        try:
            res = os_client.search(index=settings.os_index, body=mlt_query)
        except Exception as e:
            logger.error(f"OpenSearch MLT query error: {e}")
            # Fall back to text-based search
            return _fallback_similarity_search(source_ku, limit, db)
        
        # Parse results
        similar_kus = []
        max_score = res["hits"]["max_score"] or 1.0
        
        for hit in res["hits"]["hits"]:
            hit_id = hit["_id"]
            # Skip self
            if str(hit_id) == str(ku_id):
                continue
            
            # Calculate normalized similarity score
            score = hit["_score"] / max_score if max_score > 0 else 0
            
            if score >= min_similarity:
                source = hit.get("_source", {})
                similar_kus.append(SimilarKUResponse(
                    id=str(hit_id),
                    title=source.get("title", ""),
                    summary=(source.get("summary", "") or "")[:300],
                    ku_type=source.get("ku_type"),
                    product_id=source.get("product_id"),
                    similarity_score=round(score, 3),
                ))
        
        return similar_kus[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Find similar KUs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _fallback_similarity_search(
    source_ku: KnowledgeUnit,
    limit: int,
    db,
) -> List[SimilarKUResponse]:
    """
    Fallback similarity search using database text matching
    """
    from sqlalchemy import or_
    
    # Get KUs with similar title or ku_type
    similar_kus = db.query(KnowledgeUnit).filter(
        KnowledgeUnit.id != source_ku.id,
        or_(
            KnowledgeUnit.ku_type == source_ku.ku_type,
            KnowledgeUnit.product_id == source_ku.product_id,
        )
    ).limit(limit).all()
    
    results = []
    for ku in similar_kus:
        # Simple similarity based on shared attributes
        score = 0.5
        if ku.ku_type == source_ku.ku_type:
            score += 0.2
        if ku.product_id == source_ku.product_id:
            score += 0.2
        
        results.append(SimilarKUResponse(
            id=str(ku.id),
            title=ku.title or "",
            summary=(ku.summary or "")[:300],
            ku_type=ku.ku_type,
            product_id=ku.product_id,
            similarity_score=round(score, 3),
        ))
    
    return results


class MergeExecuteRequest(BaseModel):
    strategy: str = "comprehensive"  # comprehensive, newest, manual


@router.post("/group/{group_id}/merge")
async def execute_merge(
    group_id: str,
    request: MergeExecuteRequest,
    db=Depends(get_db),
):
    """
    执行合并操作（立即执行，不等待 Airflow DAG）
    仅对已批准 (approved) 状态的组有效
    """
    try:
        group = db.query(DedupGroup).filter(
            DedupGroup.group_id == group_id
        ).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        if group.status != "approved":
            raise HTTPException(
                status_code=400, 
                detail=f"Group must be approved before merging. Current status: {group.status}"
            )
        
        ku_ids = group.ku_ids if isinstance(group.ku_ids, list) else json.loads(group.ku_ids)
        
        if len(ku_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 KUs required for merge")
        
        # Get KU details
        kus = db.query(KnowledgeUnit).filter(
            KnowledgeUnit.id.in_([int(id) for id in ku_ids])
        ).all()
        
        if len(kus) < 2:
            raise HTTPException(status_code=400, detail="Not enough KUs found to merge")
        
        # Execute merge based on strategy
        if request.strategy == "newest":
            # Keep the newest (highest version) KU as primary
            primary_ku = max(kus, key=lambda ku: ku.version or 0)
            merged_title = primary_ku.title
            merged_summary = primary_ku.summary
            merged_body = primary_ku.body_markdown
        else:
            # Comprehensive merge: combine all content
            primary_ku = max(kus, key=lambda ku: len(ku.summary or "") + len(ku.body_markdown or ""))
            
            # Merge summaries
            all_summaries = [ku.summary for ku in kus if ku.summary]
            merged_summary = "\n\n".join(all_summaries) if all_summaries else primary_ku.summary
            if merged_summary and len(merged_summary) > 2000:
                merged_summary = merged_summary[:2000] + "..."
            
            merged_title = primary_ku.title
            merged_body = primary_ku.body_markdown
        
        # Create new merged KU
        merged_ku = KnowledgeUnit(
            title=f"[Merged] {merged_title}",
            summary=merged_summary,
            body_markdown=merged_body,
            ku_type=primary_ku.ku_type,
            product_id=primary_ku.product_id,
            version=(max(ku.version or 0 for ku in kus) + 1),
            is_primary=True,
            status="published",
            created_by="system_merge",
            merge_source_ids=[int(id) for id in ku_ids],
        )
        
        db.add(merged_ku)
        db.flush()  # Get the new ID
        
        # Mark source KUs as merged
        for ku in kus:
            ku.status = "merged"
            ku.parent_ku_id = merged_ku.id
        
        # Create relation records
        for ku_id in ku_ids:
            relation = KURelation(
                source_ku_id=merged_ku.id,
                target_ku_id=int(ku_id),
                relation_type="merged_from",
                metadata={"strategy": request.strategy},
            )
            db.add(relation)
        
        # Update group status
        group.status = "merged"
        group.merge_result_ku_id = merged_ku.id
        group.reviewed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully merged {len(kus)} KUs",
            "merged_ku_id": merged_ku.id,
            "source_ku_ids": ku_ids,
            "strategy": request.strategy,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute merge error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

