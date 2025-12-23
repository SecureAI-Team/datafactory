import os
from urllib.parse import urlparse
from minio import Minio

endpoint_env = os.environ.get("MINIO_URL") or os.environ.get("MINIO_ENDPOINT") or "http://minio:9000"
parsed = urlparse(endpoint_env if "://" in endpoint_env else f"http://{endpoint_env}")
client = Minio(
    f"{parsed.hostname}:{parsed.port or 80}",
    access_key=os.environ.get("MINIO_ROOT_USER", "minio"),
    secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minio123"),
    secure=(parsed.scheme == "https"),
)

for b in ["bronze", "silver", "gold", "artifacts"]:
    if not client.bucket_exists(b):
        client.make_bucket(b)
        print("created bucket", b)
