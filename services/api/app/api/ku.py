from fastapi import APIRouter, HTTPException
from ..schemas import KUCreate, KUPublish
from ..services.ku import create_ku, review_publish
from ..auth import require_role

router = APIRouter()

@router.post("/draft", dependencies=[require_role(["DATA_OPS", "BD_SALES"])])
def draft(ku: KUCreate):
    return create_ku(ku.dict())

@router.post("/publish", dependencies=[require_role(["DATA_OPS"])])
def publish(body: KUPublish):
    ku = review_publish(body.ku_id, body.decision, body.comments)
    if ku is None:
        raise HTTPException(status_code=404, detail="KU not found")
    return ku
