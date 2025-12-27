"""
用户行为跟踪服务
记录和分析用户行为，为推荐提供数据支持
"""
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class BehaviorType(str, Enum):
    """行为类型"""
    QUERY = "query"             # 查询
    VIEW = "view"               # 浏览
    CLICK = "click"             # 点击
    FEEDBACK = "feedback"       # 反馈
    BOOKMARK = "bookmark"       # 收藏
    SHARE = "share"             # 分享


class TargetType(str, Enum):
    """目标类型"""
    KU = "ku"                   # 知识单元
    DOCUMENT = "document"       # 文档
    SCENARIO = "scenario"       # 场景
    PRODUCT = "product"         # 产品


@dataclass
class BehaviorRecord:
    """行为记录"""
    user_id: str
    behavior_type: BehaviorType
    target_type: Optional[TargetType] = None
    target_id: Optional[str] = None
    query: str = ""
    intent_type: str = ""
    scenario_id: str = ""
    session_id: str = ""
    metadata: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    total_queries: int = 0
    preferred_scenarios: List[str] = field(default_factory=list)
    preferred_intents: List[str] = field(default_factory=list)
    recent_queries: List[str] = field(default_factory=list)
    topic_interests: Dict[str, float] = field(default_factory=dict)
    active_hours: List[int] = field(default_factory=list)
    avg_session_duration: float = 0.0


class BehaviorTracker:
    """行为跟踪器"""
    
    def __init__(self):
        # 内存存储（生产环境应使用数据库）
        self._behaviors: List[BehaviorRecord] = []
        self._ku_stats: Dict[str, Dict] = defaultdict(lambda: {
            "view_count": 0,
            "click_count": 0,
            "feedback_positive": 0,
            "feedback_negative": 0,
            "ratings": [],
        })
        self._user_profiles: Dict[str, UserProfile] = {}
    
    def record(
        self,
        user_id: str,
        behavior_type: BehaviorType,
        target_type: TargetType = None,
        target_id: str = None,
        query: str = "",
        intent_type: str = "",
        scenario_id: str = "",
        session_id: str = "",
        metadata: Dict = None,
    ) -> None:
        """
        记录用户行为
        
        Args:
            user_id: 用户ID
            behavior_type: 行为类型
            target_type: 目标类型
            target_id: 目标ID
            query: 查询内容
            intent_type: 意图类型
            scenario_id: 场景ID
            session_id: 会话ID
            metadata: 附加数据
        """
        record = BehaviorRecord(
            user_id=user_id,
            behavior_type=behavior_type,
            target_type=target_type,
            target_id=target_id,
            query=query,
            intent_type=intent_type,
            scenario_id=scenario_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        
        self._behaviors.append(record)
        
        # 更新 KU 统计
        if target_type == TargetType.KU and target_id:
            self._update_ku_stats(target_id, behavior_type, metadata)
        
        # 更新用户画像
        self._update_user_profile(user_id, record)
        
        logger.debug(f"Recorded behavior: user={user_id}, type={behavior_type.value}")
    
    def _update_ku_stats(
        self,
        ku_id: str,
        behavior_type: BehaviorType,
        metadata: Dict = None,
    ) -> None:
        """更新 KU 统计"""
        stats = self._ku_stats[ku_id]
        
        if behavior_type == BehaviorType.VIEW:
            stats["view_count"] += 1
        elif behavior_type == BehaviorType.CLICK:
            stats["click_count"] += 1
        elif behavior_type == BehaviorType.FEEDBACK:
            if metadata:
                if metadata.get("positive"):
                    stats["feedback_positive"] += 1
                else:
                    stats["feedback_negative"] += 1
                
                if "rating" in metadata:
                    stats["ratings"].append(metadata["rating"])
        
        stats["last_accessed"] = time.time()
    
    def _update_user_profile(self, user_id: str, record: BehaviorRecord) -> None:
        """更新用户画像"""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)
        
        profile = self._user_profiles[user_id]
        
        if record.behavior_type == BehaviorType.QUERY:
            profile.total_queries += 1
            
            # 更新最近查询
            if record.query:
                profile.recent_queries.append(record.query)
                profile.recent_queries = profile.recent_queries[-20:]  # 保留最近20条
            
            # 更新偏好场景
            if record.scenario_id and record.scenario_id not in profile.preferred_scenarios:
                profile.preferred_scenarios.append(record.scenario_id)
                profile.preferred_scenarios = profile.preferred_scenarios[-10:]
            
            # 更新偏好意图
            if record.intent_type and record.intent_type not in profile.preferred_intents:
                profile.preferred_intents.append(record.intent_type)
                profile.preferred_intents = profile.preferred_intents[-5:]
        
        # 更新活跃时间
        hour = datetime.fromtimestamp(record.created_at).hour
        if hour not in profile.active_hours:
            profile.active_hours.append(hour)
    
    def get_user_behaviors(
        self,
        user_id: str,
        behavior_type: BehaviorType = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[BehaviorRecord]:
        """获取用户行为记录"""
        cutoff = time.time() - days * 86400
        
        records = [
            r for r in self._behaviors
            if r.user_id == user_id
            and r.created_at >= cutoff
            and (behavior_type is None or r.behavior_type == behavior_type)
        ]
        
        return sorted(records, key=lambda r: r.created_at, reverse=True)[:limit]
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        return self._user_profiles.get(user_id)
    
    def get_ku_stats(self, ku_id: str) -> Dict:
        """获取 KU 统计"""
        stats = self._ku_stats.get(ku_id, {})
        
        # 计算平均评分
        if stats.get("ratings"):
            stats["avg_rating"] = sum(stats["ratings"]) / len(stats["ratings"])
        else:
            stats["avg_rating"] = 0
        
        return stats
    
    def get_popular_kus(self, limit: int = 10) -> List[Dict]:
        """获取热门 KU"""
        # 按综合热度排序
        scored = []
        for ku_id, stats in self._ku_stats.items():
            score = (
                stats["view_count"] * 1 +
                stats["click_count"] * 2 +
                stats["feedback_positive"] * 5 -
                stats["feedback_negative"] * 3
            )
            scored.append({
                "ku_id": ku_id,
                "score": score,
                **stats,
            })
        
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]
    
    def get_similar_users(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[str]:
        """
        获取相似用户（基于行为模式）
        
        简化版：基于场景和意图偏好的 Jaccard 相似度
        """
        target_profile = self._user_profiles.get(user_id)
        if not target_profile:
            return []
        
        target_scenarios = set(target_profile.preferred_scenarios)
        target_intents = set(target_profile.preferred_intents)
        
        similarities = []
        for other_id, other_profile in self._user_profiles.items():
            if other_id == user_id:
                continue
            
            other_scenarios = set(other_profile.preferred_scenarios)
            other_intents = set(other_profile.preferred_intents)
            
            # Jaccard 相似度
            scenario_sim = len(target_scenarios & other_scenarios) / len(target_scenarios | other_scenarios) if target_scenarios | other_scenarios else 0
            intent_sim = len(target_intents & other_intents) / len(target_intents | other_intents) if target_intents | other_intents else 0
            
            similarity = 0.6 * scenario_sim + 0.4 * intent_sim
            
            if similarity > 0:
                similarities.append((other_id, similarity))
        
        # 排序并返回
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [user_id for user_id, _ in similarities[:limit]]


# ==================== 模块级便捷函数 ====================

_default_tracker: Optional[BehaviorTracker] = None


def get_behavior_tracker() -> BehaviorTracker:
    """获取行为跟踪器实例"""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = BehaviorTracker()
    return _default_tracker


def record_behavior(
    user_id: str,
    behavior_type: BehaviorType,
    **kwargs,
) -> None:
    """便捷函数：记录行为"""
    get_behavior_tracker().record(user_id, behavior_type, **kwargs)


def record_query(
    user_id: str,
    query: str,
    intent_type: str = "",
    scenario_id: str = "",
    session_id: str = "",
) -> None:
    """便捷函数：记录查询"""
    get_behavior_tracker().record(
        user_id=user_id,
        behavior_type=BehaviorType.QUERY,
        query=query,
        intent_type=intent_type,
        scenario_id=scenario_id,
        session_id=session_id,
    )


def record_ku_view(user_id: str, ku_id: str, session_id: str = "") -> None:
    """便捷函数：记录 KU 浏览"""
    get_behavior_tracker().record(
        user_id=user_id,
        behavior_type=BehaviorType.VIEW,
        target_type=TargetType.KU,
        target_id=ku_id,
        session_id=session_id,
    )

