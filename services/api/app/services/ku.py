from ..db import SessionLocal
from ..models import KnowledgeUnit, KUReview
from ..clients.opensearch_client import os_client
from ..config import settings


def create_ku(payload):
    db = SessionLocal()
    ku = KnowledgeUnit(**payload)
    db.add(ku)
    db.commit()
    db.refresh(ku)
    return ku


def review_publish(ku_id, decision, comments):
    db = SessionLocal()
    ku = db.get(KnowledgeUnit, ku_id)
    if ku is None:
        return None
    ku.status = "published" if decision == "approve" else "review"
    rev = KUReview(ku_id=ku_id, reviewer="data_ops", decision=decision, comments=comments)
    db.add(rev)
    db.commit()
    if ku.status == "published":
        doc = {
            "id": ku.id,
            "title": ku.title,
            "summary": ku.summary,
            "body": ku.body_markdown,
            "tags": ku.tags_json,
            "glossary_terms": ku.glossary_terms_json,
            "source_refs": ku.source_refs_json,
            "updated_at": ku.updated_at.isoformat() if ku.updated_at else None,
        }
        os_client.index(index=settings.os_index, id=str(ku.id), body=doc, refresh=True)
    return ku
