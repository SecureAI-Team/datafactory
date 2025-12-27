"""
推荐 API
智能推荐、追问建议
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..services.recommendation_engine import (
    get_recommendation_engine,
    get_recommendations,
    get_follow_up_suggestions,
    RecommendationType,
)
from ..services.behavior_tracker import (
    get_behavior_tracker,
    record_behavior,
    record_query,
    record_ku_view,
    BehaviorType,
    TargetType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommend", tags=["recommendation"])


# ==================== 请求/响应模型 ====================

class RecordBehaviorRequest(BaseModel):
    """记录行为请求"""
    user_id: str
    behavior_type: str  # query/view/click/feedback
    target_type: Optional[str] = None  # ku/document/scenario
    target_id: Optional[str] = None
    ku_id: Optional[str] = None  # 简写，等同于 target_type=ku, target_id=ku_id
    query: Optional[str] = None
    intent_type: Optional[str] = None
    scenario_id: Optional[str] = None
    session_id: Optional[str] = None
    is_positive: Optional[bool] = None  # 用于 feedback 类型
    rating: Optional[int] = None  # 评分 1-5
    metadata: Optional[dict] = None


class RecommendRequest(BaseModel):
    """推荐请求"""
    user_id: str
    context_query: Optional[str] = None
    current_ku_id: Optional[str] = None
    limit: int = 5
    rec_types: Optional[List[str]] = None


class FollowUpRequest(BaseModel):
    """追问建议请求"""
    query: str
    response: str
    intent_type: Optional[str] = None
    limit: int = 3


# ==================== API 端点 ====================

@router.post("/track")
async def track_behavior(request: RecordBehaviorRequest):
    """
    记录用户行为
    
    Args:
        request: 行为记录请求
    
    Returns:
        记录状态
    """
    try:
        behavior_type = BehaviorType(request.behavior_type)
        
        # 处理 ku_id 简写
        target_type = None
        target_id = request.target_id
        
        if request.ku_id:
            target_type = TargetType.KU
            target_id = request.ku_id
        elif request.target_type:
            target_type = TargetType(request.target_type)
        
        # 构建 metadata
        metadata = request.metadata or {}
        if request.is_positive is not None:
            metadata["positive"] = request.is_positive
        if request.rating is not None:
            metadata["rating"] = request.rating
        
        record_behavior(
            user_id=request.user_id,
            behavior_type=behavior_type,
            target_type=target_type,
            target_id=target_id,
            query=request.query or "",
            intent_type=request.intent_type or "",
            scenario_id=request.scenario_id or "",
            session_id=request.session_id or "",
            metadata=metadata,
        )
        
        return {"status": "recorded", "behavior_type": request.behavior_type}
        
    except ValueError as e:
        return {"status": "error", "error": f"Invalid type: {e}"}
    except Exception as e:
        logger.error(f"Track behavior failed: {e}")
        return {"status": "error", "error": str(e)}


@router.get("")
async def get_recommend(
    user_id: str = Query(..., description="用户ID"),
    context: str = Query(None, description="当前查询上下文"),
    ku_id: str = Query(None, description="当前浏览的KU ID"),
    limit: int = Query(5, description="推荐数量"),
):
    """
    获取推荐（GET 方式）
    
    Args:
        user_id: 用户ID
        context: 当前上下文
        ku_id: 当前 KU ID
        limit: 数量限制
    
    Returns:
        推荐列表
    """
    try:
        engine = get_recommendation_engine()
        result = engine.recommend(
            user_id=user_id,
            context_query=context or "",
            current_ku_id=ku_id,
            limit=limit,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        return {"error": str(e), "recommendations": []}


@router.post("")
async def post_recommend(request: RecommendRequest):
    """
    获取推荐（POST 方式）
    """
    try:
        rec_types = None
        if request.rec_types:
            rec_types = [RecommendationType(t) for t in request.rec_types]
        
        engine = get_recommendation_engine()
        result = engine.recommend(
            user_id=request.user_id,
            context_query=request.context_query or "",
            current_ku_id=request.current_ku_id,
            limit=request.limit,
            rec_types=rec_types,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        return {"error": str(e), "recommendations": []}


@router.post("/follow-up")
async def get_follow_up(request: FollowUpRequest):
    """
    获取追问建议
    
    Args:
        request: 追问请求
    
    Returns:
        追问建议列表
    """
    suggestions = get_follow_up_suggestions(
        query=request.query,
        response=request.response,
        intent_type=request.intent_type or "",
    )
    
    return {
        "suggestions": suggestions[:request.limit],
        "query": request.query,
    }


@router.get("/popular")
async def get_popular(limit: int = Query(10, description="数量")):
    """获取热门内容"""
    try:
        tracker = get_behavior_tracker()
        popular = tracker.get_popular_kus(limit=limit)
        
        return {
            "popular": popular,
            "count": len(popular),
        }
        
    except Exception as e:
        logger.error(f"Get popular failed: {e}")
        return {"error": str(e), "popular": []}


@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    """获取用户画像"""
    try:
        tracker = get_behavior_tracker()
        profile = tracker.get_user_profile(user_id)
        
        if not profile:
            return {"found": False, "user_id": user_id}
        
        return {
            "found": True,
            "user_id": user_id,
            "total_queries": profile.total_queries,
            "preferred_scenarios": profile.preferred_scenarios,
            "preferred_intents": profile.preferred_intents,
            "recent_queries": profile.recent_queries[-5:],
            "active_hours": profile.active_hours,
        }
        
    except Exception as e:
        logger.error(f"Get profile failed: {e}")
        return {"error": str(e)}


@router.get("/similar-users/{user_id}")
async def get_similar_users(
    user_id: str,
    limit: int = Query(10, description="数量"),
):
    """获取相似用户"""
    try:
        tracker = get_behavior_tracker()
        similar = tracker.get_similar_users(user_id, limit=limit)
        
        return {
            "user_id": user_id,
            "similar_users": similar,
            "count": len(similar),
        }
        
    except Exception as e:
        logger.error(f"Get similar users failed: {e}")
        return {"error": str(e), "similar_users": []}


@router.get("/ku-stats/{ku_id}")
async def get_ku_stats(ku_id: str):
    """获取 KU 统计"""
    try:
        tracker = get_behavior_tracker()
        stats = tracker.get_ku_stats(ku_id)
        
        return {
            "ku_id": ku_id,
            **stats,
        }
        
    except Exception as e:
        logger.error(f"Get KU stats failed: {e}")
        return {"error": str(e)}

