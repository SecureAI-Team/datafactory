"""
智能推荐引擎
基于用户行为、内容相似度和协同过滤提供推荐
"""
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .behavior_tracker import (
    get_behavior_tracker,
    BehaviorTracker,
    BehaviorType,
    TargetType,
    UserProfile,
)

logger = logging.getLogger(__name__)


class RecommendationType(str, Enum):
    """推荐类型"""
    SIMILAR_CONTENT = "similar_content"       # 相似内容
    POPULAR = "popular"                       # 热门内容
    COLLABORATIVE = "collaborative"           # 协同过滤
    PERSONALIZED = "personalized"             # 个性化
    RELATED_QUERY = "related_query"           # 相关问题
    FOLLOW_UP = "follow_up"                   # 追问建议


@dataclass
class Recommendation:
    """推荐项"""
    rec_type: RecommendationType
    target_type: TargetType
    target_id: str
    title: str = ""
    summary: str = ""
    score: float = 0.0
    reason: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class RecommendationResult:
    """推荐结果"""
    recommendations: List[Recommendation] = field(default_factory=list)
    user_id: str = ""
    context_query: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "recommendations": [
                {
                    "type": r.rec_type.value,
                    "target_type": r.target_type.value,
                    "target_id": r.target_id,
                    "title": r.title,
                    "summary": r.summary[:100] if r.summary else "",
                    "score": r.score,
                    "reason": r.reason,
                }
                for r in self.recommendations
            ],
        }


class RecommendationEngine:
    """推荐引擎"""
    
    def __init__(self, behavior_tracker: BehaviorTracker = None):
        self._tracker = behavior_tracker
    
    @property
    def tracker(self) -> BehaviorTracker:
        if self._tracker is None:
            self._tracker = get_behavior_tracker()
        return self._tracker
    
    def recommend(
        self,
        user_id: str,
        context_query: str = "",
        current_ku_id: str = None,
        limit: int = 5,
        rec_types: List[RecommendationType] = None,
    ) -> RecommendationResult:
        """
        生成推荐
        
        Args:
            user_id: 用户ID
            context_query: 当前查询上下文
            current_ku_id: 当前浏览的 KU ID
            limit: 推荐数量
            rec_types: 推荐类型（为空则使用全部）
        
        Returns:
            RecommendationResult
        """
        result = RecommendationResult(user_id=user_id, context_query=context_query)
        
        rec_types = rec_types or [
            RecommendationType.SIMILAR_CONTENT,
            RecommendationType.POPULAR,
            RecommendationType.COLLABORATIVE,
            RecommendationType.RELATED_QUERY,
        ]
        
        all_recs = []
        
        # 1. 相似内容推荐
        if RecommendationType.SIMILAR_CONTENT in rec_types and current_ku_id:
            similar = self._get_similar_content(current_ku_id, limit=3)
            all_recs.extend(similar)
        
        # 2. 热门推荐
        if RecommendationType.POPULAR in rec_types:
            popular = self._get_popular_content(limit=3)
            all_recs.extend(popular)
        
        # 3. 协同过滤推荐
        if RecommendationType.COLLABORATIVE in rec_types:
            collaborative = self._get_collaborative(user_id, limit=3)
            all_recs.extend(collaborative)
        
        # 4. 相关问题推荐
        if RecommendationType.RELATED_QUERY in rec_types and context_query:
            related = self._get_related_queries(context_query, user_id, limit=3)
            all_recs.extend(related)
        
        # 5. 个性化推荐
        if RecommendationType.PERSONALIZED in rec_types:
            personalized = self._get_personalized(user_id, limit=3)
            all_recs.extend(personalized)
        
        # 去重和排序
        seen_ids = set()
        unique_recs = []
        for rec in sorted(all_recs, key=lambda r: r.score, reverse=True):
            if rec.target_id not in seen_ids:
                seen_ids.add(rec.target_id)
                unique_recs.append(rec)
        
        result.recommendations = unique_recs[:limit]
        
        return result
    
    def _get_similar_content(
        self,
        ku_id: str,
        limit: int = 3,
    ) -> List[Recommendation]:
        """基于内容相似度推荐"""
        recommendations = []
        
        try:
            from .retrieval import search
            
            # 获取当前 KU 的信息（这里简化处理）
            # 实际应该从 OpenSearch 获取 KU 详情
            
            # 使用 more_like_this 或相似查询
            # 简化版：基于 KU ID 搜索相关内容
            hits = search(f"related:{ku_id}", top_k=limit + 1)
            
            for hit in hits:
                if hit.get("_id") == ku_id:
                    continue
                
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.SIMILAR_CONTENT,
                    target_type=TargetType.KU,
                    target_id=hit.get("_id", ""),
                    title=hit.get("title", ""),
                    summary=hit.get("summary", ""),
                    score=hit.get("_score", 0) / 10,  # 归一化
                    reason="与当前内容相似",
                ))
                
        except Exception as e:
            logger.error(f"Similar content recommendation failed: {e}")
        
        return recommendations[:limit]
    
    def _get_popular_content(self, limit: int = 3) -> List[Recommendation]:
        """热门内容推荐"""
        recommendations = []
        
        try:
            popular_kus = self.tracker.get_popular_kus(limit=limit)
            
            for ku in popular_kus:
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.POPULAR,
                    target_type=TargetType.KU,
                    target_id=ku["ku_id"],
                    title=ku.get("title", ku["ku_id"]),
                    score=ku["score"] / 100,  # 归一化
                    reason=f"热门内容 ({ku['view_count']} 次浏览)",
                ))
                
        except Exception as e:
            logger.error(f"Popular recommendation failed: {e}")
        
        return recommendations
    
    def _get_collaborative(
        self,
        user_id: str,
        limit: int = 3,
    ) -> List[Recommendation]:
        """协同过滤推荐"""
        recommendations = []
        
        try:
            # 找到相似用户
            similar_users = self.tracker.get_similar_users(user_id, limit=5)
            
            if not similar_users:
                return []
            
            # 获取当前用户已浏览的 KU
            user_behaviors = self.tracker.get_user_behaviors(
                user_id,
                behavior_type=BehaviorType.VIEW,
                days=30,
            )
            viewed_kus = {b.target_id for b in user_behaviors if b.target_id}
            
            # 收集相似用户浏览但当前用户未浏览的 KU
            candidate_kus: Dict[str, int] = {}
            
            for similar_user_id in similar_users:
                similar_behaviors = self.tracker.get_user_behaviors(
                    similar_user_id,
                    behavior_type=BehaviorType.VIEW,
                    days=30,
                )
                
                for behavior in similar_behaviors:
                    if behavior.target_id and behavior.target_id not in viewed_kus:
                        candidate_kus[behavior.target_id] = candidate_kus.get(behavior.target_id, 0) + 1
            
            # 排序并生成推荐
            sorted_candidates = sorted(candidate_kus.items(), key=lambda x: x[1], reverse=True)
            
            for ku_id, count in sorted_candidates[:limit]:
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.COLLABORATIVE,
                    target_type=TargetType.KU,
                    target_id=ku_id,
                    score=count / len(similar_users),
                    reason=f"相似用户也在看",
                ))
                
        except Exception as e:
            logger.error(f"Collaborative recommendation failed: {e}")
        
        return recommendations
    
    def _get_related_queries(
        self,
        query: str,
        user_id: str,
        limit: int = 3,
    ) -> List[Recommendation]:
        """相关问题推荐"""
        recommendations = []
        
        try:
            # 获取用户最近的查询
            profile = self.tracker.get_user_profile(user_id)
            if not profile:
                return []
            
            # 找到与当前查询相关的历史查询
            related_queries = []
            query_words = set(query.lower().split())
            
            for recent_query in profile.recent_queries:
                if recent_query == query:
                    continue
                
                recent_words = set(recent_query.lower().split())
                overlap = len(query_words & recent_words)
                
                if overlap > 0:
                    related_queries.append((recent_query, overlap))
            
            # 排序
            related_queries.sort(key=lambda x: x[1], reverse=True)
            
            for related_query, _ in related_queries[:limit]:
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.RELATED_QUERY,
                    target_type=TargetType.KU,
                    target_id=f"query:{related_query}",
                    title=related_query,
                    score=0.5,
                    reason="您之前问过的相关问题",
                ))
                
        except Exception as e:
            logger.error(f"Related queries recommendation failed: {e}")
        
        return recommendations
    
    def _get_personalized(
        self,
        user_id: str,
        limit: int = 3,
    ) -> List[Recommendation]:
        """个性化推荐"""
        recommendations = []
        
        try:
            from .retrieval import search
            
            profile = self.tracker.get_user_profile(user_id)
            if not profile:
                return []
            
            # 基于用户偏好场景和意图搜索
            if profile.preferred_scenarios:
                scenario = profile.preferred_scenarios[0]
                hits = search(f"scenario:{scenario}", top_k=limit)
                
                for hit in hits:
                    recommendations.append(Recommendation(
                        rec_type=RecommendationType.PERSONALIZED,
                        target_type=TargetType.KU,
                        target_id=hit.get("_id", ""),
                        title=hit.get("title", ""),
                        summary=hit.get("summary", ""),
                        score=0.6,
                        reason=f"基于您对 {scenario} 的兴趣",
                    ))
                    
        except Exception as e:
            logger.error(f"Personalized recommendation failed: {e}")
        
        return recommendations
    
    def get_follow_up_suggestions(
        self,
        query: str,
        response: str,
        intent_type: str = "",
        limit: int = 3,
    ) -> List[str]:
        """
        生成追问建议
        
        基于当前查询和回复，生成用户可能想要追问的问题
        """
        suggestions = []
        
        # 基于意图类型生成
        intent_suggestions = {
            "technical_qa": [
                "能详细解释一下原理吗？",
                "有什么注意事项？",
                "和其他方案相比有什么优势？",
            ],
            "parameter_query": [
                "这个参数在什么范围内是正常的？",
                "如何调整这个参数？",
                "还有哪些相关参数需要关注？",
            ],
            "calculation": [
                "如果产能要求翻倍呢？",
                "能给出具体的型号推荐吗？",
                "成本大概是多少？",
            ],
            "comparison": [
                "综合来看推荐哪个？",
                "在具体场景下哪个更合适？",
                "性价比如何？",
            ],
        }
        
        if intent_type in intent_suggestions:
            suggestions.extend(intent_suggestions[intent_type][:limit])
        else:
            # 通用建议
            suggestions = [
                "能举个具体例子吗？",
                "还有其他需要注意的地方吗？",
                "这个问题的最佳实践是什么？",
            ][:limit]
        
        return suggestions


# ==================== 模块级便捷函数 ====================

_default_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """获取推荐引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = RecommendationEngine()
    return _default_engine


def get_recommendations(
    user_id: str,
    context_query: str = "",
    limit: int = 5,
) -> RecommendationResult:
    """便捷函数：获取推荐"""
    return get_recommendation_engine().recommend(
        user_id=user_id,
        context_query=context_query,
        limit=limit,
    )


def get_follow_up_suggestions(
    query: str,
    response: str,
    intent_type: str = "",
) -> List[str]:
    """便捷函数：获取追问建议"""
    return get_recommendation_engine().get_follow_up_suggestions(
        query, response, intent_type
    )

