"""
Extract to Silver DAG
从bronze bucket提取文本，识别材料类型，保存到silver bucket
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
import httpx
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
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998/tika")


def load_metadata(client: Minio, raw_path: str) -> dict:
    """
    加载对应的元数据文件
    
    Args:
        client: MinIO客户端
        raw_path: bronze/raw/ 下的文件路径
        
    Returns:
        元数据字典，如果不存在返回空字典
    """
    # raw_path 格式: raw/{original_path}
    if raw_path.startswith("raw/"):
        original_path = raw_path[4:]
    else:
        original_path = raw_path
    
    # 构建元数据路径
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    dir_path = os.path.dirname(original_path)
    if dir_path:
        meta_path = f"metadata/{dir_path}/{base_name}.meta.json"
    else:
        meta_path = f"metadata/{base_name}.meta.json"
    
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            client.fget_object("bronze", meta_path, tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                data = json.load(f)
            os.unlink(tmp.name)
            return data
    except Exception as e:
        print(f"  No metadata found at {meta_path}: {e}")
        return {}


def extract_text_from_bronze():
    """
    Extract text from files in bronze bucket using Tika.
    Classify material type and save to silver bucket.
    """
    from pipeline.material_classifier import classify_material, estimate_applicability_score
    
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
        raw_path = obj.object_name
        print(f"Extracting text from: {raw_path}")
        
        try:
            # 1. 加载元数据
            metadata = load_metadata(client, raw_path)
            filename = metadata.get("filename", os.path.basename(raw_path))
            scenario_id = metadata.get("scenario_id")
            
            # 2. 下载文件并用Tika提取文本
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                client.fget_object("bronze", raw_path, tmp.name)
                tmp_path = tmp.name
            
            with open(tmp_path, 'rb') as f:
                response = httpx.put(
                    TIKA_URL,
                    content=f.read(),
                    headers={"Accept": "text/plain"},
                    timeout=120.0
                )
            
            os.unlink(tmp_path)
            
            if response.status_code != 200:
                print(f"  Tika extraction failed: {response.status_code}")
                continue
            
            extracted_text = response.text.strip()
            if not extracted_text:
                print(f"  Empty text extracted, skipping")
                continue
            
            # 3. 分类材料类型
            classification = classify_material(
                filename=filename,
                content=extracted_text,
                metadata=metadata
            )
            
            # 4. 估算通用性评分
            applicability_score = metadata.get("manual_applicability_score")
            if applicability_score is None:
                applicability_score = estimate_applicability_score(scenario_id, extracted_text)
            
            # 5. 构建silver输出
            # 提取后的文本路径
            if raw_path.startswith("raw/"):
                relative_path = raw_path[4:]
            else:
                relative_path = raw_path
            
            text_path = f"extracted/{relative_path}.txt"
            
            # 保存提取的文本
            text_bytes = extracted_text.encode('utf-8')
            client.put_object(
                "silver",
                text_path,
                io.BytesIO(text_bytes),
                len(text_bytes),
                content_type="text/plain; charset=utf-8"
            )
            print(f"  Saved text to silver/{text_path}")
            
            # 6. 保存增强后的元数据
            enhanced_meta = {
                **metadata,
                "silver_text_path": text_path,
                "text_length": len(extracted_text),
                "material_type": classification.material_type,
                "material_confidence": classification.confidence,
                "intent_types": classification.intent_types,
                "applicability_score": applicability_score,
                "extracted_at": datetime.utcnow().isoformat(),
            }
            
            # 如果有手动标注的场景标签，保留
            if metadata.get("manual_scenario_tags"):
                enhanced_meta["scenario_tags"] = metadata["manual_scenario_tags"]
            
            meta_path = f"metadata/{relative_path}.meta.json"
            meta_json = json.dumps(enhanced_meta, ensure_ascii=False, indent=2)
            meta_bytes = meta_json.encode('utf-8')
            client.put_object(
                "silver",
                meta_path,
                io.BytesIO(meta_bytes),
                len(meta_bytes),
                content_type="application/json"
            )
            print(f"  Saved metadata to silver/{meta_path}")
            print(f"  Material type: {classification.material_type} (conf: {classification.confidence:.2f})")
            print(f"  Intent types: {classification.intent_types}")
            print(f"  Applicability: {applicability_score:.2f}")
            
            processed += 1
            
        except Exception as e:
            print(f"  Error processing {raw_path}: {e}")
            import traceback
            traceback.print_exc()
    
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
    Also classifies material type and estimates applicability score.
    
    ### Input:
    - `bronze/raw/{path}` - Raw files
    - `bronze/metadata/{path}.meta.json` - Path metadata
    
    ### Output:
    - `silver/extracted/{path}.txt` - Extracted text
    - `silver/metadata/{path}.meta.json` - Enhanced metadata with:
        - material_type
        - intent_types
        - applicability_score
    """
) as dag:
    
    extract_task = PythonOperator(
        task_id="extract_text",
        python_callable=extract_text_from_bronze,
    )
