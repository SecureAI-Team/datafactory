from fastapi import APIRouter
from . import ingest, ku, retrieval, gateway, feedback

api_router = APIRouter()
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(ku.router, prefix="/ku", tags=["ku"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(gateway.router, prefix="/v1", tags=["gateway"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
