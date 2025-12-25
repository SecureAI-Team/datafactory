from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
import httpx
import os
import tempfile

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998/tika")

def extract_text_from_bronze():
    """
    Extract text from files in bronze bucket using Tika.
    Save extracted text to silver bucket.
    """
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    # Ensure silver bucket exists
    if not client.bucket_exists("silver"):
        client.make_bucket("silver")
    
    # List objects in bronze bucket
    objects = list(client.list_objects("bronze", prefix="raw/", recursive=True))
    
    if not objects:
        print("No files found in bronze/raw/ bucket.")
        return {"processed": 0}
    
    processed = 0
    for obj in objects:
        print(f"Extracting text from: {obj.object_name}")
        
        try:
            # Download file to temp location
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                client.fget_object("bronze", obj.object_name, tmp.name)
                tmp_path = tmp.name
            
            # Extract text using Tika
            with open(tmp_path, 'rb') as f:
                response = httpx.put(
                    TIKA_URL,
                    content=f.read(),
                    headers={"Accept": "text/plain"},
                    timeout=60.0
                )
            
            if response.status_code == 200:
                extracted_text = response.text
                
                # Save to silver bucket
                output_key = obj.object_name.replace("raw/", "extracted/") + ".txt"
                
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as out:
                    out.write(extracted_text)
                    out_path = out.name
                
                client.fput_object("silver", output_key, out_path)
                print(f"Saved extracted text to silver/{output_key}")
                processed += 1
                
                # Cleanup temp files
                os.unlink(tmp_path)
                os.unlink(out_path)
            else:
                print(f"Tika extraction failed for {obj.object_name}: {response.status_code}")
                
        except Exception as e:
            print(f"Error processing {obj.object_name}: {e}")
    
    return {"processed": processed}

with DAG(
    "extract_to_silver",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "extraction"],
    doc_md="""
    ## Extract to Silver DAG
    
    Uses Apache Tika to extract text from documents in the bronze bucket.
    Saves extracted text to the silver bucket.
    """
) as dag:
    
    extract_task = PythonOperator(
        task_id="extract_text",
        python_callable=extract_text_from_bronze,
    )
