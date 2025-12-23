from pydantic import BaseModel
from typing import List, Optional, Any

class IngestRequest(BaseModel):
    filename: str
    uploader: str
    mime: str
    size: int

class IngestResponse(BaseModel):
    upload_url: str
    document_id: int

class KUCreate(BaseModel):
    title: str
    summary: str
    body_markdown: str
    sections_json: dict
    tags_json: list
    glossary_terms_json: list
    evidence_map_json: dict
    source_refs_json: list

class KUPublish(BaseModel):
    ku_id: int
    decision: str
    comments: Optional[str]

class RetrievalQuery(BaseModel):
    query: str
    filters: Optional[dict] = None
    top_k: int = 5

class RetrievalResult(BaseModel):
    id: int
    title: str
    summary: str
    body: str
    score: float

class FeedbackCreate(BaseModel):
    conversation_id: int
    message_id: Optional[str]
    rating: int
    reason_enum: str
    comment: Optional[str]
