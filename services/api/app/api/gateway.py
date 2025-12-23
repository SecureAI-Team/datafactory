import httpx
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from ..services.retrieval import search
from ..services.scenarios import get_prompt
from ..config import settings

router = APIRouter()

@router.post("/chat/completions")
async def gateway(body: dict, x_scenario_id: str = Header(None), authorization: str = Header(None)):
    scenario = x_scenario_id or settings.default_scenario
    prompt_row = get_prompt(scenario)
    system_prompt = prompt_row.template if prompt_row else "You are a helpful assistant. Cite sources."
    query = body["messages"][-1]["content"]
    hits = search(query, top_k=4)
    context = "\n\n".join([f"{h['title']} ({h['id']}): {h['summary']}" for h in hits])
    new_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Retrieved context:\n{context}"},
        *body["messages"],
    ]
    payload = {"model": settings.default_model, "messages": new_messages, "stream": True}
    headers = {"Authorization": f"Bearer {settings.upstream_llm_key}"}
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(settings.upstream_llm_url, json=payload, headers=headers, timeout=None)
        async def streamer():
            async for chunk in r.aiter_raw():
                yield chunk
        return StreamingResponse(streamer(), media_type="text/event-stream")
