from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.router import api_router
from .api import gateway
from .api import conversation

app = FastAPI(
    title="AI Data Factory API",
    description="多轮对话 + RAG + 用户反馈优化",
    version="2.0.0"
)

# CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 原有 API 路由
app.include_router(api_router, prefix="/api")

# OpenAI 兼容网关 (Open WebUI 使用)
app.include_router(gateway.router, prefix="/v1", tags=["openai-compatible"])
app.include_router(gateway.router, prefix="/api/v1", tags=["openai-compatible"])

# 增强版对话 API (多轮会话 + 反馈)
app.include_router(conversation.router, prefix="/api/conversation", tags=["conversation"])

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {
        "service": "AI Data Factory API",
        "version": "2.0.0",
        "endpoints": {
            "openai_compatible": "/v1/chat/completions",
            "conversation": "/api/conversation/chat",
            "feedback": "/api/conversation/feedback",
            "docs": "/docs",
        }
    }
