from fastapi import APIRouter
from ..schemas import RetrievalQuery
from ..services.retrieval import search

router = APIRouter()

@router.post("/query")
def query(q: RetrievalQuery):
    return search(q.query, q.filters, q.top_k)
