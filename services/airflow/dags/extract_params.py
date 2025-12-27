"""
Extract Parameters DAG
从silver bucket提取的文本中抽取结构化参数
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
import os
import sys
import json
import tempfile
import io

# 添加pipeline模块路径
sys.path.insert(0, '/opt/pipeline')

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")


def extract_params_from_silver():
    """
    Extract structured parameters from text in silver bucket.
    Updates the metadata with extracted params.
    """
    from pipeline.param_patterns import extract_params_from_text, params_to_dict
    
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    # List text files in silver bucket
    text_objects = [
        obj for obj in client.list_objects("silver", prefix="extracted/", recursive=True)
        if obj.object_name.endswith('.txt')
    ]
    
    if not text_objects:
        print("No text files found in silver/extracted/ bucket.")
        return {"processed": 0}
    
    processed = 0
    total_params = 0
    
    for obj in text_objects:
        text_path = obj.object_name
        print(f"Extracting params from: {text_path}")
        
        try:
            # 1. 读取提取的文本
            with tempfile.NamedTemporaryFile(delete=False, mode='w+', encoding='utf-8') as tmp:
                client.fget_object("silver", text_path, tmp.name)
                with open(tmp.name, 'r', encoding='utf-8') as f:
                    text = f.read()
                os.unlink(tmp.name)
            
            if not text.strip():
                print(f"  Empty text, skipping")
                continue
            
            # 2. 提取参数
            params = extract_params_from_text(text)
            params_list = params_to_dict(params)
            
            print(f"  Extracted {len(params_list)} parameters")
            for p in params_list[:5]:  # 只打印前5个
                if p.get("value"):
                    print(f"    - {p['name']}: {p['value']} {p['unit']}")
                else:
                    print(f"    - {p['name']}: {p.get('min')}-{p.get('max')} {p['unit']}")
            if len(params_list) > 5:
                print(f"    ... and {len(params_list) - 5} more")
            
            # 3. 加载并更新元数据
            # text_path 格式: extracted/{path}.txt
            relative_path = text_path[10:]  # 移除 "extracted/"
            if relative_path.endswith('.txt'):
                relative_path = relative_path[:-4]  # 移除 .txt 但保留原扩展名
            
            meta_path = f"metadata/{relative_path}.meta.json"
            
            try:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    client.fget_object("silver", meta_path, tmp.name)
                    with open(tmp.name, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    os.unlink(tmp.name)
            except Exception as e:
                print(f"  No metadata found at {meta_path}, creating new")
                metadata = {}
            
            # 4. 更新元数据
            metadata["params"] = params_list
            metadata["params_extracted_at"] = datetime.utcnow().isoformat()
            metadata["params_count"] = len(params_list)
            
            # 保存更新后的元数据
            meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
            meta_bytes = meta_json.encode('utf-8')
            client.put_object(
                "silver",
                meta_path,
                io.BytesIO(meta_bytes),
                len(meta_bytes),
                content_type="application/json"
            )
            print(f"  Updated metadata at silver/{meta_path}")
            
            processed += 1
            total_params += len(params_list)
            
        except Exception as e:
            print(f"  Error processing {text_path}: {e}")
            import traceback
            traceback.print_exc()
    
    result = {
        "processed": processed,
        "total_params": total_params,
        "avg_params": total_params / processed if processed > 0 else 0
    }
    print(f"Parameter extraction complete: {result}")
    return result


with DAG(
    "extract_params",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "params"],
    doc_md="""
    ## Extract Parameters DAG
    
    Extracts structured parameters from text files in the silver bucket.
    Uses regex patterns to identify:
    - Performance parameters (precision, speed, capacity)
    - Specification parameters (dimensions, power, weight)
    - Price parameters (cost, budget)
    - Range parameters (min-max values)
    
    ### Input:
    - `silver/extracted/{path}.txt` - Extracted text files
    - `silver/metadata/{path}.meta.json` - Existing metadata
    
    ### Output:
    - Updated `silver/metadata/{path}.meta.json` with:
        - params: List of extracted parameters
        - params_count: Number of parameters found
    
    ### Usage:
    Run after extract_to_silver DAG to enrich metadata with parameters.
    """
) as dag:
    
    extract_task = PythonOperator(
        task_id="extract_params",
        python_callable=extract_params_from_silver,
    )

