import json
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

@router.post("/chat/completions")
async def gateway(body: dict, x_scenario_id: str = Header(None), authorization: str = Header(None)):
    """
    OpenAI-compatible chat completions endpoint with RAG.
    Retrieves relevant context from OpenSearch and augments the prompt.
    """
    scenario = x_scenario_id or settings.default_scenario
    prompt_row = get_prompt(scenario)
    system_prompt = prompt_row.template if prompt_row else "You are a helpful assistant. Cite sources when available."
    
    # Get the user's query
    query = body["messages"][-1]["content"]
    
    # Retrieve relevant context from OpenSearch
    hits = search(query, top_k=4)
    if hits:
        context = "\n\n".join([f"[{h['id']}] {h['title']}: {h['summary']}" for h in hits])
        context_prompt = f"Retrieved context (cite source IDs when using this information):\n{context}"
    else:
        context_prompt = "No relevant context found in the knowledge base."
    
    # Build messages with system prompt and context
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": context_prompt},
        *body["messages"],
    ]
    
    model = body.get("model", settings.default_model)
    stream = body.get("stream", False)
    
    if stream:
        # Streaming response
        def generate():
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            for chunk in response:
                chunk_data = chunk.model_dump()
                yield f"data: {json.dumps(chunk_data)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        # Non-streaming response
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
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
