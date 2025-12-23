from minio import Minio
from ..config import settings

client = Minio(
    settings.minio_url.replace("http://", "").replace("https://", ""),
    access_key=settings.minio_user,
    secret_key=settings.minio_pass,
    secure=settings.minio_url.startswith("https"),
)
