"""Conversation management API endpoints"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from ..db import get_db
from ..services.conversation_service import ConversationService
from ..services.retrieval import search
from ..services.intent_recognizer import recognize_intent, get_intent_recognizer, IntentType
from ..models.user import User
from ..config import settings
from .auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_llm_client = None

def get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            api_key=settings.upstream_llm_key,
            base_url=settings.upstream_llm_url.replace("/chat/completions", ""),
        )
    return _llm_client

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
    model_config = {"protected_namespaces": ()}
    
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
    groups = service.list_conversations_grouped(str(user.id))
    
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
    
    # 调用 RAG 服务获取回答
    try:
        rag_result = await _generate_rag_response(
            query=body.content,
            conversation_id=conversation_id,
            scenario_id=conv.scenario_id
        )
        assistant_content = rag_result["answer"]
        sources = rag_result["sources"]
        model_used = rag_result.get("model", "qwen-max")
    except Exception as e:
        logger.error(f"RAG generation error: {e}")
        assistant_content = f"抱歉，生成回答时遇到问题，请稍后重试。错误信息：{str(e)}"
        sources = []
        model_used = "qwen-max"
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        sources=sources,
        model_used=model_used
    )
    
    return MessageResponse(**assistant_message.to_dict())


async def _generate_rag_response(
    query: str,
    conversation_id: str,
    scenario_id: Optional[str] = None
) -> dict:
    """
    Generate RAG response using retrieval and LLM
    
    Returns:
        dict with keys: answer, sources, model
    """
    # 1. 意图识别
    client = get_llm_client()
    intent_recognizer = get_intent_recognizer(client)
    
    try:
        intent_result = intent_recognizer.recognize(query)
        logger.info(f"Intent recognized: {intent_result.intent_type}")
    except Exception as e:
        logger.warning(f"Intent recognition failed: {e}")
        intent_result = None
    
    # 2. 检索知识
    try:
        hits = search(query, top_k=5, intent_result=intent_result)
        logger.info(f"Retrieved {len(hits)} hits")
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        hits = []
    
    # 3. 构建上下文
    sources = []
    context_parts = []
    
    for hit in hits[:5]:
        title = hit.get("title", "未知标题")
        summary = hit.get("summary", "")
        body = hit.get("body", "")[:1500]
        source_file = hit.get("source_file", "")
        
        context_parts.append(f"【来源: {source_file}】\n标题: {title}\n摘要: {summary}\n详情: {body}")
        
        sources.append({
            "id": hit.get("id"),
            "title": title,
            "type": hit.get("ku_type", "core"),
            "source_file": source_file,
            "score": hit.get("score", 0)
        })
    
    # 4. 构建 Prompt
    if context_parts:
        context = "\n\n---\n\n".join(context_parts)
        system_prompt = f"""你是一个专业的知识助手。请基于以下检索到的知识内容回答用户问题。

{context}

回答要求：
1. 基于上述内容准确回答，不要编造信息
2. 在适当位置引用来源，格式如【来源: xxx】
3. 如果检索内容不足以回答问题，请如实说明
4. 使用专业但易懂的语言"""
    else:
        system_prompt = """你是一个专业的知识助手。当前知识库未找到相关内容。
请告知用户暂无相关资料，并询问是否可以提供更多信息帮助完善知识库。"""
    
    # 5. 调用 LLM 生成回答
    try:
        response = client.chat.completions.create(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.7,
            max_tokens=2048
        )
        answer = response.choices[0].message.content
        model = response.model if hasattr(response, 'model') else "qwen-max"
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        if hits:
            # 回退：直接返回检索结果摘要
            summaries = [f"• {h.get('title', '')}: {h.get('summary', '')[:100]}" for h in hits[:3]]
            answer = f"抱歉，AI 回答生成遇到问题，以下是检索到的相关内容：\n\n" + "\n\n".join(summaries)
        else:
            answer = "抱歉，当前无法生成回答，请稍后重试。"
        model = "fallback"
    
    return {
        "answer": answer,
        "sources": sources,
        "model": model
    }


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

# ==================== Export Endpoint ====================

class ExportResponse(BaseModel):
    content: str
    filename: str


@router.get("/{conversation_id}/export", response_model=ExportResponse)
async def export_conversation(
    conversation_id: str,
    format: str = "markdown",  # markdown or json
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出对话"""
    service = ConversationService(db)
    
    # 验证对话属于用户
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = service.get_messages(conversation_id, limit=1000)
    
    if format == "json":
        import json
        content = json.dumps({
            "conversation": conv.to_dict(),
            "messages": [m.to_dict() for m in messages]
        }, ensure_ascii=False, indent=2)
        filename = f"conversation-{conversation_id}.json"
    else:
        # Markdown format
        lines = [
            f"# {conv.title or '对话导出'}",
            "",
            f"导出时间: {conv.created_at}",
            "",
            "---",
            ""
        ]
        
        for msg in messages:
            role = "**用户**" if msg.role == "user" else "**助手**"
            lines.append(role)
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            
            # Add sources if available
            if msg.sources:
                lines.append("📎 来源：")
                for src in msg.sources:
                    title = src.get("title", "未知") if isinstance(src, dict) else str(src)
                    lines.append(f"- {title}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        content = "\n".join(lines)
        filename = f"conversation-{conversation_id}.md"
    
    return ExportResponse(content=content, filename=filename)


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

