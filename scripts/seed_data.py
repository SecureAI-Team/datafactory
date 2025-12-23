import os
from minio import Minio
client = Minio("localhost:9000", access_key=os.getenv("MINIO_ROOT_USER","minio"), secret_key=os.getenv("MINIO_ROOT_PASSWORD","minio123"), secure=False)
sample = b"Sample PDF content for sales."
client.put_object("bronze", "uploads/sample.pdf", data=sample, length=len(sample))
print("seeded sample upload")
