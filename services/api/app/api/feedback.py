from fastapi import APIRouter, HTTPException, Depends
from ..schemas import FeedbackCreate
from ..services.feedback import create_feedback
from ..auth import require_role

router = APIRouter()

@router.post("/", dependencies=[Depends(require_role(["DATA_OPS", "BD_SALES"]))])
def add_feedback(body: FeedbackCreate):
    fb = create_feedback(body.dict())
    return {"id": fb.id}
