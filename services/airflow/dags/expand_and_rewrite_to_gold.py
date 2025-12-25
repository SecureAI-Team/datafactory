from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
from openai import OpenAI
import json
import os
import tempfile

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
LLM_API_KEY = os.getenv("UPSTREAM_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
LLM_BASE_URL = os.getenv("UPSTREAM_LLM_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").replace("/chat/completions", "")
LLM_MODEL = os.getenv("DEFAULT_MODEL", "qwen-plus")

def expand_and_rewrite_to_gold():
    """
    Use LLM to expand and rewrite extracted text into structured Knowledge Units.
    """
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    # Ensure gold bucket exists
    if not minio_client.bucket_exists("gold"):
        minio_client.make_bucket("gold")
    
    # Initialize OpenAI client
    if not LLM_API_KEY:
        print("WARNING: LLM API key not configured. Set DASHSCOPE_API_KEY environment variable.")
        return {"processed": 0, "error": "No API key"}
    
    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    
    # List extracted texts in silver bucket
    objects = list(minio_client.list_objects("silver", prefix="extracted/", recursive=True))
    
    if not objects:
        print("No extracted texts found in silver/extracted/ bucket.")
        return {"processed": 0}
    
    processed = 0
    for obj in objects:
        print(f"Processing: {obj.object_name}")
        
        try:
            # Download extracted text
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as tmp:
                minio_client.fget_object("silver", obj.object_name, tmp.name)
                with open(tmp.name, 'r') as f:
                    extracted_text = f.read()
                os.unlink(tmp.name)
            
            if not extracted_text.strip():
                print(f"Skipping empty file: {obj.object_name}")
                continue
            
            # Use LLM to create structured Knowledge Unit
            prompt = """你是一个知识工程师。请将以下文本转换为结构化的知识单元（Knowledge Unit）。

要求：
1. 提取关键信息和要点
2. 生成简洁的标题和摘要
3. 识别关键术语
4. 保持原文的事实准确性

请以JSON格式返回，包含以下字段：
- title: 标题
- summary: 摘要（不超过200字）
- key_points: 关键要点列表
- terms: 关键术语列表
- full_text: 整理后的完整文本

原文：
"""
            
            response = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的知识工程师，擅长提取和结构化信息。"},
                    {"role": "user", "content": prompt + extracted_text[:4000]}  # Limit input length
                ],
                response_format={"type": "json_object"}
            )
            
            ku_json = response.choices[0].message.content
            
            # Save to gold bucket
            output_key = obj.object_name.replace("extracted/", "knowledge_units/").replace(".txt", ".json")
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as out:
                out.write(ku_json)
                out_path = out.name
            
            minio_client.fput_object("gold", output_key, out_path)
            print(f"Saved Knowledge Unit to gold/{output_key}")
            processed += 1
            
            os.unlink(out_path)
            
        except Exception as e:
            print(f"Error processing {obj.object_name}: {e}")
    
    return {"processed": processed}

with DAG(
    "expand_and_rewrite_to_gold",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "llm"],
    doc_md="""
    ## Expand and Rewrite to Gold DAG
    
    Uses LLM to transform extracted text into structured Knowledge Units.
    Saves results to the gold bucket.
    """
) as dag:
    
    rewrite_task = PythonOperator(
        task_id="expand_and_rewrite",
        python_callable=expand_and_rewrite_to_gold,
    )
