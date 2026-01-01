"""Conversation management API endpoints - 统一意图路由架构"""
import logging
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from openai import OpenAI

from ..db import get_db
from ..services.conversation_service import ConversationService
from ..services.retrieval import search
from ..services.intent_recognizer import (
    recognize_intent, get_intent_recognizer, IntentType, ActionType
)
from ..services.dynamic_interaction import (
    get_dynamic_interaction_service, DynamicQuestion, QuestionType
)
from ..models.user import User
from ..models.config import InteractionFlow, InteractionSession
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


class InteractionTriggerInfo(BaseModel):
    """交互流程触发信息（兼容旧版）"""
    flow_id: str
    flow_name: str
    description: Optional[str] = None
    confidence: float
    reason: str


class DynamicInteractionQuestion(BaseModel):
    """动态生成的问题"""
    field_id: str
    question: str
    question_type: str  # single/multi/input/confirm
    options: Optional[List[dict]] = None
    placeholder: Optional[str] = None


class DynamicInteractionInfo(BaseModel):
    """动态交互信息"""
    session_id: str
    is_dynamic: bool = True
    question: Optional[DynamicInteractionQuestion] = None
    progress: Optional[dict] = None


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
    # 交互流程触发信息（兼容旧版）
    interaction_trigger: Optional[InteractionTriggerInfo] = None
    # 动态交互信息（新版）
    interaction: Optional[DynamicInteractionInfo] = None


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
    """
    发送消息 - 统一意图路由架构
    
    路由流程：
    1. 意图识别 → 分析用户意图和上下文充分性
    2. 路由决策 → 根据意图类型和上下文决定执行路径
    3. 执行 → 直接RAG/动态收集信息/计算/对比
    """
    service = ConversationService(db)
    client = get_llm_client()
    
    # 验证对话存在
    conv = service.get_conversation(conversation_id, str(user.id))
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # 检查是否有活跃的交互会话需要继续
    active_session = db.query(InteractionSession).filter(
        InteractionSession.conversation_id == conversation_id,
        InteractionSession.user_id == user.id,
        InteractionSession.status == 'active'
    ).first()
    
    if active_session:
        # 继续交互会话
        return await _handle_interaction_answer(
            db, service, client, conversation_id, user, body.content, active_session
        )
    
    # 保存用户消息
    user_message = service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=body.content
    )
    
    # ==================== 统一意图路由 ====================
    try:
        # Step 1: 意图识别（包含上下文充分性分析）
        intent_recognizer = get_intent_recognizer(client)
        history = [m.to_dict() for m in service.get_messages(conversation_id, limit=5)]
        
        intent_result = intent_recognizer.recognize(
            query=body.content,
            history=history,
            context={"scenario_id": conv.scenario_id}
        )
        
        logger.info(
            f"Unified routing: intent={intent_result.intent_type.value}, "
            f"action={intent_result.recommended_action.value}, "
            f"sufficient={intent_result.context_sufficiency.is_sufficient if intent_result.context_sufficiency else 'N/A'}"
        )
        
        # Step 2: 根据推荐动作路由
        action = intent_result.recommended_action
        
        if action == ActionType.NEED_INFO:
            # 需要收集更多信息 → 启动动态交互
            return await _start_dynamic_interaction(
                db, service, client, conversation_id, user, 
                body.content, intent_result
            )
        
        elif action == ActionType.CALCULATE:
            # 计算类 → 检查参数后执行计算或收集信息
            return await _handle_calculation(
                db, service, client, conversation_id, user,
                body.content, intent_result
            )
        
        elif action == ActionType.COMPARE:
            # 对比类 → 执行对比
            return await _handle_comparison(
                db, service, client, conversation_id, user,
                body.content, intent_result
            )
        
        else:
            # DIRECT_RAG → 直接检索回答
            optimized_query = body.content
            user_context = {}
            
            if intent_result.context_sufficiency:
                optimized_query = intent_result.context_sufficiency.optimized_query or body.content
                user_context = intent_result.context_sufficiency.extracted_context or {}
            
            rag_result = await _generate_rag_response(
                query=optimized_query,
                conversation_id=conversation_id,
                scenario_id=conv.scenario_id,
                db=db,
                user_context=user_context,
                intent_result=intent_result
            )
            
            assistant_message = service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=rag_result["answer"],
                sources=rag_result["sources"],
                model_used=rag_result.get("model", "qwen-max")
            )
            
            return MessageResponse(**assistant_message.to_dict())
            
    except Exception as e:
        logger.error(f"Unified routing error: {e}", exc_info=True)
        # 回退到基本 RAG
        try:
            rag_result = await _generate_rag_response(
                query=body.content,
                conversation_id=conversation_id,
                scenario_id=conv.scenario_id,
                db=db
            )
            assistant_content = rag_result["answer"]
            sources = rag_result["sources"]
            model_used = rag_result.get("model", "qwen-max")
        except Exception as e2:
            logger.error(f"Fallback RAG also failed: {e2}")
            assistant_content = f"抱歉，生成回答时遇到问题，请稍后重试。"
            sources = []
            model_used = "fallback"
        
        assistant_message = service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            sources=sources,
            model_used=model_used
        )
        
        return MessageResponse(**assistant_message.to_dict())


# ==================== 动态交互处理函数 ====================

async def _start_dynamic_interaction(
    db: Session,
    service: ConversationService,
    client: OpenAI,
    conversation_id: str,
    user: User,
    query: str,
    intent_result
) -> MessageResponse:
    """启动动态交互流程 - LLM 动态生成问题"""
    
    # 创建动态交互会话
    session_id = f"dyn_{uuid.uuid4().hex[:12]}"
    session = InteractionSession(
        session_id=session_id,
        conversation_id=conversation_id,
        flow_id=None,  # 动态模式不绑定静态流程
        user_id=user.id,
        is_dynamic=True,
        original_query=query,
        intent_context={
            "intent_type": intent_result.intent_type.value,
            "entities": intent_result.entities,
            "scenario_ids": intent_result.scenario_ids,
            "missing_fields": intent_result.context_sufficiency.missing_fields if intent_result.context_sufficiency else []
        },
        collected_answers={},
        questions_asked=[]
    )
    db.add(session)
    db.commit()
    
    # 使用动态交互服务生成第一个问题
    interaction_service = get_dynamic_interaction_service(client)
    analysis = interaction_service.analyze_and_generate_question(
        intent_result=intent_result,
        collected_answers={},
        original_query=query
    )
    
    if analysis.can_proceed:
        # 不需要收集信息，直接执行
        db.delete(session)
        db.commit()
        
        rag_result = await _generate_rag_response(
            query=analysis.optimized_query or query,
            conversation_id=conversation_id,
            scenario_id=None,
            db=db,
            user_context=analysis.collected_context
        )
        
        assistant_message = service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=rag_result["answer"],
            sources=rag_result["sources"],
            model_used=rag_result.get("model", "qwen-max")
        )
        
        return MessageResponse(**assistant_message.to_dict())
    
    # 需要收集信息，返回问题
    if analysis.next_question:
        # 记录问题
        question_dict = {
            "field_id": analysis.next_question.field_id,
            "question": analysis.next_question.question,
            "question_type": analysis.next_question.question_type.value,
            "options": [{"id": o.id, "label": o.label} for o in analysis.next_question.options],
            "placeholder": analysis.next_question.placeholder
        }
        session.questions_asked = [question_dict]
        flag_modified(session, "questions_asked")
        db.commit()
        
        # 构建回复消息
        assistant_content = _format_question_message(analysis.next_question)
        
        assistant_message = service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            sources=[],
            model_used="dynamic_interaction"
        )
        
        response_dict = assistant_message.to_dict()
        response_dict["interaction"] = {
            "session_id": session_id,
            "is_dynamic": True,
            "question": question_dict,
            "progress": {"answered": 0, "total": len(analysis.missing_fields) or 1}
        }
        
        return MessageResponse(**response_dict)
    
    # 没有问题生成，回退到 RAG
    db.delete(session)
    db.commit()
    
    rag_result = await _generate_rag_response(
        query=query,
        conversation_id=conversation_id,
        scenario_id=None,
        db=db
    )
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=rag_result["answer"],
        sources=rag_result["sources"],
        model_used=rag_result.get("model", "qwen-max")
    )
    
    return MessageResponse(**assistant_message.to_dict())


async def _handle_interaction_answer(
    db: Session,
    service: ConversationService,
    client: OpenAI,
    conversation_id: str,
    user: User,
    answer: str,
    session: InteractionSession
) -> MessageResponse:
    """处理动态交互中的用户回答"""
    
    # 保存用户回答消息
    user_message = service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=answer
    )
    
    # 获取最后一个问题
    questions_asked = session.questions_asked or []
    if questions_asked:
        last_question = questions_asked[-1]
        field_id = last_question.get("field_id", f"answer_{len(questions_asked)}")
        
        # 保存答案
        answers = dict(session.collected_answers or {})
        answers[field_id] = answer
        session.collected_answers = answers
        session.current_step = len(answers)
        flag_modified(session, "collected_answers")
    
    # 重新分析是否需要更多信息
    intent_recognizer = get_intent_recognizer(client)
    
    # 构建增强的上下文
    enhanced_context = session.intent_context or {}
    enhanced_context["collected_answers"] = session.collected_answers
    
    # 重新识别意图（包含已收集的信息）
    from ..services.intent_recognizer import IntentResult as IR
    intent_result = IR(
        intent_type=IntentType(enhanced_context.get("intent_type", "general")),
        confidence=0.8,
        entities=enhanced_context.get("entities", {}),
        scenario_ids=enhanced_context.get("scenario_ids", [])
    )
    
    # 使用动态交互服务分析
    interaction_service = get_dynamic_interaction_service(client)
    analysis = interaction_service.analyze_and_generate_question(
        intent_result=intent_result,
        collected_answers=session.collected_answers,
        original_query=session.original_query or "",
        history=[m.to_dict() for m in service.get_messages(conversation_id, limit=5)]
    )
    
    if analysis.can_proceed:
        # 信息收集完成，执行操作
        session.status = 'completed'
        session.optimized_query = analysis.optimized_query
        db.commit()
        
        # 根据意图类型执行不同操作
        intent_type_str = enhanced_context.get("intent_type", "general")
        
        if intent_type_str == "calculation":
            # 执行计算
            result_content = await _execute_calculation(
                client, session.collected_answers, session.original_query
            )
        else:
            # 执行 RAG 检索
            rag_result = await _generate_rag_response(
                query=analysis.optimized_query or session.original_query,
                conversation_id=conversation_id,
                scenario_id=None,
                db=db,
                user_context={**analysis.collected_context, **session.collected_answers}
            )
            result_content = rag_result["answer"]
        
        # 添加收集信息摘要
        info_summary = interaction_service.format_collected_info_for_display(
            session.collected_answers,
            [DynamicQuestion(
                field_id=q.get("field_id", ""),
                question=q.get("question", ""),
                question_type=QuestionType(q.get("question_type", "single")),
                options=[]
            ) for q in questions_asked]
        )
        
        if info_summary:
            result_content = f"{info_summary}\n\n---\n\n{result_content}"
        
        assistant_message = service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result_content,
            sources=[],
            model_used="dynamic_interaction"
        )
        
        return MessageResponse(**assistant_message.to_dict())
    
    # 需要继续收集信息
    if analysis.next_question:
        # 记录新问题
        question_dict = {
            "field_id": analysis.next_question.field_id,
            "question": analysis.next_question.question,
            "question_type": analysis.next_question.question_type.value,
            "options": [{"id": o.id, "label": o.label} for o in analysis.next_question.options],
            "placeholder": analysis.next_question.placeholder
        }
        questions_asked.append(question_dict)
        session.questions_asked = questions_asked
        flag_modified(session, "questions_asked")
        db.commit()
        
        assistant_content = _format_question_message(analysis.next_question)
        
        assistant_message = service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            sources=[],
            model_used="dynamic_interaction"
        )
        
        response_dict = assistant_message.to_dict()
        response_dict["interaction"] = {
            "session_id": session.session_id,
            "is_dynamic": True,
            "question": question_dict,
            "progress": {
                "answered": len(session.collected_answers or {}),
                "total": len(analysis.missing_fields) + len(session.collected_answers or {}) or 1
            }
        }
        
        return MessageResponse(**response_dict)
    
    # 没有更多问题，完成会话
    session.status = 'completed'
    db.commit()
    
    rag_result = await _generate_rag_response(
        query=session.original_query or answer,
        conversation_id=conversation_id,
        scenario_id=None,
        db=db,
        user_context=session.collected_answers
    )
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=rag_result["answer"],
        sources=rag_result["sources"],
        model_used=rag_result.get("model", "qwen-max")
    )
    
    return MessageResponse(**assistant_message.to_dict())


def _format_question_message(question: DynamicQuestion) -> str:
    """格式化问题消息"""
    message = question.question
    
    if question.question_type == QuestionType.SINGLE and question.options:
        options_text = "\n".join([f"  • {opt.label}" for opt in question.options])
        message += f"\n\n{options_text}"
    elif question.question_type == QuestionType.MULTI and question.options:
        options_text = "\n".join([f"  ☐ {opt.label}" for opt in question.options])
        message += f"\n\n（可多选）\n{options_text}"
    elif question.question_type == QuestionType.INPUT and question.placeholder:
        message += f"\n\n（请输入，如：{question.placeholder}）"
    
    return message


async def _handle_calculation(
    db: Session,
    service: ConversationService,
    client: OpenAI,
    conversation_id: str,
    user: User,
    query: str,
    intent_result
) -> MessageResponse:
    """处理计算类意图"""
    entities = intent_result.entities
    
    # 检查是否有足够的参数
    has_capacity = "capacity" in entities
    has_power = "power" in entities
    has_count = "device_count" in entities
    
    if not (has_capacity or has_power or has_count):
        # 参数不足，启动动态交互
        return await _start_dynamic_interaction(
            db, service, client, conversation_id, user, query, intent_result
        )
    
    # 执行计算
    result_content = await _execute_calculation(client, entities, query)
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=result_content,
        sources=[],
        model_used="calculation"
    )
    
    return MessageResponse(**assistant_message.to_dict())


async def _execute_calculation(
    client: OpenAI,
    params: dict,
    query: str
) -> str:
    """执行计算"""
    prompt = f"""基于以下参数进行计算：

用户问题：{query}
参数：{params}

请进行相关计算（如设备数量、产能、ROI等），并给出详细的计算过程和结果。
使用表格展示关键数据。"""

    try:
        response = client.chat.completions.create(
            model="qwen-max",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Calculation failed: {e}")
        return f"计算过程中遇到问题：{str(e)}"


async def _handle_comparison(
    db: Session,
    service: ConversationService,
    client: OpenAI,
    conversation_id: str,
    user: User,
    query: str,
    intent_result
) -> MessageResponse:
    """处理对比类意图"""
    # 对比类直接使用 RAG，但提示使用表格格式
    optimized_query = query
    if intent_result.context_sufficiency:
        optimized_query = intent_result.context_sufficiency.optimized_query or query
    
    rag_result = await _generate_rag_response(
        query=optimized_query,
        conversation_id=conversation_id,
        scenario_id=None,
        db=db,
        user_context=intent_result.context_sufficiency.extracted_context if intent_result.context_sufficiency else {},
        intent_result=intent_result,
        force_table_format=True
    )
    
    assistant_message = service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=rag_result["answer"],
        sources=rag_result["sources"],
        model_used=rag_result.get("model", "qwen-max")
    )
    
    return MessageResponse(**assistant_message.to_dict())


async def _generate_rag_response(
    query: str,
    conversation_id: str,
    scenario_id: Optional[str] = None,
    db: Session = None,
    user_context: dict = None,
    intent_result = None,
    force_table_format: bool = False
) -> dict:
    """
    Generate RAG response using retrieval and LLM
    
    Args:
        query: 用户查询（可能是 LLM 优化后的）
        conversation_id: 对话 ID
        scenario_id: 场景 ID
        db: 数据库会话
        user_context: 用户意图上下文（LLM 提取的主题、关键词等）
        intent_result: 预计算的意图识别结果（可选，避免重复计算）
        force_table_format: 强制使用表格格式（对比类）
    
    Returns:
        dict with keys: answer, sources, model
    """
    user_context = user_context or {}
    
    # 1. 意图识别（如果没有预计算）
    client = get_llm_client()
    
    if intent_result is None:
        intent_recognizer = get_intent_recognizer(client)
        try:
            intent_result = intent_recognizer.recognize(query)
            logger.info(f"Intent recognized: {intent_result.intent_type}")
        except Exception as e:
            logger.warning(f"Intent recognition failed: {e}")
            intent_result = None
    
    # 2. 增强检索查询 - 结合用户上下文
    enhanced_query = query
    if user_context:
        topic = user_context.get("topic", "")
        keywords = user_context.get("keywords", [])
        product = user_context.get("product", "")
        
        # 如果有提取的主题/关键词，添加到查询中以提高检索精度
        context_terms = [topic] if topic else []
        if isinstance(keywords, list):
            context_terms.extend(keywords)
        if product:
            context_terms.append(product)
        
        if context_terms:
            # 将上下文关键词加入查询，避免重复
            unique_terms = [t for t in context_terms if t and t.lower() not in query.lower()]
            if unique_terms:
                enhanced_query = f"{query} {' '.join(unique_terms)}"
                logger.info(f"Enhanced query with context: {enhanced_query}")
    
    # 3. 检索知识
    try:
        hits = search(enhanced_query, top_k=5, intent_result=intent_result)
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
    format_instruction = ""
    if force_table_format:
        format_instruction = """
**重要：本次回答必须使用 Markdown 表格格式**
请将对比信息整理成清晰的表格，包含所有相关参数的对比。

表格格式示例：
| 对比项 | 产品A | 产品B |
|--------|-------|-------|
| 精度   | 0.01mm | 0.02mm |
| 产能   | 5000片/h | 3500片/h |
"""
    else:
        format_instruction = """
格式化输出要求（使用 Markdown）：
- **对比类问题**：使用 Markdown 表格展示
- **多步骤/流程**：使用有序列表 1. 2. 3.
- **多要点**：使用无序列表 - 或 *
- **代码/配置**：使用代码块
- **重点内容**：使用 **加粗** 或 `行内代码`
"""
    
    # 检测搜索结果是否真正匹配用户需求
    has_good_matches = False
    low_quality_threshold = 0.35  # 低于此分数认为不匹配
    
    if context_parts:
        # 检查平均分数 - 如果所有结果分数都很低，说明没有好的匹配
        avg_score = sum(s.get("score", 0) for s in sources) / len(sources) if sources else 0
        max_score = max((s.get("score", 0) for s in sources), default=0)
        has_good_matches = max_score > low_quality_threshold
        
        logger.info(f"Search quality: max_score={max_score:.3f}, avg_score={avg_score:.3f}, has_good_matches={has_good_matches}")
    
    if context_parts and has_good_matches:
        context = "\n\n---\n\n".join(context_parts)
        system_prompt = f"""你是一个专业的知识助手。请基于以下检索到的知识内容回答用户问题。

{context}

回答要求：
1. 基于上述内容准确回答，不要编造信息
2. 在适当位置引用来源，格式如【来源: xxx】
3. 如果检索内容不足以回答问题，请如实说明
4. 使用专业但易懂的语言
{format_instruction}"""
    elif context_parts and not has_good_matches:
        # 有结果但不匹配 - 返回相关内容但邀请贡献
        context = "\n\n---\n\n".join(context_parts)
        system_prompt = f"""你是一个专业的知识助手。用户查询的内容在知识库中没有直接匹配的资料，但找到了一些可能相关的内容。

{context}

回答要求：
1. 首先明确告知用户：目前知识库中没有找到与"{query}"直接相关的资料
2. 如果上述相关内容对用户有参考价值，可以简要提及
3. **重点**：邀请用户贡献相关材料，例如：
   "如果您手上有相关资料，欢迎通过上传功能分享给我们，帮助丰富知识库！"
4. 保持友好和专业的语气
{format_instruction}"""
    else:
        system_prompt = f"""你是一个专业的知识助手。当前知识库未找到与用户查询相关的内容。

回答要求：
1. 告知用户：目前知识库中暂无与"{query}"相关的资料
2. **重要**：积极邀请用户贡献材料：
   "如果您有相关资料，欢迎通过上传功能分享给我们！您的贡献将帮助我们完善知识库，也能帮助到其他同事。"
3. 可以询问用户是否需要其他帮助
4. 保持友好和专业的语气"""
    
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

