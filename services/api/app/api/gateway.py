import json
import uuid
import logging
from openai import OpenAI
from fastapi import APIRouter, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from ..services.retrieval import search
from ..services.scenarios import get_prompt
from ..services.intent_scenario import (
    recognize_intent, match_scenario, get_prompt_for_intent_scenario,
    IntentType
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
        logger.info(f"Langfuse initialized: host={settings.langfuse_host}, public_key={settings.langfuse_public_key[:10]}...")
        print(f"✓ Langfuse initialized: host={settings.langfuse_host}")
    else:
        logger.warning("Langfuse not configured: missing LANGFUSE_PUBLIC_KEY or LANGFUSE_API_KEY")
        print(f"⚠ Langfuse not configured: PUBLIC_KEY={settings.langfuse_public_key}, API_KEY={'set' if settings.langfuse_api_key else 'not set'}")
except Exception as e:
    logger.error(f"Langfuse initialization failed: {e}")
    print(f"✗ Langfuse initialization failed: {e}")

def detect_feedback_intent(query: str) -> tuple[bool, bool, str]:
    """
    检测用户是否在给反馈
    返回: (is_feedback, is_positive, feedback_type)
    """
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


def check_needs_clarification(query: str, intent_type: IntentType) -> tuple[bool, str]:
    """
    检查是否需要澄清，返回澄清问题
    """
    # 复杂/模糊问题的特征
    vague_patterns = [
        ("怎么", "如何", "方案", "推荐"),  # 方案类问题
        ("设计", "架构", "实现"),           # 设计类问题
        ("对比", "区别", "选择"),           # 对比类问题
    ]
    
    # 简单问题不需要澄清
    if len(query) < 15:
        return False, ""
    
    # 如果已经包含具体上下文，不需要澄清
    specific_keywords = ["我们公司", "我的项目", "具体来说", "比如说", "场景是"]
    if any(kw in query for kw in specific_keywords):
        return False, ""
    
    # 方案推荐类需要澄清
    if intent_type == IntentType.SOLUTION_RECOMMENDATION:
        clarification = """🤔 为了给您更精准的推荐，请先告诉我：

**请回复对应数字或直接描述：**

1️⃣ **企业规模**：小型(<100人) / 中型(100-1000人) / 大型(>1000人)
2️⃣ **预算范围**：有限 / 中等 / 充足
3️⃣ **技术能力**：基础 / 中等 / 专业团队
4️⃣ **核心需求**：（请描述您最关心的问题）

💡 或者直接告诉我您的具体场景，例如：
"我们是一家100人的金融公司，预算中等，主要担心数据泄露"
"""
        return True, clarification
    
    # 对比类需要澄清
    if intent_type == IntentType.COMPARISON:
        clarification = """🤔 为了更好地进行对比分析，请告诉我：

**您最关注哪些维度？（可多选，回复数字）**

1️⃣ **成本** - 采购、实施、运维成本
2️⃣ **技术复杂度** - 学习曲线、实施难度
3️⃣ **安全性** - 防护能力、合规性
4️⃣ **可扩展性** - 未来扩展能力
5️⃣ **成熟度** - 市场验证、案例数量

💡 或者告诉我您的选择场景，例如：
"我们想在零信任和SASE之间选择，主要考虑成本和易用性"
"""
        return True, clarification
    
    # 操作指南类可能需要澄清
    if intent_type == IntentType.HOW_TO and len(query) < 30:
        clarification = """🤔 为了给您更实用的指南，请补充：

**请回复对应信息：**

1️⃣ **您的环境**：云服务器 / 本地机房 / 混合云
2️⃣ **技术栈**：使用的主要技术或产品
3️⃣ **当前状态**：从零开始 / 已有基础 / 升级改造

💡 或者直接描述您的具体情况
"""
        return True, clarification
    
    return False, ""


@router.post("/chat/completions")
async def gateway(body: dict, background_tasks: BackgroundTasks, x_scenario_id: str = Header(None), authorization: str = Header(None)):
    """
    OpenAI-compatible chat completions endpoint with RAG.
    增强版：意图识别 + 场景匹配 + 层级化材料 + RAG + 反馈识别
    """
    trace_id = str(uuid.uuid4())
    logger.info(f"Chat request received, trace_id={trace_id}, langfuse_enabled={langfuse is not None}")
    
    # Get the user's query
    query = body["messages"][-1]["content"]
    
    # ========== 检测是否为反馈 ==========
    is_feedback, is_positive, feedback_type = detect_feedback_intent(query)
    
    if is_feedback and feedback_type in ("positive", "negative"):
        # 记录反馈（简化版，实际应保存到数据库）
        logger.info(f"User feedback detected: {feedback_type}")
        
        if is_positive:
            feedback_response = """😊 感谢您的反馈！很高兴这个回答对您有帮助。

如果您有其他问题，随时可以继续提问。我会持续优化回答质量！"""
        else:
            feedback_response = """🙏 感谢您的反馈！很抱歉这次回答没有完全满足您的需求。

为了改进，您能告诉我：
1. 具体哪部分不准确或不够详细？
2. 您期望获得什么样的信息？

我会尽力给出更好的回答！"""
        
        # 直接返回反馈响应
        return JSONResponse(content={
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion",
            "created": int(__import__('time').time()),
            "model": body.get("model", settings.default_model),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": feedback_response},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })
    
    # ========== 意图识别 ==========
    intent = recognize_intent(query, {}, client)
    logger.info(f"Intent: {intent.intent_type.value} (confidence: {intent.confidence:.2f})")
    
    # ========== 检查是否需要澄清 ==========
    # 检查用户是否在回复澄清问题（数字选择或详细描述）
    is_clarification_response = (
        query.strip() in ["1", "2", "3", "4", "5", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"] or
        len(query) > 50 or  # 详细描述
        any(kw in query for kw in ["我们", "公司", "项目", "场景", "需要", "希望"])
    )
    
    if not is_clarification_response:
        needs_clarification, clarification_prompt = check_needs_clarification(query, intent.intent_type)
        
        if needs_clarification:
            logger.info(f"Clarification needed for intent: {intent.intent_type.value}")
            
            return JSONResponse(content={
                "id": f"chatcmpl-{trace_id}",
                "object": "chat.completion",
                "created": int(__import__('time').time()),
                "model": body.get("model", settings.default_model),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": clarification_prompt},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            })
    
    # ========== 场景匹配 ==========
    scenario_config = match_scenario(query, intent)
    scenario_id = scenario_config.id if scenario_config else (x_scenario_id or settings.default_scenario)
    logger.info(f"Scenario: {scenario_id}")
    
    # ========== 获取场景化 Prompt ==========
    if scenario_config:
        template = get_prompt_for_intent_scenario(intent.intent_type, scenario_id)
        system_prompt = template.get("system_prompt", "")
    else:
        prompt_row = get_prompt(scenario_id)
        system_prompt = prompt_row.template if prompt_row else "You are a helpful assistant. Cite sources when available."
    
    # Start Langfuse trace
    trace = None
    if langfuse:
        trace = langfuse.trace(
            id=trace_id,
            name="chat_completion",
            input={"query": query, "intent": intent.intent_type.value, "scenario": scenario_id},
            metadata={"model": body.get("model", settings.default_model)},
        )
    
    # ========== 层级化材料检索 ==========
    context_parts = []
    solutions_info = []
    
    # 1. 如果匹配到场景，获取场景下的方案和材料
    if scenario_config:
        repo = get_material_repository()
        scenario_obj = repo.get_scenario(scenario_id)
        
        if scenario_obj:
            for sol in scenario_obj.solutions[:3]:
                solutions_info.append(f"- {sol.name}: {sol.summary}")
                
                for mat in sol.materials[:2]:
                    context_parts.append(
                        f"【{sol.name} - {mat.name}】\n"
                        f"类型: {mat.material_type.value}\n"
                        f"摘要: {mat.content_summary}\n"
                        f"要点: {'; '.join(mat.key_points)}"
                    )
    
    # 2. OpenSearch 检索补充
    hits = search(query, top_k=4)
    
    # Log retrieval span
    if trace:
        trace.span(
            name="retrieval",
            input={"query": query, "scenario": scenario_id},
            output={"hits": len(hits), "materials": len(context_parts)},
        )
    
    for h in hits:
        part = f"【来源: {h['source_file']}】\n标题: {h['title']}\n摘要: {h['summary']}"
        if h.get('key_points'):
            part += f"\n要点: {'; '.join(h['key_points'][:3])}"
        if h.get('body'):
            part += f"\n详情: {h['body'][:500]}..."
        context_parts.append(part)
    
    # ========== 构建上下文 Prompt ==========
    if context_parts:
        context = "\n\n---\n\n".join(context_parts)
        context_prompt = f"""以下是从知识库检索到的相关内容，请基于这些内容回答用户问题，并在回答末尾注明来源：

{context}

请在回答中引用上述来源，格式如：【来源: xxx】"""
    else:
        context_prompt = "知识库中未找到相关内容，请基于通用知识回答。"
    
    # 如果是方案推荐，添加方案列表
    if intent.intent_type == IntentType.SOLUTION_RECOMMENDATION and solutions_info:
        context_prompt = f"【可推荐的解决方案】\n" + "\n".join(solutions_info) + "\n\n" + context_prompt
    
    # ========== 构建增强的系统提示 ==========
    intent_label = {
        IntentType.SOLUTION_RECOMMENDATION: "🎯 方案推荐",
        IntentType.TECHNICAL_QA: "💡 技术问答",
        IntentType.TROUBLESHOOTING: "🔧 故障诊断",
        IntentType.COMPARISON: "⚖️ 对比分析",
        IntentType.CONCEPT_EXPLAIN: "📖 概念解释",
        IntentType.BEST_PRACTICE: "✨ 最佳实践",
        IntentType.HOW_TO: "📋 操作指南",
        IntentType.GENERAL: "💬 通用问答",
    }.get(intent.intent_type, "💬 通用问答")
    
    scenario_label = scenario_config.name if scenario_config else "通用"
    
    # 在系统提示中要求添加信息卡片
    enhanced_system_prompt = f"""{system_prompt}

【重要】请在回答开头添加以下信息卡片（保持格式）：
> 🤖 **{intent_label}** | 📁 场景: {scenario_label}

【重要】请在回答结尾添加反馈引导：
---
📝 **反馈**：这个回答是否有帮助？如需调整请告诉我具体需求。"""
    
    # Build messages with system prompt and context
    messages = [
        {"role": "system", "content": enhanced_system_prompt},
        {"role": "system", "content": context_prompt},
        *body["messages"],
    ]
    
    model = body.get("model", settings.default_model)
    stream = body.get("stream", False)
    
    # Log generation span
    generation = None
    if trace:
        generation = trace.generation(
            name="llm_call",
            model=model,
            input=messages,
        )
    
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
                # End generation span and flush (runs after streaming completes)
                try:
                    if generation:
                        generation.end(output=full_response)
                    if trace:
                        trace.update(output={"response": full_response[:500]})
                    if langfuse:
                        langfuse.flush()
                        logger.info(f"Langfuse trace flushed (stream): {trace_id}")
                except Exception as e:
                    logger.error(f"Langfuse flush error (stream): {e}")
        
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
                logger.info(f"Langfuse trace flushed: {trace_id}")
        except Exception as e:
            logger.error(f"Langfuse flush error: {e}")
        
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
