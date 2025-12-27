"""
对话摘要服务
长对话自动生成摘要，用于上下文压缩和历史回顾
"""
import os
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from openai import OpenAI

logger = logging.getLogger(__name__)


class SummaryType(str, Enum):
    """摘要类型"""
    INSTANT = "instant"           # 即时摘要（对话中）
    SESSION = "session"           # 会话摘要（会话结束）
    TOPIC = "topic"               # 主题摘要（话题切换）


@dataclass
class ConversationTurn:
    """对话轮次"""
    role: str  # user/assistant
    content: str
    timestamp: float = 0.0
    intent_type: str = ""
    entities: List[str] = field(default_factory=list)


@dataclass
class Summary:
    """摘要结果"""
    summary_type: SummaryType
    text: str = ""  # 添加默认值
    key_points: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.summary_type.value,
            "text": self.text,
            "key_points": self.key_points,
            "entities": self.entities_mentioned,
            "topics": self.topics,
            "turn_count": self.turn_count,
            "created_at": self.created_at,
        }


class SummaryService:
    """摘要服务"""
    
    # 触发摘要的阈值
    INSTANT_TRIGGER_TURNS = 10        # 消息数超过此值触发即时摘要
    INSTANT_TRIGGER_TOKENS = 2000     # token 数超过此值触发即时摘要
    
    def __init__(self, llm_client: OpenAI = None):
        self._client = llm_client
        self._model = os.getenv("DEFAULT_MODEL", "qwen-plus")
        
        # 缓存的摘要
        self._summaries: Dict[str, List[Summary]] = {}
    
    @property
    def client(self) -> OpenAI:
        if self._client is None:
            from ..config import settings
            self._client = OpenAI(
                api_key=settings.upstream_llm_key,
                base_url=settings.upstream_llm_url.replace("/chat/completions", ""),
            )
        return self._client
    
    def should_summarize(
        self,
        turns: List[ConversationTurn],
        last_summary_turn: int = 0,
    ) -> Tuple[bool, SummaryType]:
        """
        判断是否需要生成摘要
        
        Args:
            turns: 对话轮次列表
            last_summary_turn: 上次生成摘要时的轮次数
        
        Returns:
            (是否需要摘要, 摘要类型)
        """
        current_turn = len(turns)
        turns_since_summary = current_turn - last_summary_turn
        
        # 检查轮次数
        if turns_since_summary >= self.INSTANT_TRIGGER_TURNS:
            return True, SummaryType.INSTANT
        
        # 检查 token 数（粗略估计）
        total_chars = sum(len(t.content) for t in turns[last_summary_turn:])
        estimated_tokens = total_chars // 2  # 粗略估计
        
        if estimated_tokens >= self.INSTANT_TRIGGER_TOKENS:
            return True, SummaryType.INSTANT
        
        return False, SummaryType.INSTANT
    
    def generate_summary(
        self,
        turns: List[ConversationTurn],
        summary_type: SummaryType = SummaryType.INSTANT,
        conversation_id: str = None,
    ) -> Summary:
        """
        生成对话摘要
        
        Args:
            turns: 对话轮次列表
            summary_type: 摘要类型
            conversation_id: 对话ID（用于缓存）
        
        Returns:
            Summary
        """
        if not turns:
            return Summary(
                summary_type=summary_type,
                text="无对话内容",
            )
        
        # 构建对话文本
        conversation_text = self._format_turns(turns)
        
        # 根据摘要类型选择 prompt
        prompt = self._get_summary_prompt(summary_type, conversation_text)
        
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            
            result_text = response.choices[0].message.content
            
            # 解析结果
            summary = self._parse_summary_response(result_text, summary_type, len(turns))
            
            # 缓存
            if conversation_id:
                if conversation_id not in self._summaries:
                    self._summaries[conversation_id] = []
                self._summaries[conversation_id].append(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Generate summary failed: {e}")
            return Summary(
                summary_type=summary_type,
                text=f"摘要生成失败: {str(e)}",
                turn_count=len(turns),
            )
    
    def _format_turns(self, turns: List[ConversationTurn]) -> str:
        """格式化对话轮次为文本"""
        lines = []
        for turn in turns:
            role_label = "用户" if turn.role == "user" else "助手"
            lines.append(f"{role_label}: {turn.content}")
        return "\n\n".join(lines)
    
    def _get_summary_prompt(self, summary_type: SummaryType, conversation: str) -> str:
        """获取摘要 prompt"""
        
        if summary_type == SummaryType.INSTANT:
            return f"""请对以下对话生成一个简洁的摘要，用于在后续对话中作为上下文。

对话内容：
{conversation}

要求：
1. 摘要应在100-200字之间
2. 提取关键信息点（最多5个）
3. 列出提到的重要实体（产品、参数、场景等）
4. 保持客观，不要添加新信息

请按以下格式返回：

摘要：[摘要内容]

关键点：
- [要点1]
- [要点2]
...

提及实体：[实体1], [实体2], ...
"""
        
        elif summary_type == SummaryType.SESSION:
            return f"""请对以下完整会话生成总结，用于会话归档。

对话内容：
{conversation}

要求：
1. 总结用户的主要需求和问题
2. 总结提供的解答和建议
3. 标注会话涉及的主题领域
4. 摘要应在200-300字之间

请按以下格式返回：

会话摘要：[摘要内容]

用户需求：
- [需求1]
- [需求2]

解答要点：
- [要点1]
- [要点2]

涉及主题：[主题1], [主题2], ...
"""
        
        else:  # TOPIC
            return f"""请对以下对话中的特定话题生成摘要。

对话内容：
{conversation}

要求：
1. 识别对话中讨论的主要话题
2. 为每个话题提供简要摘要
3. 摘要应简洁明了

请按以下格式返回：

话题摘要：
[话题1]: [摘要]
[话题2]: [摘要]
...
"""
    
    def _parse_summary_response(
        self,
        response: str,
        summary_type: SummaryType,
        turn_count: int,
    ) -> Summary:
        """解析摘要响应"""
        summary = Summary(
            summary_type=summary_type,
            turn_count=turn_count,
        )
        
        lines = response.strip().split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("摘要：") or line.startswith("会话摘要："):
                summary.text = line.split("：", 1)[1].strip()
                current_section = "summary"
            elif line.startswith("关键点：") or line.startswith("解答要点：") or line.startswith("用户需求："):
                current_section = "key_points"
            elif line.startswith("提及实体：") or line.startswith("涉及主题："):
                entities_text = line.split("：", 1)[1].strip()
                summary.entities_mentioned = [e.strip() for e in entities_text.split(",") if e.strip()]
                current_section = None
            elif line.startswith("- ") and current_section == "key_points":
                summary.key_points.append(line[2:].strip())
            elif current_section == "summary" and not summary.text:
                summary.text = line
        
        # 如果没有解析到摘要文本，使用整个响应
        if not summary.text:
            summary.text = response[:500]
        
        return summary
    
    def get_summary_for_context(
        self,
        conversation_id: str,
    ) -> Optional[str]:
        """
        获取用于上下文的摘要
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            摘要文本
        """
        summaries = self._summaries.get(conversation_id, [])
        
        if not summaries:
            return None
        
        # 返回最新的摘要
        latest = summaries[-1]
        
        context_parts = [f"【历史摘要】{latest.text}"]
        
        if latest.key_points:
            context_parts.append("关键点：" + "；".join(latest.key_points[:3]))
        
        if latest.entities_mentioned:
            context_parts.append("相关实体：" + "、".join(latest.entities_mentioned[:5]))
        
        return "\n".join(context_parts)
    
    def compress_history(
        self,
        turns: List[ConversationTurn],
        max_turns: int = 5,
    ) -> Tuple[List[ConversationTurn], Optional[Summary]]:
        """
        压缩对话历史
        
        将超出限制的历史消息生成摘要，保留最近的消息
        
        Args:
            turns: 对话轮次列表
            max_turns: 保留的最大轮次数
        
        Returns:
            (压缩后的轮次, 摘要)
        """
        if len(turns) <= max_turns:
            return turns, None
        
        # 分割历史和最近消息
        to_summarize = turns[:-max_turns]
        to_keep = turns[-max_turns:]
        
        # 生成摘要
        summary = self.generate_summary(to_summarize, SummaryType.INSTANT)
        
        return to_keep, summary
    
    def get_all_summaries(self, conversation_id: str) -> List[Summary]:
        """获取对话的所有摘要"""
        return self._summaries.get(conversation_id, [])
    
    def clear_summaries(self, conversation_id: str) -> None:
        """清除对话的摘要"""
        if conversation_id in self._summaries:
            del self._summaries[conversation_id]


# ==================== 模块级便捷函数 ====================

_default_service: Optional[SummaryService] = None


def get_summary_service(llm_client: OpenAI = None) -> SummaryService:
    """获取摘要服务实例"""
    global _default_service
    if _default_service is None:
        _default_service = SummaryService(llm_client)
    return _default_service


def should_summarize(
    turns: List[ConversationTurn],
    last_summary_turn: int = 0,
) -> Tuple[bool, SummaryType]:
    """便捷函数：判断是否需要摘要"""
    return get_summary_service().should_summarize(turns, last_summary_turn)


def generate_summary(
    turns: List[ConversationTurn],
    summary_type: SummaryType = SummaryType.INSTANT,
    conversation_id: str = None,
) -> Summary:
    """便捷函数：生成摘要"""
    return get_summary_service().generate_summary(turns, summary_type, conversation_id)


def compress_history(
    turns: List[ConversationTurn],
    max_turns: int = 5,
) -> Tuple[List[ConversationTurn], Optional[Summary]]:
    """便捷函数：压缩历史"""
    return get_summary_service().compress_history(turns, max_turns)

