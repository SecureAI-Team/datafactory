"""
增强版对话 API
支持：意图识别 + 场景匹配 + 多轮会话 + 问卷澄清 + 用户反馈 + 层级化材料
"""
import json
import uuid
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from openai import OpenAI
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from ..services.retrieval import search
from ..services.conversation import (
    Conversation, ConversationState, ClarificationQuestion,
    get_or_create_conversation, save_conversation,
    CLARIFICATION_SYSTEM_PROMPT
)
from ..services.feedback_optimizer import (
    get_optimizer, record_feedback, FeedbackType
)
from ..services.intent_scenario import (
    recognize_intent, match_scenario, get_prompt_for_intent_scenario,
    IntentType, IntentResult, ScenarioConfig
)
from ..services.material_manager import (
    get_material_repository, MaterialType
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# OpenAI client
client = OpenAI(
    api_key=settings.upstream_llm_key,
    base_url=settings.upstream_llm_url.replace("/chat/completions", ""),
)

# Langfuse (可选)
langfuse = None
try:
    if settings.langfuse_public_key and settings.langfuse_api_key:
        from langfuse import Langfuse
        langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_api_key,
            host=settings.langfuse_host or "http://langfuse:3000",
        )
except Exception as e:
    logger.warning(f"Langfuse not available: {e}")


# ==================== 请求/响应模型 ====================

class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    clarification_response: Optional[Dict[str, Any]] = None  # 澄清问题的回答
    stream: bool = False


class FeedbackRequest(BaseModel):
    """反馈请求"""
    conversation_id: str
    message_id: str
    feedback_type: str  # thumbs_up, thumbs_down, rating, correction
    feedback_value: Any  # true/false for thumbs, 1-5 for rating
    correction_text: Optional[str] = None


class ChatResponse(BaseModel):
    """对话响应"""
    conversation_id: str
    message_id: str
    response: str
    sources: List[Dict] = []
    needs_clarification: bool = False
    clarifications: List[Dict] = []
    state: str
    # 新增：意图和场景信息
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    scenario: Optional[str] = None
    solutions: List[Dict] = []  # 推荐的解决方案


# ==================== 核心逻辑 ====================

def analyze_needs_clarification(query: str, context: Dict) -> tuple[bool, List[ClarificationQuestion]]:
    """
    分析是否需要澄清问题
    """
    # 简单问题不需要澄清
    simple_patterns = ["你好", "谢谢", "再见", "是什么", "帮我", "请问"]
    if len(query) < 10 or any(p in query for p in simple_patterns[:3]):
        return False, []
    
    # 使用 LLM 判断
    try:
        response = client.chat.completions.create(
            model=settings.default_model,
            messages=[
                {"role": "system", "content": CLARIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户问题：{query}\n\n已有上下文：{json.dumps(context, ensure_ascii=False)}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if result.get("needs_clarification"):
            clarifications = []
            for c in result.get("clarifications", []):
                clarifications.append(ClarificationQuestion(
                    question=c["question"],
                    options=[
                        {"id": opt["id"], "text": opt["text"], "description": opt.get("description")}
                        for opt in c.get("options", [])
                    ],
                    allow_multiple=c.get("allow_multiple", False),
                    allow_free_text=c.get("allow_free_text", True),
                ))
            return True, clarifications
    except Exception as e:
        logger.error(f"Clarification analysis failed: {e}")
    
    return False, []


def build_rag_context(
    query: str,
    conversation: Conversation,
    intent: IntentResult = None,
    scenario: ScenarioConfig = None,
) -> tuple[str, List[Dict], List[Dict]]:
    """
    构建 RAG 上下文
    整合：OpenSearch 检索 + 层级化材料
    
    返回: (context, sources, solutions)
    """
    context_parts = []
    sources = []
    solutions = []
    
    # 1. 如果有场景匹配，优先获取场景下的方案和材料
    if scenario:
        repo = get_material_repository()
        scenario_obj = repo.get_scenario(scenario.id)
        
        if scenario_obj:
            # 获取场景下的解决方案
            for sol in scenario_obj.solutions[:3]:  # 最多3个方案
                solutions.append({
                    "id": sol.id,
                    "name": sol.name,
                    "summary": sol.summary,
                    "maturity_score": sol.maturity_score,
                    "cost_level": sol.cost_level,
                    "complexity_level": sol.complexity_level,
                    "tags": sol.tags,
                    "material_count": len(sol.materials),
                })
                
                # 获取方案下的材料摘要
                for mat in sol.materials[:3]:  # 每个方案最多3个材料
                    context_parts.append(
                        f"【{sol.name} - {mat.name}】\n"
                        f"类型: {mat.material_type.value}\n"
                        f"摘要: {mat.content_summary}\n"
                        f"要点: {'; '.join(mat.key_points)}"
                    )
                    sources.append({
                        "id": mat.id,
                        "title": mat.name,
                        "source_file": mat.file_path,
                        "solution": sol.name,
                        "type": mat.material_type.value,
                        "score": mat.quality_score,
                    })
    
    # 2. 从 OpenSearch 检索补充内容
    hits = search(query, top_k=4)
    
    for h in hits:
        # 避免重复
        if any(s["id"] == h["id"] for s in sources):
            continue
            
        part = f"【来源: {h['source_file']}】\n标题: {h['title']}\n摘要: {h['summary']}"
        if h.get('key_points'):
            part += f"\n要点: {'; '.join(h['key_points'][:3])}"
        if h.get('body'):
            part += f"\n详情: {h['body'][:500]}..."
        context_parts.append(part)
        
        sources.append({
            "id": h["id"],
            "title": h["title"],
            "source_file": h["source_file"],
            "score": h["score"],
        })
    
    if not context_parts:
        return "知识库中未找到直接相关的内容。", [], solutions
    
    context = "\n\n---\n\n".join(context_parts)
    return context, sources, solutions


def build_system_prompt(
    conversation: Conversation,
    rag_context: str,
    intent: IntentResult = None,
    scenario: ScenarioConfig = None,
    solutions: List[Dict] = None,
) -> str:
    """
    构建系统提示词
    整合：场景化 Prompt + 反馈优化
    """
    optimizer = get_optimizer()
    
    # 1. 获取场景化的 Prompt 模板
    if intent and scenario:
        template = get_prompt_for_intent_scenario(intent.intent_type, scenario.id)
        base_prompt = template.get("system_prompt", "")
    elif intent:
        template = get_prompt_for_intent_scenario(intent.intent_type)
        base_prompt = template.get("system_prompt", "")
    else:
        base_prompt = """你是一个专业的 AI 助手，基于知识库内容回答用户问题。

回答要求：
1. 基于提供的知识库内容回答，如有引用请标注来源
2. 如果知识库内容不足以完整回答，可以结合通用知识，但要说明
3. 回答要清晰、有条理，适当使用列表和分点
4. 对于复杂问题，先给出简要答案，再展开详细说明
5. 如果用户问题不清楚，可以主动询问澄清"""
    
    # 2. 添加用户上下文
    user_context = conversation.get_context_summary()
    if user_context:
        base_prompt += f"\n\n{user_context}"
    
    # 3. 添加解决方案信息（如果是方案推荐场景）
    if solutions and intent and intent.intent_type == IntentType.SOLUTION_RECOMMENDATION:
        solutions_text = "\n【可推荐的解决方案】\n"
        for sol in solutions:
            solutions_text += f"- {sol['name']}: {sol['summary']} (成熟度:{sol['maturity_score']}, 成本:{sol['cost_level']}, 复杂度:{sol['complexity_level']})\n"
        base_prompt += solutions_text
    
    # 4. 添加基于反馈的优化
    optimized_prompt = optimizer.build_optimized_system_prompt(base_prompt)
    
    # 5. 添加 RAG 上下文
    optimized_prompt += f"\n\n【知识库检索结果】\n{rag_context}"
    
    return optimized_prompt


def generate_response(
    conversation: Conversation,
    query: str,
    system_prompt: str,
    stream: bool = False
) -> tuple[str, str]:
    """
    生成回复
    返回: (response_text, message_id)
    """
    message_id = str(uuid.uuid4())
    
    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    # 添加历史对话
    history = conversation.get_history_for_llm(max_turns=6)
    messages.extend(history)
    
    # 添加当前问题
    messages.append({"role": "user", "content": query})
    
    # Langfuse trace
    trace = None
    generation = None
    if langfuse:
        trace = langfuse.trace(
            id=message_id,
            name="conversation",
            input={"query": query, "conversation_id": conversation.id},
        )
        generation = trace.generation(
            name="llm_response",
            model=settings.default_model,
            input=messages,
        )
    
    try:
        if stream:
            # 流式响应
            def generate():
                full_response = ""
                response = client.chat.completions.create(
                    model=settings.default_model,
                    messages=messages,
                    stream=True,
                )
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
                yield f"data: {json.dumps({'done': True, 'message_id': message_id})}\n\n"
                
                # 记录完成
                if generation:
                    generation.end(output=full_response)
                if langfuse:
                    langfuse.flush()
            
            return generate(), message_id
        else:
            # 非流式响应
            response = client.chat.completions.create(
                model=settings.default_model,
                messages=messages,
                stream=False,
            )
            response_text = response.choices[0].message.content
            
            # 记录到 Langfuse
            if generation:
                generation.end(
                    output=response_text,
                    usage={
                        "input": response.usage.prompt_tokens if response.usage else 0,
                        "output": response.usage.completion_tokens if response.usage else 0,
                    }
                )
            if langfuse:
                langfuse.flush()
            
            return response_text, message_id
            
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        if generation:
            generation.end(output=f"Error: {str(e)}")
        raise


# ==================== API 端点 ====================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    多轮对话端点
    
    支持：
    - 意图识别 + 场景匹配
    - 多轮会话历史
    - 自动澄清问卷
    - 层级化材料检索
    - RAG 检索增强
    - 反馈优化
    """
    # 获取或创建会话
    conversation = get_or_create_conversation(
        conversation_id=request.conversation_id,
        user_id=request.user_id
    )
    
    query = request.message
    
    # 处理澄清问题的回答
    if request.clarification_response and conversation.clarifications:
        for key, value in request.clarification_response.items():
            conversation.context[key] = value
        conversation.clarifications = []
        conversation.state = ConversationState.ANSWERING
        logger.info(f"Received clarification response: {request.clarification_response}")
    
    # ========== 意图识别 ==========
    intent = recognize_intent(query, conversation.context, client)
    logger.info(f"Intent recognized: {intent.intent_type.value} (confidence: {intent.confidence})")
    
    # 保存意图到会话上下文
    conversation.context["last_intent"] = intent.intent_type.value
    conversation.context["intent_confidence"] = intent.confidence
    
    # ========== 场景匹配 ==========
    scenario = match_scenario(query, intent)
    if scenario:
        logger.info(f"Scenario matched: {scenario.name}")
        conversation.context["scenario"] = scenario.id
    
    # ========== 检查是否需要澄清 ==========
    if conversation.state == ConversationState.INITIAL or not request.clarification_response:
        needs_clarification, clarifications = analyze_needs_clarification(query, conversation.context)
        
        if needs_clarification and clarifications:
            conversation.clarifications = clarifications
            conversation.state = ConversationState.NEEDS_CLARIFICATION
            conversation.add_turn("user", query)
            save_conversation(conversation)
            
            return ChatResponse(
                conversation_id=conversation.id,
                message_id=str(uuid.uuid4()),
                response="为了更好地回答您的问题，请先帮我确认以下信息：",
                sources=[],
                needs_clarification=True,
                clarifications=[c.model_dump() for c in clarifications],
                state=conversation.state.value,
                intent=intent.intent_type.value,
                intent_confidence=intent.confidence,
                scenario=scenario.id if scenario else None,
            )
    
    # ========== 构建 RAG 上下文（整合层级化材料）==========
    rag_context, sources, solutions = build_rag_context(query, conversation, intent, scenario)
    
    # ========== 构建场景化系统提示词 ==========
    system_prompt = build_system_prompt(conversation, rag_context, intent, scenario, solutions)
    
    # ========== 生成回复 ==========
    conversation.add_turn("user", query)
    
    if request.stream:
        generator, message_id = generate_response(conversation, query, system_prompt, stream=True)
        return StreamingResponse(generator, media_type="text/event-stream")
    else:
        response_text, message_id = generate_response(conversation, query, system_prompt, stream=False)
        
        # 记录助手回复
        conversation.add_turn("assistant", response_text, metadata={
            "message_id": message_id,
            "sources": [s.get("source_file", s.get("title", "")) for s in sources],
            "intent": intent.intent_type.value,
            "scenario": scenario.id if scenario else None,
        })
        conversation.state = ConversationState.AWAITING_FEEDBACK
        save_conversation(conversation)
        
        return ChatResponse(
            conversation_id=conversation.id,
            message_id=message_id,
            response=response_text,
            sources=sources,
            needs_clarification=False,
            clarifications=[],
            state=conversation.state.value,
            intent=intent.intent_type.value,
            intent_confidence=intent.confidence,
            scenario=scenario.id if scenario else None,
            solutions=solutions,
        )


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈
    
    反馈类型：
    - thumbs_up: 点赞
    - thumbs_down: 踩
    - rating: 1-5 评分
    - correction: 纠正答案
    """
    conversation = get_or_create_conversation(request.conversation_id)
    
    # 获取对应的问答对
    user_query = ""
    assistant_response = ""
    sources = []
    
    for i, turn in enumerate(conversation.turns):
        if turn.metadata.get("message_id") == request.message_id:
            assistant_response = turn.content
            sources = turn.metadata.get("sources", [])
            # 获取前一个用户消息
            if i > 0 and conversation.turns[i-1].role == "user":
                user_query = conversation.turns[i-1].content
            break
    
    if not assistant_response:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # 记录反馈
    feedback = record_feedback(
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        user_query=user_query,
        assistant_response=assistant_response,
        feedback_type=request.feedback_type,
        feedback_value=request.feedback_value,
        correction_text=request.correction_text,
        retrieved_sources=sources,
    )
    
    # 更新会话状态
    conversation.state = ConversationState.COMPLETED
    save_conversation(conversation)
    
    return {
        "status": "success",
        "feedback_id": feedback.id,
        "message": "感谢您的反馈！这将帮助我们改进回答质量。"
    }


@router.get("/feedback/stats")
async def get_feedback_stats():
    """获取反馈统计"""
    optimizer = get_optimizer()
    return optimizer.get_feedback_stats()


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取会话详情"""
    conversation = get_or_create_conversation(conversation_id)
    return {
        "id": conversation.id,
        "state": conversation.state.value,
        "turns": [
            {
                "role": t.role,
                "content": t.content[:500] + "..." if len(t.content) > 500 else t.content,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in conversation.turns
        ],
        "context": conversation.context,
    }


@router.delete("/conversation/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """清除会话"""
    conversation = get_or_create_conversation(conversation_id)
    conversation.turns = []
    conversation.context = {}
    conversation.state = ConversationState.INITIAL
    save_conversation(conversation)
    return {"status": "cleared"}


# ==================== 场景和材料管理 API ====================

@router.get("/scenarios")
async def list_scenarios():
    """列出所有场景"""
    repo = get_material_repository()
    scenarios = repo.list_scenarios()
    return {
        "scenarios": [
            {
                "id": s.id,
                "name": s.name,
                "domain": s.domain,
                "description": s.description,
                "keywords": s.keywords,
                "solution_count": len(s.solutions),
            }
            for s in scenarios
        ]
    }


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """获取场景详情"""
    repo = get_material_repository()
    scenario = repo.get_scenario(scenario_id)
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    return {
        "id": scenario.id,
        "name": scenario.name,
        "domain": scenario.domain,
        "description": scenario.description,
        "keywords": scenario.keywords,
        "solutions": [
            {
                "id": s.id,
                "name": s.name,
                "summary": s.summary,
                "maturity_score": s.maturity_score,
                "cost_level": s.cost_level,
                "complexity_level": s.complexity_level,
                "material_count": len(s.materials),
            }
            for s in scenario.solutions
        ]
    }


@router.get("/solutions/{solution_id}")
async def get_solution(solution_id: str):
    """获取方案详情"""
    repo = get_material_repository()
    solution = repo.get_solution(solution_id)
    
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    
    return {
        "id": solution.id,
        "name": solution.name,
        "description": solution.description,
        "summary": solution.summary,
        "tags": solution.tags,
        "target_audience": solution.target_audience,
        "applicable_scenarios": solution.applicable_scenarios,
        "maturity_score": solution.maturity_score,
        "cost_level": solution.cost_level,
        "complexity_level": solution.complexity_level,
        "materials": [
            {
                "id": m.id,
                "name": m.name,
                "format": m.format.value,
                "type": m.material_type.value,
                "summary": m.content_summary,
                "key_points": m.key_points,
                "quality_score": m.quality_score,
            }
            for m in solution.materials
        ]
    }


@router.get("/materials/{material_id}")
async def get_material(material_id: str):
    """获取材料详情"""
    repo = get_material_repository()
    material = repo.get_material(material_id)
    
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    solution = repo.get_solution(material.solution_id)
    
    return {
        "id": material.id,
        "name": material.name,
        "solution": solution.name if solution else None,
        "format": material.format.value,
        "type": material.material_type.value,
        "file_path": material.file_path,
        "content_summary": material.content_summary,
        "key_points": material.key_points,
        "tags": material.tags,
        "quality_score": material.quality_score,
    }


@router.get("/intents")
async def list_intents():
    """列出支持的意图类型"""
    return {
        "intents": [
            {
                "type": it.value,
                "name": it.name,
                "description": {
                    IntentType.SOLUTION_RECOMMENDATION: "方案推荐 - 帮助用户选择合适的解决方案",
                    IntentType.TECHNICAL_QA: "技术问答 - 回答技术相关问题",
                    IntentType.TROUBLESHOOTING: "故障诊断 - 帮助排查和解决问题",
                    IntentType.COMPARISON: "对比分析 - 比较多个选项的优缺点",
                    IntentType.BEST_PRACTICE: "最佳实践 - 提供行业标准和规范",
                    IntentType.CONCEPT_EXPLAIN: "概念解释 - 解释术语和概念",
                    IntentType.HOW_TO: "操作指南 - 提供步骤和流程",
                    IntentType.GENERAL: "通用问答 - 其他类型问题",
                }.get(it, "")
            }
            for it in IntentType
        ]
    }

