from fastapi import APIRouter
from ..schemas import IngestRequest, IngestResponse
from ..services.ingestion import presign_upload
from ..auth import require_role

router = APIRouter()

@router.post("/upload", response_model=IngestResponse, dependencies=[require_role(["DATA_OPS", "BD_SALES"])])
def upload(req: IngestRequest):
    url, doc_id = presign_upload(req.filename, req.uploader, req.mime, req.size)
    return IngestResponse(upload_url=url, document_id=doc_id)
