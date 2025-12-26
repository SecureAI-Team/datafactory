"""
多轮对话状态管理
支持会话历史、意图识别、澄清问卷
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel


class ConversationState(str, Enum):
    """对话状态"""
    INITIAL = "initial"              # 初始状态
    NEEDS_CLARIFICATION = "needs_clarification"  # 需要澄清
    ANSWERING = "answering"          # 正在回答
    AWAITING_FEEDBACK = "awaiting_feedback"  # 等待反馈
    COMPLETED = "completed"          # 完成


class ClarificationOption(BaseModel):
    """澄清选项"""
    id: str
    text: str
    description: Optional[str] = None


class ClarificationQuestion(BaseModel):
    """澄清问题"""
    question: str
    options: List[ClarificationOption]
    allow_multiple: bool = False
    allow_free_text: bool = True


class ConversationTurn(BaseModel):
    """对话轮次"""
    role: str  # user / assistant / system
    content: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = {}
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class Conversation(BaseModel):
    """完整对话会话"""
    id: str
    user_id: Optional[str] = None
    state: ConversationState = ConversationState.INITIAL
    turns: List[ConversationTurn] = []
    context: Dict[str, Any] = {}  # 收集的上下文信息
    clarifications: List[ClarificationQuestion] = []  # 待回答的澄清问题
    created_at: datetime = None
    updated_at: datetime = None
    
    def __init__(self, **data):
        if data.get('id') is None:
            data['id'] = str(uuid.uuid4())
        if data.get('created_at') is None:
            data['created_at'] = datetime.utcnow()
        if data.get('updated_at') is None:
            data['updated_at'] = datetime.utcnow()
        super().__init__(**data)
    
    def add_turn(self, role: str, content: str, metadata: Dict = None):
        """添加对话轮次"""
        self.turns.append(ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {}
        ))
        self.updated_at = datetime.utcnow()
    
    def get_history_for_llm(self, max_turns: int = 10) -> List[Dict]:
        """获取用于 LLM 的历史记录"""
        recent_turns = self.turns[-max_turns:] if len(self.turns) > max_turns else self.turns
        return [{"role": t.role, "content": t.content} for t in recent_turns if t.role in ("user", "assistant")]
    
    def get_context_summary(self) -> str:
        """获取上下文摘要"""
        if not self.context:
            return ""
        parts = []
        for key, value in self.context.items():
            if isinstance(value, list):
                parts.append(f"{key}: {', '.join(value)}")
            else:
                parts.append(f"{key}: {value}")
        return "用户上下文：" + "; ".join(parts)


# 简单的内存存储（生产环境应使用 Redis）
_conversations: Dict[str, Conversation] = {}


def get_or_create_conversation(conversation_id: Optional[str] = None, user_id: Optional[str] = None) -> Conversation:
    """获取或创建会话"""
    if conversation_id and conversation_id in _conversations:
        return _conversations[conversation_id]
    
    conv = Conversation(user_id=user_id)
    _conversations[conv.id] = conv
    return conv


def save_conversation(conv: Conversation):
    """保存会话"""
    conv.updated_at = datetime.utcnow()
    _conversations[conv.id] = conv


def cleanup_old_conversations(max_age_hours: int = 24):
    """清理过期会话"""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    expired = [k for k, v in _conversations.items() if v.updated_at < cutoff]
    for k in expired:
        del _conversations[k]


# 意图识别和澄清问题生成的 Prompt 模板
CLARIFICATION_SYSTEM_PROMPT = """你是一个智能对话助手，负责分析用户问题是否需要澄清。

分析用户问题，判断是否需要进一步了解以下信息来给出更好的回答：
1. 问题的具体场景或背景
2. 用户的技术水平或角色
3. 期望的答案深度或格式
4. 特定的约束条件

如果问题足够清晰，返回 {"needs_clarification": false}

如果需要澄清，返回格式如下的 JSON：
{
  "needs_clarification": true,
  "clarifications": [
    {
      "question": "您希望了解哪个层面的内容？",
      "options": [
        {"id": "basic", "text": "基础概念", "description": "适合入门了解"},
        {"id": "practical", "text": "实践应用", "description": "具体实现方法"},
        {"id": "advanced", "text": "深入原理", "description": "底层机制分析"}
      ],
      "allow_multiple": false,
      "allow_free_text": true
    }
  ]
}

注意：
- 最多生成 2 个澄清问题
- 每个问题最多 4 个选项
- 选项要简洁明了
- 如果是简单的问候或闲聊，不需要澄清"""

