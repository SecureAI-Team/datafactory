from fastapi import FastAPI
from .api.router import api_router
from .api import gateway

app = FastAPI(title="AI Data Factory API")
app.include_router(api_router, prefix="/api")

# Also mount gateway at /v1 for Open WebUI compatibility
app.include_router(gateway.router, prefix="/v1", tags=["openai-compatible"])

@app.get("/health")
def health():
    return {"ok": True}
