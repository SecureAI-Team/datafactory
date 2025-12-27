"""
OpenAI 兼容的 Chat Completions Gateway
增强版：意图识别 + 场景路由 + 澄清问卷 + RAG
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
    authorization: str = Header(None),
):
    """
    OpenAI-compatible chat completions endpoint with RAG.
    增强版：意图识别 + 场景路由 + 澄清问卷 + RAG + 反馈识别
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()
    
    logger.info(f"Chat request received, trace_id={trace_id}")
    
    # Get the user's query
    query = body["messages"][-1]["content"]
    model = body.get("model", settings.default_model)
    stream = body.get("stream", False)
    
    # 提取对话历史
    history = body["messages"][:-1] if len(body["messages"]) > 1 else []
    
    # ========== Step 1: 检测反馈 ==========
    is_feedback, is_positive, feedback_type = detect_feedback_intent(query)
    
    if is_feedback and feedback_type in ("positive", "negative"):
        logger.info(f"User feedback detected: {feedback_type}")
        
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
    # 合并实体和澄清上下文
    entities = {**intent_result.entities, **clarification_context}
    
    # 执行检索
    hits = search(
        query,
        intent_result=intent_result,
        entities=entities,
        top_k=5,
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
            },
        )
    
    # ========== Step 6: 构建 Prompt ==========
    context_prompt = build_context_prompt(hits, intent_result, solutions_info)
    system_prompt = build_system_prompt(intent_result)
    
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
