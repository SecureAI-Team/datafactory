from fastapi import FastAPI
from .api.router import api_router

app = FastAPI(title="AI Data Factory API")
app.include_router(api_router, prefix="/api")

@app.get("/health")
def health():
    return {"ok": True}
