from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
import json
import os
import tempfile

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")

def validate_knowledge_units():
    """
    Validate Knowledge Units in gold bucket before publishing.
    Checks for required fields and data quality.
    """
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    # Ensure published bucket exists
    if not minio_client.bucket_exists("published"):
        minio_client.make_bucket("published")
    
    # List Knowledge Units in gold bucket
    objects = list(minio_client.list_objects("gold", prefix="knowledge_units/", recursive=True))
    
    if not objects:
        print("No Knowledge Units found in gold/knowledge_units/ bucket.")
        return {"validated": 0, "published": 0, "failed": 0}
    
    validated = 0
    published = 0
    failed = 0
    
    required_fields = ["title", "summary"]
    
    for obj in objects:
        print(f"Validating: {obj.object_name}")
        
        try:
            # Download KU JSON
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmp:
                minio_client.fget_object("gold", obj.object_name, tmp.name)
                with open(tmp.name, 'r') as f:
                    ku_data = json.load(f)
                os.unlink(tmp.name)
            
            # Validate required fields
            validation_errors = []
            for field in required_fields:
                if field not in ku_data or not ku_data[field]:
                    validation_errors.append(f"Missing required field: {field}")
            
            # Validate title length
            if ku_data.get("title") and len(ku_data["title"]) > 200:
                validation_errors.append("Title exceeds 200 characters")
            
            # Validate summary length
            if ku_data.get("summary") and len(ku_data["summary"]) > 1000:
                validation_errors.append("Summary exceeds 1000 characters")
            
            if validation_errors:
                print(f"Validation failed for {obj.object_name}: {validation_errors}")
                ku_data["_validation_errors"] = validation_errors
                ku_data["_validation_status"] = "failed"
                failed += 1
            else:
                ku_data["_validation_status"] = "passed"
                ku_data["_validated_at"] = datetime.utcnow().isoformat()
                validated += 1
                
                # Copy to published bucket
                output_key = obj.object_name.replace("knowledge_units/", "")
                
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as out:
                    json.dump(ku_data, out, ensure_ascii=False, indent=2)
                    out_path = out.name
                
                minio_client.fput_object("published", output_key, out_path)
                print(f"Published to published/{output_key}")
                published += 1
                
                os.unlink(out_path)
            
        except Exception as e:
            print(f"Error validating {obj.object_name}: {e}")
            failed += 1
    
    result = {"validated": validated, "published": published, "failed": failed}
    print(f"Validation complete: {result}")
    return result

with DAG(
    "dq_validate_and_publish",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "quality"],
    doc_md="""
    ## Data Quality Validate and Publish DAG
    
    Validates Knowledge Units for required fields and data quality.
    Valid units are moved to the 'published' bucket.
    """
) as dag:
    
    validate_task = PythonOperator(
        task_id="validate_and_publish",
        python_callable=validate_knowledge_units,
    )
