import os
from urllib.parse import urlparse
from minio import Minio

endpoint_env = os.environ.get("MINIO_URL") or os.environ.get("MINIO_ENDPOINT") or "http://minio:9000"
parsed = urlparse(endpoint_env if "://" in endpoint_env else f"http://{endpoint_env}")
client = Minio(
    f"{parsed.hostname}:{parsed.port or 80}",
    access_key=os.getenv("MINIO_ROOT_USER", "minio"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minio123"),
    secure=(parsed.scheme == "https"),
)
sample = b"Sample PDF content for sales."
client.put_object("bronze", "uploads/sample.pdf", data=sample, length=len(sample))
print("seeded sample upload")
