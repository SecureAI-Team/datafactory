import uuid
from ..clients.minio_client import client
from ..db import SessionLocal
from ..models import SourceDocument


def presign_upload(filename, uploader, mime, size):
    bucket = "bronze"
    key = f"uploads/{uuid.uuid4()}-{filename}"
    policy = client.presigned_put_object(bucket, key, expires=3600)
    db = SessionLocal()
    doc = SourceDocument(filename=filename, uploader=uploader, mime=mime, size=size, minio_uri=f"s3://{bucket}/{key}")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return policy, doc.id
