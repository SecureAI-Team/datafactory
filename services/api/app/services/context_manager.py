"""
对话上下文管理器
负责管理对话历史、实体跟踪、偏好记忆
"""
import json
import time
import logging
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """对话状态"""
    ACTIVE = "active"              # 活跃对话
    AWAITING_CLARIFICATION = "awaiting_clarification"  # 等待澄清回复
    COMPLETED = "completed"        # 已完成
    EXPIRED = "expired"           # 已过期


@dataclass
class ExtractedEntity:
    """提取的实体"""
    name: str                     # 实体名称（如"产能"、"公司名"）
    value: Any                    # 实体值
    entity_type: str              # 实体类型（param/preference/reference）
    source_turn: int              # 来源对话轮次
    confidence: float = 1.0       # 置信度


@dataclass
class UserPreference:
    """用户偏好"""
    key: str                      # 偏好键（如"budget"、"tech_level"）
    value: Any                    # 偏好值
    source: str                   # 来源（explicit/inferred）
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationTurn:
    """对话轮次"""
    turn_id: int
    role: str                     # user/assistant
    content: str
    intent_type: Optional[str] = None
    scenario_ids: List[str] = field(default_factory=list)
    entities: List[ExtractedEntity] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationContext:
    """对话上下文"""
    conversation_id: str
    state: ConversationState = ConversationState.ACTIVE
    
    # 对话历史
    turns: List[ConversationTurn] = field(default_factory=list)
    
    # 实体追踪
    entities: Dict[str, ExtractedEntity] = field(default_factory=dict)
    
    # 用户偏好
    preferences: Dict[str, UserPreference] = field(default_factory=dict)
    
    # 场景上下文
    current_scenario: Optional[str] = None
    scenario_history: List[str] = field(default_factory=list)
    
    # 推荐追踪
    recommended_solutions: List[str] = field(default_factory=list)
    user_feedback_on_solutions: Dict[str, str] = field(default_factory=dict)
    
    # 澄清状态
    pending_clarification: Optional[Dict] = None
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def add_turn(
        self,
        role: str,
        content: str,
        intent_type: str = None,
        scenario_ids: List[str] = None,
        entities: List[Dict] = None,
    ):
        """添加对话轮次"""
        turn = ConversationTurn(
            turn_id=len(self.turns),
            role=role,
            content=content,
            intent_type=intent_type,
            scenario_ids=scenario_ids or [],
            entities=[
                ExtractedEntity(**e) if isinstance(e, dict) else e
                for e in (entities or [])
            ],
        )
        self.turns.append(turn)
        self.updated_at = time.time()
        
        # 更新实体
        for entity in turn.entities:
            self.entities[entity.name] = entity
        
        # 更新场景
        if scenario_ids:
            for sid in scenario_ids:
                if sid not in self.scenario_history:
                    self.scenario_history.append(sid)
            self.current_scenario = scenario_ids[0]
    
    def set_preference(self, key: str, value: Any, source: str = "explicit"):
        """设置用户偏好"""
        self.preferences[key] = UserPreference(
            key=key,
            value=value,
            source=source,
        )
        self.updated_at = time.time()
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        pref = self.preferences.get(key)
        return pref.value if pref else default
    
    def get_entity(self, name: str) -> Optional[Any]:
        """获取实体值"""
        entity = self.entities.get(name)
        return entity.value if entity else None
    
    def add_recommendation(self, solution_name: str):
        """添加推荐记录"""
        if solution_name not in self.recommended_solutions:
            self.recommended_solutions.append(solution_name)
        self.updated_at = time.time()
    
    def record_solution_feedback(self, solution_name: str, feedback: str):
        """记录方案反馈"""
        self.user_feedback_on_solutions[solution_name] = feedback
        self.updated_at = time.time()
    
    def get_compressed_history(self, max_turns: int = 5) -> List[Dict]:
        """获取压缩的对话历史"""
        if len(self.turns) <= max_turns:
            return [
                {"role": t.role, "content": t.content}
                for t in self.turns
            ]
        
        # 压缩策略：保留摘要 + 最近轮次
        summary = self._generate_history_summary()
        recent = self.turns[-max_turns:]
        
        result = [{"role": "system", "content": f"【对话摘要】\n{summary}"}]
        result.extend([
            {"role": t.role, "content": t.content}
            for t in recent
        ])
        
        return result
    
    def _generate_history_summary(self) -> str:
        """生成历史摘要"""
        # 提取关键信息
        topics = []
        for turn in self.turns[:-5]:  # 排除最近5轮
            if turn.role == "user" and turn.intent_type:
                topics.append(f"- {turn.intent_type}: {turn.content[:50]}...")
        
        if not topics:
            return "用户进行了多轮咨询。"
        
        return "\n".join(topics[:5])
    
    def build_context_prompt(self) -> str:
        """构建上下文注入 Prompt"""
        parts = []
        
        # 用户信息
        if self.preferences:
            pref_lines = []
            pref_mappings = {
                "enterprise_scale": "企业规模",
                "budget_range": "预算范围",
                "tech_capability": "技术水平",
                "aoi_product_type": "检测产品",
                "aoi_defect_type": "关注缺陷",
            }
            for key, pref in self.preferences.items():
                label = pref_mappings.get(key, key)
                pref_lines.append(f"- {label}: {pref.value}")
            
            if pref_lines:
                parts.append("【用户信息】\n" + "\n".join(pref_lines))
        
        # 已识别实体
        if self.entities:
            entity_lines = []
            for name, entity in list(self.entities.items())[:10]:
                entity_lines.append(f"- {name}: {entity.value}")
            
            if entity_lines:
                parts.append("【已知参数】\n" + "\n".join(entity_lines))
        
        # 已推荐方案
        if self.recommended_solutions:
            solutions_str = ", ".join(self.recommended_solutions[-3:])
            parts.append(f"【已推荐方案】\n{solutions_str}")
            
            # 反馈
            if self.user_feedback_on_solutions:
                feedback_lines = [
                    f"- {sol}: {fb}"
                    for sol, fb in list(self.user_feedback_on_solutions.items())[-3:]
                ]
                parts.append("【用户反馈】\n" + "\n".join(feedback_lines))
        
        # 当前场景
        if self.current_scenario:
            parts.append(f"【当前场景】\n{self.current_scenario}")
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """检查是否过期"""
        elapsed = time.time() - self.updated_at
        return elapsed > timeout_minutes * 60
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "conversation_id": self.conversation_id,
            "state": self.state.value,
            "turns": [
                {
                    "turn_id": t.turn_id,
                    "role": t.role,
                    "content": t.content,
                    "intent_type": t.intent_type,
                    "scenario_ids": t.scenario_ids,
                    "timestamp": t.timestamp,
                }
                for t in self.turns
            ],
            "entities": {
                k: {"name": v.name, "value": v.value, "type": v.entity_type}
                for k, v in self.entities.items()
            },
            "preferences": {
                k: {"key": v.key, "value": v.value, "source": v.source}
                for k, v in self.preferences.items()
            },
            "current_scenario": self.current_scenario,
            "recommended_solutions": self.recommended_solutions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ContextManager:
    """上下文管理器"""
    
    def __init__(self, storage_backend: str = "memory"):
        """
        Args:
            storage_backend: 存储后端 ("memory" 或 "redis")
        """
        self.storage_backend = storage_backend
        self._memory_store: Dict[str, ConversationContext] = {}
        self._redis_client = None
        
        if storage_backend == "redis":
            self._init_redis()
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import redis
            self._redis_client = redis.Redis(
                host="redis",
                port=6379,
                decode_responses=True,
            )
            self._redis_client.ping()
            logger.info("Redis connection established for context storage")
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to memory: {e}")
            self.storage_backend = "memory"
    
    def get_or_create(self, conversation_id: str) -> ConversationContext:
        """获取或创建对话上下文"""
        context = self.get(conversation_id)
        
        if context is None:
            context = ConversationContext(conversation_id=conversation_id)
            self.save(context)
        
        return context
    
    def get(self, conversation_id: str) -> Optional[ConversationContext]:
        """获取对话上下文"""
        if self.storage_backend == "memory":
            return self._memory_store.get(conversation_id)
        elif self.storage_backend == "redis" and self._redis_client:
            data = self._redis_client.get(f"conv:{conversation_id}")
            if data:
                return self._deserialize_context(json.loads(data))
        return None
    
    def save(self, context: ConversationContext):
        """保存对话上下文"""
        context.updated_at = time.time()
        
        if self.storage_backend == "memory":
            self._memory_store[context.conversation_id] = context
        elif self.storage_backend == "redis" and self._redis_client:
            data = json.dumps(context.to_dict())
            self._redis_client.setex(
                f"conv:{context.conversation_id}",
                timedelta(hours=2),
                data,
            )
    
    def delete(self, conversation_id: str):
        """删除对话上下文"""
        if self.storage_backend == "memory":
            self._memory_store.pop(conversation_id, None)
        elif self.storage_backend == "redis" and self._redis_client:
            self._redis_client.delete(f"conv:{conversation_id}")
    
    def cleanup_expired(self, timeout_minutes: int = 30):
        """清理过期上下文"""
        if self.storage_backend == "memory":
            expired = [
                cid for cid, ctx in self._memory_store.items()
                if ctx.is_expired(timeout_minutes)
            ]
            for cid in expired:
                del self._memory_store[cid]
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired contexts")
    
    def _deserialize_context(self, data: Dict) -> ConversationContext:
        """反序列化上下文"""
        context = ConversationContext(
            conversation_id=data["conversation_id"],
            state=ConversationState(data.get("state", "active")),
            current_scenario=data.get("current_scenario"),
            recommended_solutions=data.get("recommended_solutions", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
        
        # 恢复轮次
        for t in data.get("turns", []):
            turn = ConversationTurn(
                turn_id=t["turn_id"],
                role=t["role"],
                content=t["content"],
                intent_type=t.get("intent_type"),
                scenario_ids=t.get("scenario_ids", []),
                timestamp=t.get("timestamp", time.time()),
            )
            context.turns.append(turn)
        
        # 恢复实体
        for k, v in data.get("entities", {}).items():
            context.entities[k] = ExtractedEntity(
                name=v["name"],
                value=v["value"],
                entity_type=v.get("type", "param"),
                source_turn=0,
            )
        
        # 恢复偏好
        for k, v in data.get("preferences", {}).items():
            context.preferences[k] = UserPreference(
                key=v["key"],
                value=v["value"],
                source=v.get("source", "explicit"),
            )
        
        return context
    
    def extract_entities_from_text(
        self,
        text: str,
        turn_id: int = 0,
    ) -> List[ExtractedEntity]:
        """从文本中提取实体"""
        import re
        entities = []
        
        # 功率
        power_match = re.search(r"(\d+(?:\.\d+)?)\s*[wW瓦]", text)
        if power_match:
            entities.append(ExtractedEntity(
                name="功率",
                value=float(power_match.group(1)),
                entity_type="param",
                source_turn=turn_id,
            ))
        
        # 精度
        precision_match = re.search(r"(\d+(?:\.\d+)?)\s*(mm|毫米|um|微米|μm)", text)
        if precision_match:
            value = float(precision_match.group(1))
            unit = precision_match.group(2)
            if unit in ("um", "微米", "μm"):
                value = value / 1000
            entities.append(ExtractedEntity(
                name="精度",
                value=value,
                entity_type="param",
                source_turn=turn_id,
            ))
        
        # 产能
        capacity_match = re.search(r"(\d+)\s*(片|件|个)/\s*(小时|h|分钟|min)", text)
        if capacity_match:
            value = int(capacity_match.group(1))
            time_unit = capacity_match.group(3)
            if time_unit in ("分钟", "min"):
                value = value * 60  # 转换为每小时
            entities.append(ExtractedEntity(
                name="产能",
                value=value,
                entity_type="param",
                source_turn=turn_id,
            ))
        
        # 价格
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
        if price_match:
            entities.append(ExtractedEntity(
                name="预算",
                value=float(price_match.group(1)) * 10000,
                entity_type="param",
                source_turn=turn_id,
            ))
        
        # 企业规模（从澄清回复中提取）
        if "小型" in text or "100人以下" in text:
            entities.append(ExtractedEntity(
                name="企业规模",
                value="small",
                entity_type="preference",
                source_turn=turn_id,
            ))
        elif "中型" in text or "几百人" in text:
            entities.append(ExtractedEntity(
                name="企业规模",
                value="medium",
                entity_type="preference",
                source_turn=turn_id,
            ))
        elif "大型" in text or "千人" in text:
            entities.append(ExtractedEntity(
                name="企业规模",
                value="large",
                entity_type="preference",
                source_turn=turn_id,
            ))
        
        return entities


# ==================== 模块级便捷函数 ====================

_default_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取上下文管理器实例"""
    global _default_manager
    if _default_manager is None:
        # 尝试使用 Redis，失败则回退到内存
        _default_manager = ContextManager(storage_backend="redis")
    return _default_manager


def get_or_create_context(conversation_id: str) -> ConversationContext:
    """便捷函数：获取或创建上下文"""
    return get_context_manager().get_or_create(conversation_id)


def save_context(context: ConversationContext):
    """便捷函数：保存上下文"""
    get_context_manager().save(context)

