from minio import Minio
import os
client = Minio("localhost:9000", access_key=os.environ.get("MINIO_ROOT_USER","minio"), secret_key=os.environ.get("MINIO_ROOT_PASSWORD","minio123"), secure=False)
for b in ["bronze","silver","gold","artifacts"]:
    if not client.bucket_exists(b):
        client.make_bucket(b)
        print("created bucket", b)
