from fastapi import APIRouter
from . import (
    ingest, ku, retrieval, gateway, feedback,
    dedup, products, bd, conversation, kg, recommend, summary, vision
)

api_router = APIRouter()
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(ku.router, prefix="/ku", tags=["ku"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(gateway.router, prefix="/v1", tags=["gateway"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])

# Phase A-D: 多资料处理与角色流程
api_router.include_router(dedup.router, tags=["dedup"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(bd.router, tags=["bd"])

# Phase 5: 智能能力扩展
api_router.include_router(conversation.router, tags=["conversation"])
api_router.include_router(kg.router, tags=["knowledge-graph"])
api_router.include_router(recommend.router, tags=["recommend"])
api_router.include_router(summary.router, tags=["summary"])
api_router.include_router(vision.router, tags=["vision"])
