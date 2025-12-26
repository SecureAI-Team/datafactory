import json
import uuid
from openai import OpenAI
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse, JSONResponse
from ..services.retrieval import search
from ..services.scenarios import get_prompt
from ..config import settings

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
except Exception as e:
    print(f"Langfuse initialization skipped: {e}")

@router.post("/chat/completions")
async def gateway(body: dict, x_scenario_id: str = Header(None), authorization: str = Header(None)):
    """
    OpenAI-compatible chat completions endpoint with RAG.
    Retrieves relevant context from OpenSearch and augments the prompt.
    """
    trace_id = str(uuid.uuid4())
    scenario = x_scenario_id or settings.default_scenario
    prompt_row = get_prompt(scenario)
    system_prompt = prompt_row.template if prompt_row else "You are a helpful assistant. Cite sources when available."
    
    # Get the user's query
    query = body["messages"][-1]["content"]
    
    # Start Langfuse trace
    trace = None
    if langfuse:
        trace = langfuse.trace(
            id=trace_id,
            name="chat_completion",
            input={"query": query, "scenario": scenario},
            metadata={"model": body.get("model", settings.default_model)},
        )
    
    # Retrieve relevant context from OpenSearch
    hits = search(query, top_k=4)
    
    # Log retrieval span
    if trace:
        trace.span(
            name="retrieval",
            input={"query": query},
            output={"hits": len(hits), "sources": [h.get("source_file") for h in hits]},
        )
    
    if hits:
        context_parts = []
        for h in hits:
            part = f"【来源: {h['source_file']}】\n标题: {h['title']}\n摘要: {h['summary']}"
            if h.get('key_points'):
                part += f"\n要点: {'; '.join(h['key_points'][:3])}"
            if h.get('body'):
                # Include first 500 chars of body for more context
                part += f"\n详情: {h['body'][:500]}..."
            context_parts.append(part)
        context = "\n\n---\n\n".join(context_parts)
        context_prompt = f"""以下是从知识库检索到的相关内容，请基于这些内容回答用户问题，并在回答末尾注明来源：

{context}

请在回答中引用上述来源，格式如：【来源: xxx】"""
    else:
        context_prompt = "知识库中未找到相关内容，请基于通用知识回答。"
    
    # Build messages with system prompt and context
    messages = [
        {"role": "system", "content": system_prompt},
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
            
            # End generation span
            if generation:
                generation.end(output=full_response)
            if trace:
                trace.update(output={"response": full_response[:500]})
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        # Non-streaming response
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
        response_content = response.choices[0].message.content if response.choices else ""
        
        # End generation span
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
