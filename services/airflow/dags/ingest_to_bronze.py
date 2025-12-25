from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime
from minio import Minio
import os

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")

def list_and_process_uploads():
    """
    List files in 'uploads' bucket and move them to 'bronze' bucket.
    This simulates the ingestion process.
    """
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    # Ensure buckets exist
    for bucket in ["uploads", "bronze", "silver", "gold"]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")
    
    # List objects in uploads bucket
    objects = list(client.list_objects("uploads", recursive=True))
    
    if not objects:
        print("No files found in uploads bucket. Upload files to MinIO 'uploads' bucket first.")
        return {"processed": 0, "files": []}
    
    processed_files = []
    for obj in objects:
        print(f"Processing: {obj.object_name}")
        
        # Copy from uploads to bronze
        client.copy_object(
            "bronze",
            f"raw/{obj.object_name}",
            f"uploads/{obj.object_name}"
        )
        
        # Remove from uploads (optional - comment out to keep original)
        # client.remove_object("uploads", obj.object_name)
        
        processed_files.append(obj.object_name)
        print(f"Moved {obj.object_name} to bronze/raw/")
    
    result = {"processed": len(processed_files), "files": processed_files}
    print(f"Ingestion complete: {result}")
    return result

with DAG(
    "ingest_to_bronze",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=["pipeline", "ingestion"],
    doc_md="""
    ## Ingest to Bronze DAG
    
    Moves files from the 'uploads' bucket to the 'bronze' bucket.
    
    ### Usage:
    1. Upload files to MinIO 'uploads' bucket
    2. Trigger this DAG
    3. Files will be moved to bronze/raw/
    """
) as dag:
    
    ingest_task = PythonOperator(
        task_id="ingest_uploads_to_bronze",
        python_callable=list_and_process_uploads,
    )
