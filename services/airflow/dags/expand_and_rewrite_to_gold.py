"""
Expand and Rewrite to Gold DAG
使用LLM将提取的文本转换为结构化知识单元，增强场景化标注
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
from openai import OpenAI
import json
import os
import sys
import tempfile
import io

# 添加pipeline模块路径
sys.path.insert(0, '/opt/pipeline')

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
LLM_API_KEY = os.getenv("UPSTREAM_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
LLM_BASE_URL = os.getenv("UPSTREAM_LLM_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").replace("/chat/completions", "")
LLM_MODEL = os.getenv("DEFAULT_MODEL", "qwen-plus")


def build_ku_prompt(text: str, metadata: dict, params: list) -> str:
    """
    构建KU生成的增强Prompt
    """
    scenario_id = metadata.get("scenario_id", "")
    solution_id = metadata.get("solution_id", "")
    filename = metadata.get("filename", "")
    material_type = metadata.get("material_type", "")
    intent_types = metadata.get("intent_types", [])
    applicability_score = metadata.get("applicability_score", 0.5)
    
    # 格式化已提取的参数
    params_str = ""
    if params:
        param_lines = []
        for p in params[:10]:  # 最多显示10个
            if p.get('value') is not None:
                param_lines.append(f"- {p['name']}: {p['value']} {p['unit']}")
            else:
                param_lines.append(f"- {p['name']}: {p.get('min')}-{p.get('max')} {p['unit']}")
        params_str = "\n".join(param_lines)
    
    prompt = f"""你是一个知识工程师。请将以下文本转换为结构化的知识单元（Knowledge Unit）。

【文件元数据】
- 文件名: {filename}
- 场景ID: {scenario_id or '未指定'}
- 解决方案ID: {solution_id or '未指定'}
- 初步识别材料类型: {material_type or '未识别'}
- 初步识别意图类型: {', '.join(intent_types) if intent_types else '未识别'}
- 初步通用性评分: {applicability_score:.2f}

【已提取的结构化参数】
{params_str if params_str else '无'}

【原文内容（截取）】
{text[:6000]}

【任务要求】
1. 生成简洁的标题（title）和摘要（summary，不超过200字）
2. 提取3-7个关键要点（key_points）
3. 识别关键术语（terms）
4. 整理完整文本（full_text），保持原意但可适当优化表述
5. 验证或补充场景标签（scenario_tags）- 可以有多个
6. 验证或补充意图类型（intent_types）- 参考类型：
   - solution_recommendation（方案推荐）
   - technical_qa（技术问答）
   - troubleshooting（故障诊断）
   - comparison（对比分析）
   - concept_explain（概念解释）
   - best_practice（最佳实践）
   - how_to（操作指南）
7. 评估通用性评分（applicability_score）：0-1，0=专属某场景，1=完全通用
8. 确认材料类型（material_type）：
   - whitepaper, case_study, tutorial, faq, comparison, architecture, datasheet, troubleshooting, general
9. 整合结构化参数（params）- 保留已提取的参数，可补充遗漏的

【输出JSON格式】
请严格按以下JSON格式返回：
{{
  "title": "...",
  "summary": "...",
  "key_points": ["要点1", "要点2", ...],
  "terms": ["术语1", "术语2", ...],
  "full_text": "...",
  "scenario_id": "{scenario_id or ''}",
  "scenario_tags": ["tag1", "tag2"],
  "solution_id": "{solution_id or ''}",
  "intent_types": ["intent1", "intent2"],
  "applicability_score": 0.x,
  "material_type": "...",
  "params": [
    {{"name": "参数名", "value": 数值, "unit": "单位", "type": "performance/spec/price/scope"}},
    ...
  ]
}}
"""
    return prompt


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
    
    # List text files in silver bucket
    text_objects = [
        obj for obj in minio_client.list_objects("silver", prefix="extracted/", recursive=True)
        if obj.object_name.endswith('.txt')
    ]
    
    if not text_objects:
        print("No extracted texts found in silver/extracted/ bucket.")
        return {"processed": 0}
    
    processed = 0
    for obj in text_objects:
        text_path = obj.object_name
        print(f"Processing: {text_path}")
        
        try:
            # 1. 读取提取的文本
            with tempfile.NamedTemporaryFile(delete=False, mode='w+', encoding='utf-8') as tmp:
                minio_client.fget_object("silver", text_path, tmp.name)
                with open(tmp.name, 'r', encoding='utf-8') as f:
                    extracted_text = f.read()
                os.unlink(tmp.name)
            
            if not extracted_text.strip():
                print(f"  Skipping empty file")
                continue
            
            # 2. 加载元数据
            relative_path = text_path[10:]  # 移除 "extracted/"
            if relative_path.endswith('.txt'):
                relative_path = relative_path[:-4]
            
            meta_path = f"metadata/{relative_path}.meta.json"
            
            try:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    minio_client.fget_object("silver", meta_path, tmp.name)
                    with open(tmp.name, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    os.unlink(tmp.name)
            except Exception:
                metadata = {}
            
            # 获取已提取的参数
            params = metadata.get("params", [])
            
            # 3. 构建Prompt并调用LLM
            prompt = build_ku_prompt(extracted_text, metadata, params)
            
            response = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {
                        "role": "system", 
                        "content": "你是一个专业的知识工程师，擅长提取和结构化信息。请严格按照要求的JSON格式返回结果。"
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # 较低的温度以提高一致性
            )
            
            ku_json_str = response.choices[0].message.content
            
            # 4. 解析并验证KU
            try:
                ku_data = json.loads(ku_json_str)
            except json.JSONDecodeError as e:
                print(f"  Failed to parse LLM response as JSON: {e}")
                print(f"  Response: {ku_json_str[:500]}...")
                continue
            
            # 确保必要字段存在
            required_fields = ["title", "summary", "key_points", "terms", "full_text"]
            missing = [f for f in required_fields if f not in ku_data]
            if missing:
                print(f"  Missing required fields: {missing}")
                continue
            
            # 合并元数据（LLM输出优先，但保留原始来源信息）
            ku_data["source_file"] = metadata.get("filename", os.path.basename(text_path))
            ku_data["original_path"] = metadata.get("original_path", relative_path)
            ku_data["bronze_path"] = metadata.get("bronze_path", "")
            ku_data["silver_text_path"] = text_path
            ku_data["generated_at"] = datetime.utcnow().isoformat()
            
            # 如果LLM没有返回这些字段，使用元数据中的值
            if not ku_data.get("scenario_id"):
                ku_data["scenario_id"] = metadata.get("scenario_id", "")
            if not ku_data.get("solution_id"):
                ku_data["solution_id"] = metadata.get("solution_id", "")
            if not ku_data.get("material_type"):
                ku_data["material_type"] = metadata.get("material_type", "general")
            if not ku_data.get("intent_types"):
                ku_data["intent_types"] = metadata.get("intent_types", ["technical_qa"])
            if ku_data.get("applicability_score") is None:
                ku_data["applicability_score"] = metadata.get("applicability_score", 0.5)
            if not ku_data.get("params"):
                ku_data["params"] = params
            
            # 5. 保存到gold bucket
            output_path = f"knowledge_units/{relative_path}.json"
            ku_json = json.dumps(ku_data, ensure_ascii=False, indent=2)
            ku_bytes = ku_json.encode('utf-8')
            
            minio_client.put_object(
                "gold",
                output_path,
                io.BytesIO(ku_bytes),
                len(ku_bytes),
                content_type="application/json"
            )
            
            print(f"  Saved KU to gold/{output_path}")
            print(f"  Title: {ku_data.get('title', 'N/A')[:50]}...")
            print(f"  Scenario: {ku_data.get('scenario_id')} | Type: {ku_data.get('material_type')}")
            print(f"  Intents: {ku_data.get('intent_types')} | Applicability: {ku_data.get('applicability_score'):.2f}")
            
            processed += 1
            
        except Exception as e:
            print(f"  Error processing {text_path}: {e}")
            import traceback
            traceback.print_exc()
    
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
    Enriches with scenario tags, intent types, and applicability scores.
    
    ### Input:
    - `silver/extracted/{path}.txt` - Extracted text
    - `silver/metadata/{path}.meta.json` - Enhanced metadata with params
    
    ### Output:
    - `gold/knowledge_units/{path}.json` - Structured Knowledge Unit with:
        - title, summary, key_points, terms, full_text
        - scenario_id, scenario_tags, solution_id
        - intent_types, applicability_score
        - material_type, params
    
    ### Usage:
    Run after extract_to_silver and extract_params DAGs.
    """
) as dag:
    
    rewrite_task = PythonOperator(
        task_id="expand_and_rewrite",
        python_callable=expand_and_rewrite_to_gold,
    )
