from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.router import api_router
from .api import gateway
from .api import conversation
from .api import vision
from .api import kg
from .api import recommend
from .api import summary
from .api import dedup
from .api import products
from .api import bd

# 新增：自研前端 API
from .api import auth
from .api import users
from .api import conversations as conversations_v2
from .api import settings
from .api import contribute
from .api import review
from .api import stats
from .api import tasks
from .api import config
from .api import llm
from .api import storage
from .api import regression

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

# 视觉理解 API (图片问答)
app.include_router(vision.router, prefix="/v1", tags=["vision"])
app.include_router(vision.router, prefix="/api", tags=["vision"])

# 知识图谱 API
app.include_router(kg.router, prefix="/v1", tags=["knowledge-graph"])
app.include_router(kg.router, prefix="/api", tags=["knowledge-graph"])

# 智能推荐 API
app.include_router(recommend.router, prefix="/v1", tags=["recommendation"])
app.include_router(recommend.router, prefix="/api", tags=["recommendation"])

# 对话摘要 API
app.include_router(summary.router, prefix="/v1", tags=["summary"])
app.include_router(summary.router, prefix="/api", tags=["summary"])

# Phase 6: 多资料处理 API
app.include_router(dedup.router, tags=["dedup"])
app.include_router(dedup.router, prefix="/api", tags=["dedup"])

app.include_router(products.router, tags=["products"])
app.include_router(products.router, prefix="/api", tags=["products"])

app.include_router(bd.router, tags=["bd-sales"])
app.include_router(bd.router, prefix="/api", tags=["bd-sales"])

# ==================== 自研前端 API ====================

# 认证 API
app.include_router(auth.router, tags=["auth"])

# 用户管理 API
app.include_router(users.router, tags=["users"])

# 对话管理 API (新版 - 支持历史会话)
app.include_router(conversations_v2.router, tags=["conversations-v2"])

# 系统配置 API
app.include_router(settings.router, tags=["settings"])

# 贡献管理 API
app.include_router(contribute.router, tags=["contribute"])

# 审核管理 API
app.include_router(review.router, tags=["review"])

# 统计分析 API
app.include_router(stats.router, tags=["stats"])

# 任务协作 API
app.include_router(tasks.router, tags=["tasks"])

# 配置管理 API (场景/Prompt/KU类型)
app.include_router(config.router, tags=["config"])

# LLM 配置 API (提供商/模型/分配)
app.include_router(llm.router, tags=["llm-config"])

# 存储管理 API (MinIO)
app.include_router(storage.router, tags=["storage"])

# 回归测试 API
app.include_router(regression.router, tags=["regression"])

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
