"""
Ingest to Bronze DAG
从uploads bucket读取文件，解析路径元数据，复制到bronze bucket
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
from minio.commonconfig import CopySource
import os
import sys
import json
import tempfile
import io

# 添加pipeline模块路径
sys.path.insert(0, '/opt/pipeline')

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio123")


def list_and_process_uploads():
    """
    List files in 'uploads' bucket, parse metadata, and move to 'bronze' bucket.
    """
    from pipeline.metadata_parser import parse_upload_path, load_manual_metadata, merge_metadata
    
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
    
    # List objects in uploads bucket (excluding metadata.json files)
    objects = [
        obj for obj in client.list_objects("uploads", recursive=True)
        if not obj.object_name.endswith('metadata.json')
    ]
    
    if not objects:
        print("No files found in uploads bucket. Upload files to MinIO 'uploads' bucket first.")
        return {"processed": 0, "files": []}
    
    processed_files = []
    for obj in objects:
        object_name = obj.object_name
        print(f"Processing: {object_name}")
        
        try:
            # 1. 解析路径元数据
            file_meta = parse_upload_path(object_name)
            
            # 2. 尝试加载手动元数据
            manual_meta = load_manual_metadata(client, "uploads", object_name)
            if manual_meta:
                print(f"  Found manual metadata for {object_name}")
                file_meta = merge_metadata(file_meta, manual_meta)
            
            # 3. 复制文件到 bronze/raw/
            raw_path = f"raw/{object_name}"
            client.copy_object(
                "bronze",
                raw_path,
                CopySource("uploads", object_name)
            )
            print(f"  Copied to bronze/{raw_path}")
            
            # 4. 保存元数据到 bronze/metadata/
            meta_dict = file_meta.to_dict()
            meta_dict["bronze_path"] = raw_path
            meta_json = json.dumps(meta_dict, ensure_ascii=False, indent=2)
            
            # 构建元数据路径
            base_name = os.path.splitext(os.path.basename(object_name))[0]
            dir_path = os.path.dirname(object_name)
            if dir_path:
                meta_path = f"metadata/{dir_path}/{base_name}.meta.json"
            else:
                meta_path = f"metadata/{base_name}.meta.json"
            
            # 写入元数据
            meta_bytes = meta_json.encode('utf-8')
            client.put_object(
                "bronze",
                meta_path,
                io.BytesIO(meta_bytes),
                len(meta_bytes),
                content_type="application/json"
            )
            print(f"  Saved metadata to bronze/{meta_path}")
            
            processed_files.append({
                "file": object_name,
                "raw_path": raw_path,
                "meta_path": meta_path,
                "scenario_id": file_meta.scenario_id,
                "solution_id": file_meta.solution_id,
            })
            
        except Exception as e:
            print(f"  Error processing {object_name}: {e}")
            import traceback
            traceback.print_exc()
    
    result = {"processed": len(processed_files), "files": processed_files}
    print(f"Ingestion complete: processed {len(processed_files)} files")
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
    Also parses path metadata and saves it to bronze/metadata/.
    
    ### Path Format:
    - `uploads/{scenario_id}/{solution_id}/{filename}` - Full hierarchy
    - `uploads/{scenario_id}/general/{filename}` - Scenario-level general
    - `uploads/common/{filename}` - Cross-scenario common materials
    - `uploads/{filename}` - Uncategorized
    
    ### Output:
    - `bronze/raw/{original_path}` - Raw file copy
    - `bronze/metadata/{path}/{name}.meta.json` - Parsed metadata
    
    ### Usage:
    1. Upload files to MinIO 'uploads' bucket (optionally with metadata.json)
    2. Trigger this DAG
    3. Files will be moved to bronze with metadata
    """
) as dag:
    
    ingest_task = PythonOperator(
        task_id="ingest_uploads_to_bronze",
        python_callable=list_and_process_uploads,
    )
