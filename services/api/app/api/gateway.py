"""
OpenAI 兼容的 Chat Completions Gateway
Phase 2: 意图识别 + 场景路由 + 澄清问卷 + 上下文管理 + 计算引擎 + 反馈优化
"""
import json
import uuid
import logging
import time
from typing import Optional, Tuple, List, Dict, Any

from openai import OpenAI
from fastapi import APIRouter, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse

from ..services.retrieval import search, get_index_stats
from ..services.scenarios import get_prompt
from ..services.intent_recognizer import (
    recognize_intent,
    IntentResult,
    IntentType,
    SceneClassification,
    get_intent_recognizer,
)
from ..services.scenario_router import get_scenario_router
from ..services.clarification import (
    generate_clarification,
    parse_clarification_response,
    get_clarification_engine,
)
from ..services.material_manager import get_material_repository
from ..services.context_manager import (
    get_or_create_context,
    save_context,
    get_context_manager,
    ConversationContext,
    ConversationState,
)
from ..services.calculation_engine import (
    try_calculate,
    get_calculation_engine,
    CalculationResult,
)
from ..services.feedback_optimizer import (
    detect_and_record_natural_feedback,
    get_feedback_optimizer,
    FeedbackType,
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize OpenAI client with Aliyun DashScope compatible endpoint
client = OpenAI(
    api_key=settings.upstream_llm_key,
    base_url=settings.upstream_llm_url.replace("/chat/completions", ""),
)

# Initialize intent recognizer with LLM client
_intent_recognizer = get_intent_recognizer(client)

# Initialize Langfuse for tracing (if configured)
langfuse = None
try:
    if settings.langfuse_public_key and settings.langfuse_api_key:
        from langfuse import Langfuse
        langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_api_key,
            host=settings.langfuse_host or "http://langfuse:3000",
        )
        logger.info(f"Langfuse initialized: host={settings.langfuse_host}")
    else:
        logger.warning("Langfuse not configured")
except Exception as e:
    logger.error(f"Langfuse initialization failed: {e}")


# ==================== 辅助函数 ====================

def detect_feedback_intent(query: str) -> Tuple[bool, Optional[bool], Optional[str]]:
    """检测用户是否在给反馈"""
    query_lower = query.lower()
    
    positive_keywords = ["有帮助", "很好", "不错", "满意", "谢谢", "感谢", "太棒了", "完美", "正是我需要的", "解决了"]
    negative_keywords = ["不满意", "没有帮助", "不对", "错了", "不准确", "有问题", "需要改进", "太简单", "不够详细"]
    clarify_keywords = ["详细说说", "展开讲讲", "具体一点", "举个例子", "不太明白", "什么意思"]
    
    for kw in positive_keywords:
        if kw in query_lower:
            return True, True, "positive"
    
    for kw in negative_keywords:
        if kw in query_lower:
            return True, False, "negative"
    
    for kw in clarify_keywords:
        if kw in query_lower:
            return True, None, "clarify"
    
    return False, None, None


def is_clarification_response(query: str) -> bool:
    """检测用户是否在回复澄清问题"""
    import re
    
    # 数字选择
    if re.match(r'^[\d\s,，、]+$', query.strip()):
        return True
    
    # 包含具体上下文的回复
    context_keywords = ["我们", "公司", "项目", "场景", "需要", "希望", "目前", "正在", "想要"]
    if any(kw in query for kw in context_keywords):
        return True
    
    # 较长的详细描述
    if len(query) > 50:
        return True
    
    return False


def get_intent_label(intent_type: IntentType) -> str:
    """获取意图的显示标签"""
    labels = {
        IntentType.SOLUTION_RECOMMENDATION: "🎯 方案推荐",
        IntentType.TECHNICAL_QA: "💡 技术问答",
        IntentType.TROUBLESHOOTING: "🔧 故障诊断",
        IntentType.COMPARISON: "⚖️ 对比分析",
        IntentType.CONCEPT_EXPLAIN: "📖 概念解释",
        IntentType.BEST_PRACTICE: "✨ 最佳实践",
        IntentType.HOW_TO: "📋 操作指南",
        IntentType.PARAMETER_QUERY: "📊 参数查询",
        IntentType.CALCULATION: "🔢 计算选型",
        IntentType.CASE_STUDY: "📁 案例参考",
        IntentType.GENERAL: "💬 通用问答",
    }
    return labels.get(intent_type, "💬 通用问答")


def get_scenario_label(scenario_ids: List[str]) -> str:
    """获取场景的显示标签"""
    scenario_names = {
        "aoi_inspection": "工业AOI视觉检测",
        "network_security": "网络安全",
        "cloud_architecture": "云架构",
        "api_design": "API设计",
    }
    
    if not scenario_ids:
        return "通用"
    
    names = [scenario_names.get(sid, sid) for sid in scenario_ids[:2]]
    return " / ".join(names)


def build_feedback_response(is_positive: bool) -> str:
    """构建反馈响应"""
    if is_positive:
        return """😊 感谢您的反馈！很高兴这个回答对您有帮助。

如果您有其他问题，随时可以继续提问。我会持续优化回答质量！"""
    else:
        return """🙏 感谢您的反馈！很抱歉这次回答没有完全满足您的需求。

为了改进，您能告诉我：
1. 具体哪部分不准确或不够详细？
2. 您期望获得什么样的信息？

我会尽力给出更好的回答！"""


def build_context_prompt(
    hits: List[Dict],
    intent_result: IntentResult,
    solutions_info: List[str] = None,
) -> str:
    """构建上下文 Prompt"""
    context_parts = []
    
    # 方案信息（如果有）
    if solutions_info:
        context_parts.append("【可推荐的解决方案】\n" + "\n".join(solutions_info))
    
    # 检索结果
    for h in hits:
        part = f"【来源: {h['source_file']}】\n标题: {h['title']}\n摘要: {h['summary']}"
        
        if h.get('key_points'):
            part += f"\n要点: {'; '.join(h['key_points'][:3])}"
        
        if h.get('body'):
            body_preview = h['body'][:500]
            part += f"\n详情: {body_preview}..."
        
        # 添加参数信息（如果有）
        if h.get('params'):
            params_str = ", ".join([
                f"{p['name']}={p.get('value', 'N/A')}{p.get('unit', '')}"
                for p in h['params'][:5]
            ])
            part += f"\n参数: {params_str}"
        
        context_parts.append(part)
    
    if context_parts:
        context = "\n\n---\n\n".join(context_parts)
        return f"""以下是从知识库检索到的相关内容，请基于这些内容回答用户问题：

{context}

请在回答中引用上述来源，格式如：【来源: xxx】"""
    else:
        return "知识库中未找到相关内容，请基于通用知识回答。"


def build_system_prompt(
    intent_result: IntentResult,
    base_prompt: str = None,
) -> str:
    """构建系统 Prompt"""
    # 获取基础 prompt
    if not base_prompt:
        if intent_result.scenario_ids:
            prompt_row = get_prompt(intent_result.scenario_ids[0])
            base_prompt = prompt_row.template if prompt_row else ""
        
        if not base_prompt:
            base_prompt = "你是一个专业的知识助手，请准确、有帮助地回答用户问题。"
    
    # 意图特定指令
    intent_instructions = {
        IntentType.SOLUTION_RECOMMENDATION: """
请按以下结构推荐解决方案：
1. 需求分析：理解用户的具体需求
2. 推荐方案：给出1-3个可选方案
3. 对比分析：说明各方案的优缺点
4. 选型建议：根据用户情况给出建议""",
        
        IntentType.PARAMETER_QUERY: """
请准确回答参数相关问题：
1. 明确给出具体数值和单位
2. 说明参数的含义和适用范围
3. 如有必要，给出参数间的关联关系""",
        
        IntentType.CALCULATION: """
请帮助用户进行计算或选型：
1. 明确计算所需的输入参数
2. 说明计算公式或选型依据
3. 给出计算结果和建议
4. 如信息不足，说明还需要哪些信息""",
        
        IntentType.TROUBLESHOOTING: """
请帮助用户诊断和解决问题：
1. 分析可能的原因
2. 给出排查步骤
3. 提供解决方案
4. 建议预防措施""",
        
        IntentType.COMPARISON: """
请客观对比分析：
1. 从多个维度进行对比
2. 使用表格形式呈现差异
3. 总结各选项的适用场景
4. 根据用户情况给出建议""",
    }
    
    intent_instruction = intent_instructions.get(intent_result.intent_type, "")
    
    # 构建完整 prompt
    intent_label = get_intent_label(intent_result.intent_type)
    scenario_label = get_scenario_label(intent_result.scenario_ids)
    
    return f"""{base_prompt}

{intent_instruction}

【重要】请在回答开头添加以下信息卡片（保持格式）：
> 🤖 **{intent_label}** | 📁 场景: {scenario_label}

【重要】请在回答结尾添加反馈引导：
---
📝 **反馈**：这个回答是否有帮助？如需调整请告诉我具体需求。"""


# ==================== API 端点 ====================

@router.post("/chat/completions")
async def gateway(
    body: dict,
    background_tasks: BackgroundTasks,
    x_scenario_id: str = Header(None),
    x_conversation_id: str = Header(None),
    authorization: str = Header(None),
):
    """
    OpenAI-compatible chat completions endpoint with RAG.
    Phase 2: 意图识别 + 场景路由 + 澄清问卷 + 上下文管理 + 计算引擎 + 反馈优化
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()
    
    # 使用传入的会话ID或生成新的
    conversation_id = x_conversation_id or trace_id
    
    logger.info(f"Chat request received, trace_id={trace_id}, conv_id={conversation_id}")
    
    # Get the user's query
    query = body["messages"][-1]["content"]
    model = body.get("model", settings.default_model)
    stream = body.get("stream", False)
    
    # 提取对话历史
    history = body["messages"][:-1] if len(body["messages"]) > 1 else []
    
    # ========== Step 0: 获取/创建对话上下文 ==========
    context = get_or_create_context(conversation_id)
    
    # 从历史中提取实体
    ctx_manager = get_context_manager()
    extracted_entities = ctx_manager.extract_entities_from_text(query, len(context.turns))
    
    # ========== Step 1: 检测反馈 ==========
    is_feedback, is_positive, feedback_type = detect_feedback_intent(query)
    
    if is_feedback and feedback_type in ("positive", "negative"):
        logger.info(f"User feedback detected: {feedback_type}")
        
        # 记录反馈
        last_response = context.turns[-1].content if context.turns else ""
        last_query = context.turns[-2].content if len(context.turns) >= 2 else query
        
        detect_and_record_natural_feedback(
            text=query,
            conversation_id=conversation_id,
            query=last_query,
            response=last_response,
            intent_type=context.turns[-1].intent_type if context.turns else None,
            scenario_id=context.current_scenario,
        )
        
        return JSONResponse(content={
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": build_feedback_response(is_positive)},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })
    
    # ========== Step 2: 意图识别 ==========
    intent_result = recognize_intent(
        query,
        history=history,
        context={"scenario_hint": x_scenario_id},
        llm_client=client,
    )
    
    logger.info(
        f"Intent: {intent_result.intent_type.value} "
        f"(conf={intent_result.confidence:.2f}, "
        f"scenes={intent_result.scenario_ids}, "
        f"clarify={intent_result.needs_clarification})"
    )
    
    # ========== Step 3: 澄清问卷 ==========
    # 检查是否需要澄清，且用户不是在回复澄清
    if intent_result.needs_clarification and not is_clarification_response(query):
        clarification_text = generate_clarification(intent_result)
        
        if clarification_text:
            logger.info(f"Generating clarification questionnaire")
            
            return JSONResponse(content={
                "id": f"chatcmpl-{trace_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": clarification_text},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            })
    
    # 如果用户在回复澄清问卷，解析回复
    clarification_context = {}
    if is_clarification_response(query):
        clarification_context = parse_clarification_response(query, intent_result)
        logger.info(f"Parsed clarification: {clarification_context}")
    
    # ========== Step 4: 开始 Langfuse Trace ==========
    trace = None
    if langfuse:
        trace = langfuse.trace(
            id=trace_id,
            name="chat_completion",
            input={
                "query": query,
                "intent": intent_result.intent_type.value,
                "scenarios": intent_result.scenario_ids,
                "confidence": intent_result.confidence,
            },
            metadata={"model": model},
        )
    
    # ========== Step 5: 场景化检索 ==========
    # 合并实体：用户输入 + 澄清回复 + 上下文历史
    entities = {
        **intent_result.entities,
        **clarification_context,
        **{e.name: e.value for e in extracted_entities},
    }
    
    # 从上下文中补充参数
    context_params = {k: v.value for k, v in context.entities.items()}
    
    # 执行检索
    hits = search(
        query,
        intent_result=intent_result,
        entities=entities,
        top_k=5,
    )
    
    # ========== Step 5.5: 计算引擎 ==========
    calculation_result = None
    if intent_result.intent_type == IntentType.CALCULATION:
        # 从检索结果中提取参数
        retrieved_params = []
        for h in hits:
            retrieved_params.extend(h.get("params", []))
        
        calculation_result = try_calculate(
            query=query,
            entities=entities,
            context_params=context_params,
            retrieved_params=retrieved_params,
        )
        
        if calculation_result:
            logger.info(
                f"Calculation: {calculation_result.calculation_type.value}, "
                f"success={calculation_result.success}"
            )
    
    # 获取层级化材料（如果匹配到场景）
    solutions_info = []
    if intent_result.scenario_ids:
        repo = get_material_repository()
        for scenario_id in intent_result.scenario_ids[:1]:
            scenario_obj = repo.get_scenario(scenario_id)
            if scenario_obj:
                for sol in scenario_obj.solutions[:3]:
                    solutions_info.append(f"- {sol.name}: {sol.summary}")
    
    # Log retrieval span
    if trace:
        trace.span(
            name="retrieval",
            input={
                "query": query,
                "scenarios": intent_result.scenario_ids,
                "entities": entities,
            },
            output={
                "hits": len(hits),
                "solutions": len(solutions_info),
                "calculation": calculation_result.calculation_type.value if calculation_result else None,
            },
        )
    
    # ========== Step 6: 构建 Prompt ==========
    context_prompt = build_context_prompt(hits, intent_result, solutions_info)
    
    # 添加计算结果到上下文
    if calculation_result and calculation_result.success:
        calc_engine = get_calculation_engine()
        calc_text = calc_engine.format_calculation_response(calculation_result)
        context_prompt = f"【计算结果】\n{calc_text}\n\n{context_prompt}"
    
    # 添加对话上下文
    conv_context_prompt = context.build_context_prompt()
    if conv_context_prompt:
        context_prompt = f"{conv_context_prompt}\n\n{context_prompt}"
    
    # 使用反馈优化器增强 Prompt
    optimizer = get_feedback_optimizer()
    system_prompt = optimizer.build_enhanced_prompt(
        build_system_prompt(intent_result),
        intent_type=intent_result.intent_type.value,
        scenario_id=intent_result.scenario_ids[0] if intent_result.scenario_ids else None,
    )
    
    # Build messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": context_prompt},
        *body["messages"],
    ]
    
    # Log generation span
    generation = None
    if trace:
        generation = trace.generation(
            name="llm_call",
            model=model,
            input=messages,
        )
    
    # ========== Step 7: 调用 LLM ==========
    if stream:
        # Streaming response
        def generate():
            full_response = ""
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )
                for chunk in response:
                    chunk_data = chunk.model_dump()
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                # 保存对话上下文
                try:
                    context.add_turn(
                        role="user",
                        content=query,
                        intent_type=intent_result.intent_type.value,
                        scenario_ids=intent_result.scenario_ids,
                        entities=[{"name": e.name, "value": e.value, "entity_type": e.entity_type, "source_turn": e.source_turn} for e in extracted_entities],
                    )
                    context.add_turn(
                        role="assistant",
                        content=full_response[:1000],  # 截断以节省空间
                        intent_type=intent_result.intent_type.value,
                    )
                    save_context(context)
                except Exception as e:
                    logger.error(f"Context save error: {e}")
                
                try:
                    if generation:
                        generation.end(output=full_response)
                    if trace:
                        trace.update(output={"response": full_response[:500]})
                    if langfuse:
                        langfuse.flush()
                except Exception as e:
                    logger.error(f"Langfuse flush error: {e}")
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        # Non-streaming response
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
        response_content = response.choices[0].message.content if response.choices else ""
        
        # ========== Step 8: 保存对话上下文 ==========
        try:
            context.add_turn(
                role="user",
                content=query,
                intent_type=intent_result.intent_type.value,
                scenario_ids=intent_result.scenario_ids,
                entities=[{"name": e.name, "value": e.value, "entity_type": e.entity_type, "source_turn": e.source_turn} for e in extracted_entities],
            )
            context.add_turn(
                role="assistant",
                content=response_content[:1000],
                intent_type=intent_result.intent_type.value,
            )
            save_context(context)
            logger.info(f"Context saved: {conversation_id}, turns={len(context.turns)}")
        except Exception as e:
            logger.error(f"Context save error: {e}")
        
        # End generation span and flush to Langfuse
        try:
            if generation:
                generation.end(
                    output=response_content,
                    usage={
                        "input": response.usage.prompt_tokens if response.usage else 0,
                        "output": response.usage.completion_tokens if response.usage else 0,
                    }
                )
            if trace:
                trace.update(output={"response": response_content[:500]})
            if langfuse:
                langfuse.flush()
        except Exception as e:
            logger.error(f"Langfuse flush error: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Chat completed in {elapsed:.2f}s, trace_id={trace_id}")
        
        return JSONResponse(content=response.model_dump())


@router.get("/models")
async def list_models():
    """List available models."""
    return {
        "object": "list",
        "data": [
            {"id": "qwen-plus", "object": "model", "owned_by": "alibaba"},
            {"id": "qwen-turbo", "object": "model", "owned_by": "alibaba"},
            {"id": "qwen-max", "object": "model", "owned_by": "alibaba"},
        ]
    }


@router.get("/debug/langfuse")
async def debug_langfuse():
    """Debug endpoint to check Langfuse configuration."""
    return {
        "langfuse_enabled": langfuse is not None,
        "langfuse_host": settings.langfuse_host,
        "langfuse_public_key": settings.langfuse_public_key[:10] + "..." if settings.langfuse_public_key else None,
        "langfuse_api_key_set": bool(settings.langfuse_api_key),
    }


@router.get("/debug/index-stats")
async def debug_index_stats():
    """获取索引统计信息"""
    return get_index_stats()


@router.post("/debug/recognize-intent")
async def debug_recognize_intent(body: dict):
    """调试接口：测试意图识别"""
    query = body.get("query", "")
    history = body.get("history", [])
    
    result = recognize_intent(query, history=history, llm_client=client)
    
    return {
        "query": query,
        "intent_type": result.intent_type.value,
        "confidence": result.confidence,
        "scene_classification": result.scene_classification.value,
        "scenario_ids": result.scenario_ids,
        "matched_keywords": result.matched_keywords,
        "entities": result.entities,
        "needs_clarification": result.needs_clarification,
        "clarification_reason": result.clarification_reason,
    }


@router.post("/debug/search")
async def debug_search(body: dict):
    """调试接口：测试场景化检索"""
    query = body.get("query", "")
    top_k = body.get("top_k", 5)
    
    # 识别意图
    intent_result = recognize_intent(query, llm_client=client)
    
    # 执行检索
    hits = search(query, intent_result=intent_result, top_k=top_k)
    
    return {
        "query": query,
        "intent": {
            "type": intent_result.intent_type.value,
            "scenarios": intent_result.scenario_ids,
            "entities": intent_result.entities,
        },
        "hits": [
            {
                "id": h["id"],
                "title": h["title"],
                "score": h["score"],
                "scenario_id": h.get("scenario_id"),
                "material_type": h.get("material_type"),
                "params": h.get("params", [])[:3],
            }
            for h in hits
        ]
    }


@router.post("/debug/calculate")
async def debug_calculate(body: dict):
    """调试接口：测试计算引擎"""
    query = body.get("query", "")
    entities = body.get("entities", {})
    context_params = body.get("context_params", {})
    
    result = try_calculate(
        query=query,
        entities=entities,
        context_params=context_params,
    )
    
    if result:
        engine = get_calculation_engine()
        return {
            "query": query,
            "calculation_type": result.calculation_type.value,
            "success": result.success,
            "result_value": result.result_value,
            "result_unit": result.result_unit,
            "result_text": result.result_text,
            "reasoning": result.reasoning,
            "inputs_used": result.inputs_used,
            "missing_inputs": result.missing_inputs,
            "formatted_response": engine.format_calculation_response(result),
        }
    else:
        return {
            "query": query,
            "calculation_detected": False,
            "message": "No calculation pattern detected in query",
        }


@router.get("/debug/context/{conversation_id}")
async def debug_get_context(conversation_id: str):
    """调试接口：获取对话上下文"""
    ctx = get_context_manager().get(conversation_id)
    
    if ctx:
        return {
            "conversation_id": conversation_id,
            "state": ctx.state.value,
            "turns_count": len(ctx.turns),
            "entities": {k: v.value for k, v in ctx.entities.items()},
            "preferences": {k: v.value for k, v in ctx.preferences.items()},
            "current_scenario": ctx.current_scenario,
            "recommended_solutions": ctx.recommended_solutions,
            "recent_turns": [
                {"role": t.role, "content": t.content[:100], "intent": t.intent_type}
                for t in ctx.turns[-5:]
            ],
            "context_prompt_preview": ctx.build_context_prompt()[:500],
        }
    else:
        return {"error": "Context not found", "conversation_id": conversation_id}


@router.delete("/debug/context/{conversation_id}")
async def debug_delete_context(conversation_id: str):
    """调试接口：删除对话上下文"""
    get_context_manager().delete(conversation_id)
    return {"deleted": conversation_id}


@router.get("/debug/feedback-stats")
async def debug_feedback_stats(days: int = 7, intent_type: str = None, scenario_id: str = None):
    """调试接口：获取反馈统计"""
    optimizer = get_feedback_optimizer()
    stats = optimizer.get_stats(days=days, intent_type=intent_type, scenario_id=scenario_id)
    
    return {
        "period_days": days,
        "total_count": stats.total_count,
        "positive_count": stats.positive_count,
        "negative_count": stats.negative_count,
        "positive_rate": stats.positive_count / stats.total_count * 100 if stats.total_count > 0 else 0,
        "average_rating": stats.average_rating,
        "by_intent": stats.by_intent,
        "by_scenario": stats.by_scenario,
        "common_issues": stats.common_issues,
    }


@router.post("/debug/record-feedback")
async def debug_record_feedback(body: dict):
    """调试接口：手动记录反馈"""
    from ..services.feedback_optimizer import record_feedback
    
    record = record_feedback(
        conversation_id=body.get("conversation_id", "test"),
        feedback_type=FeedbackType(body.get("feedback_type", "explicit_positive")),
        query=body.get("query", ""),
        response=body.get("response", ""),
        rating=body.get("rating"),
        text=body.get("text"),
        intent_type=body.get("intent_type"),
        scenario_id=body.get("scenario_id"),
    )
    
    return {
        "feedback_id": record.feedback_id,
        "feedback_type": record.feedback_type.value,
        "recorded_at": record.created_at,
    }


# ==================== Phase 3: 结构化参数调试接口 ====================

@router.post("/debug/extract-params")
async def debug_extract_params(body: dict):
    """调试接口：测试参数提取"""
    from ..services.param_extractor import extract_params, extract_param_requirements
    
    query = body.get("query", "")
    
    params = extract_params(query)
    requirements = extract_param_requirements(query)
    
    return {
        "query": query,
        "params": [p.to_dict() for p in params],
        "requirements": requirements,
    }


@router.post("/debug/smart-search")
async def debug_smart_search(body: dict):
    """调试接口：智能搜索"""
    from ..services.retrieval import smart_search
    
    query = body.get("query", "")
    top_k = body.get("top_k", 5)
    
    result = smart_search(query, top_k=top_k)
    
    return {
        "query": query,
        "strategy": result["strategy"],
        "intent": result["intent"],
        "extracted_params": result["extracted_params"],
        "total": result["total"],
        "hits": [
            {
                "id": h["id"],
                "title": h["title"],
                "score": h["score"],
                "matched_params": h.get("matched_params", []),
            }
            for h in result["hits"]
        ],
    }


@router.post("/debug/search-by-params")
async def debug_search_by_params(body: dict):
    """调试接口：参数化搜索"""
    from ..services.retrieval import search_by_params
    
    param_name = body.get("param_name", "")
    min_value = body.get("min_value")
    max_value = body.get("max_value")
    exact_value = body.get("exact_value")
    scenario_id = body.get("scenario_id")
    top_k = body.get("top_k", 10)
    
    hits = search_by_params(
        param_name=param_name,
        min_value=min_value,
        max_value=max_value,
        exact_value=exact_value,
        scenario_id=scenario_id,
        top_k=top_k,
    )
    
    return {
        "param_name": param_name,
        "filter": {
            "min_value": min_value,
            "max_value": max_value,
            "exact_value": exact_value,
        },
        "total": len(hits),
        "hits": [
            {
                "id": h["id"],
                "title": h["title"],
                "score": h["score"],
                "params": h.get("params", []),
            }
            for h in hits
        ],
    }


@router.post("/debug/compare-specs")
async def debug_compare_specs(body: dict):
    """调试接口：规格比对"""
    from ..services.calculation_engine import compare_specs, format_comparison_for_chat
    
    products = body.get("products", [])
    param_names = body.get("param_names")
    
    result = compare_specs(products, param_names)
    
    return {
        "success": result.success,
        "products": result.products,
        "comparison_table": result.comparison_table,
        "summary": result.summary,
        "recommendation": result.recommendation,
        "formatted": format_comparison_for_chat(result),
    }


@router.post("/debug/calculate-enhanced")
async def debug_calculate_enhanced(body: dict):
    """调试接口：增强计算（自动参数提取）"""
    from ..services.calculation_engine import calculate_with_extraction, format_calculation_for_chat
    
    query = body.get("query", "")
    context_params = body.get("context_params", {})
    
    result = calculate_with_extraction(query, context_params)
    
    if result:
        return {
            "success": result.success,
            "calculation_type": result.calculation_type.value,
            "result_value": result.result_value,
            "result_unit": result.result_unit,
            "result_text": result.result_text,
            "reasoning": result.reasoning,
            "inputs_used": result.inputs_used,
            "missing_inputs": result.missing_inputs,
            "formatted": format_calculation_for_chat(result),
        }
    else:
        return {"success": False, "message": "未检测到计算需求"}


# ==================== Phase 4: 优化闭环调试接口 ====================

@router.post("/debug/detect-switch")
async def debug_detect_switch(body: dict):
    """调试接口：场景切换检测"""
    from ..services.scenario_switch_detector import detect_scenario_switch
    
    current_query = body.get("query", "")
    previous_queries = body.get("previous_queries", [])
    current_scenario = body.get("current_scenario")
    
    result = detect_scenario_switch(
        current_query,
        previous_queries,
        current_scenario,
    )
    
    return {
        "switch_type": result.switch_type.value,
        "confidence": result.confidence,
        "previous_scenario": result.previous_scenario,
        "new_scenario": result.new_scenario,
        "should_clear_context": result.should_clear_context,
        "should_summarize_previous": result.should_summarize_previous,
        "transition_message": result.transition_message,
        "reasoning": result.reasoning,
    }


@router.get("/debug/feedback-report")
async def debug_feedback_report(days: int = 7):
    """调试接口：反馈分析报告"""
    from ..services.feedback_analyzer import analyze_feedback, get_feedback_analyzer
    
    report = analyze_feedback(days=days)
    
    return {
        "period": report.period,
        "total_feedback": report.total_feedback,
        "positive_rate": report.positive_rate,
        "average_rating": report.average_rating,
        "health_score": report.health_score,
        "by_intent": report.by_intent,
        "by_scenario": report.by_scenario,
        "patterns": [
            {
                "type": p.pattern_type,
                "description": p.description,
                "severity": p.severity,
                "frequency": p.frequency,
                "suggested_actions": p.suggested_actions,
            }
            for p in report.patterns
        ],
        "recommendations": report.recommendations,
        "report_text": get_feedback_analyzer().generate_report_text(report),
    }


@router.get("/debug/feedback-trend")
async def debug_feedback_trend(metric: str = "positive_rate", days: int = 7):
    """调试接口：反馈趋势"""
    from ..services.feedback_analyzer import get_feedback_trend
    
    trend = get_feedback_trend(metric, days)
    
    return {
        "metric": metric,
        "days": days,
        "data": trend,
    }


@router.get("/debug/optimization-suggestions")
async def debug_optimization_suggestions(
    intent_type: str = None,
    scenario_id: str = None,
):
    """调试接口：Prompt优化建议"""
    from ..services.prompt_optimizer import get_optimization_suggestions
    
    suggestions = get_optimization_suggestions(intent_type, scenario_id)
    
    return {
        "intent_type": intent_type,
        "scenario_id": scenario_id,
        "suggestions": [
            {
                "type": s.optimization_type.value,
                "priority": s.priority,
                "description": s.description,
                "suggested_content": s.suggested_content,
                "reasoning": s.reasoning,
                "expected_impact": s.expected_impact,
                "examples_count": len(s.examples),
            }
            for s in suggestions
        ],
    }


@router.get("/debug/health")
async def debug_health():
    """调试接口：系统健康状态"""
    from ..services.quality_monitor import get_health_status
    
    status = get_health_status()
    
    return {
        "healthy": status.healthy,
        "score": status.score,
        "components": status.components,
        "active_alerts": [
            {
                "id": a.alert_id,
                "level": a.level.value,
                "message": a.message,
                "current_value": a.current_value,
                "threshold": a.threshold,
            }
            for a in status.active_alerts
        ],
    }


@router.get("/debug/dashboard")
async def debug_dashboard():
    """调试接口：监控仪表盘数据"""
    from ..services.quality_monitor import get_dashboard_data
    
    return get_dashboard_data()


@router.post("/debug/record-quality-metric")
async def debug_record_quality_metric(body: dict):
    """调试接口：记录质量指标"""
    from ..services.quality_monitor import record_metric
    
    name = body.get("name", "")
    value = body.get("value", 0)
    labels = body.get("labels", {})
    
    record_metric(name, value, labels)
    
    return {"status": "recorded", "name": name, "value": value}
