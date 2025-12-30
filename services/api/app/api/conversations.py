"""Conversation management API endpoints"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.conversation_service import ConversationService
from ..models.user import User
from .auth import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ==================== Request/Response Models ====================

class CreateConversationRequest(BaseModel):
    title: Optional[str] = None
    scenario_id: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    scenario_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str


class FeedbackRequest(BaseModel):
    feedback: str  # positive/negative
    feedback_text: Optional[str] = None


class CreateShareRequest(BaseModel):
    allow_copy: bool = True
    expires_in_days: Optional[int] = None


class ConversationResponse(BaseModel):
    id: int
    conversation_id: str
    title: Optional[str]
    summary: Optional[str]
    status: str
    is_pinned: bool
    message_count: int
    last_message_at: Optional[str]
    tags: List
    scenario_id: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class MessageResponse(BaseModel):
    id: int
    message_id: str
    role: str
    content: str
    sources: List
    feedback: Optional[str]
    tokens_used: Optional[int]
    model_used: Optional[str]
    latency_ms: Optional[int]
    created_at: Optional[str]


class ConversationListResponse(BaseModel):
    pinned: List[ConversationResponse]
    today: List[ConversationResponse]
    yesterday: List[ConversationResponse]
    this_week: List[ConversationResponse]
    earlier: List[ConversationResponse]


# ==================== API Endpoints ====================

@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的对话列表（分组）"""
    service = ConversationService(db)
    groups = service.list_conversations_grouped(user.id)
    
    return ConversationListResponse(
        pinned=[ConversationResponse(**c.to_dict()) for c in groups["pinned"]],
        today=[ConversationResponse(**c.to_dict()) for c in groups["today"]],
        yesterday=[ConversationResponse(**c.to_dict()) for c in groups["yesterday"]],
        this_week=[ConversationResponse(**c.to_dict()) for c in groups["this_week"]],
        earlier=[ConversationResponse(**c.to_dict()) for c in groups["earlier"]]
    )


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    body: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新对话"""
    service = ConversationService(db)
    conv = service.create_conversation(
        user_id=str(user.id),
        title=body.title,
        scenario_id=body.scenario_id
    )
    return ConversationResponse(**conv.to_dict())


@router.get("/search")
async def search_conversations(
    q: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """搜索历史对话"""
    service = ConversationService(db)
    results = service.search_conversations(str(user.id), q)
    return {"results": [c.to_dict() for c in results]}


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话详情"""
    service = ConversationService(db)
    conv = service.get_conversation(conversation_id, str(user.id))
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse(**conv.to_dict())


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新对话"""
    service = ConversationService(db)
    conv = service.update_conversation(
        conversation_id,
        str(user.id),
        title=body.title,
        tags=body.tags,
        scenario_id=body.scenario_id
    )
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse(**conv.to_dict())


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除对话"""
    service = ConversationService(db)
    success = service.delete_conversation(conversation_id, str(user.id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return {"message": "Conversation deleted"}


@router.post("/{conversation_id}/archive", response_model=ConversationResponse)
async def archive_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """归档对话"""
    service = ConversationService(db)
    conv = service.archive_conversation(conversation_id, str(user.id))
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse(**conv.to_dict())


@router.post("/{conversation_id}/pin", response_model=ConversationResponse)
async def pin_conversation(
    conversation_id: str,
    pinned: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """置顶/取消置顶"""
    service = ConversationService(db)
    conv = service.pin_conversation(conversation_id, str(user.id), pinned)
    
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse(**conv.to_dict())


# ==================== Message Endpoints ====================

@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话消息列表"""
    service = ConversationService(db)
    
    # 验证用户有权限访问该对话
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = service.get_messages(conversation_id, limit, offset)
    return {"messages": [m.to_dict() for m in messages]}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发送消息（触发 RAG 回答）"""
    service = ConversationService(db)
    
    # 验证对话存在
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # 保存用户消息
    user_message = service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=body.content
    )
    
    # TODO: 调用 RAG 服务获取回答
    # 这里暂时返回一个占位回答，实际实现需要调用现有的 gateway API
    assistant_content = f"收到您的问题：{body.content[:50]}...（RAG 回答待集成）"
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        sources=[],
        model_used="qwen-max"
    )
    
    return MessageResponse(**assistant_message.to_dict())


@router.put("/{conversation_id}/messages/{message_id}/feedback")
async def update_feedback(
    conversation_id: str,
    message_id: str,
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新消息反馈"""
    service = ConversationService(db)
    
    # 验证对话属于用户
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    message = service.update_message_feedback(message_id, body.feedback, body.feedback_text)
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return {"message": "Feedback updated"}


# ==================== Share Endpoints ====================

@router.post("/{conversation_id}/share")
async def create_share(
    conversation_id: str,
    body: CreateShareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建分享链接"""
    service = ConversationService(db)
    
    # 验证对话属于用户
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    share = service.create_share(
        conversation_id=conversation_id,
        user_id=user.id,
        allow_copy=body.allow_copy,
        expires_in_days=body.expires_in_days
    )
    
    return {
        "share_token": share.share_token,
        "share_url": f"/share/{share.share_token}",
        "expires_at": share.expires_at.isoformat() if share.expires_at else None
    }


@router.delete("/{conversation_id}/share")
async def delete_share(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消分享"""
    service = ConversationService(db)
    success = service.delete_share(conversation_id, user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )
    
    return {"message": "Share deleted"}


# ==================== Public Share Access ====================

@router.get("/share/{token}")
async def get_shared_conversation(
    token: str,
    db: Session = Depends(get_db)
):
    """获取分享的对话（公开访问）"""
    service = ConversationService(db)
    result = service.get_shared_conversation(token)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found or expired"
        )
    
    return result

