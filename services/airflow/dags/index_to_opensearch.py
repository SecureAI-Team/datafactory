"""
Index to OpenSearch DAG
将gold bucket中的知识单元索引到OpenSearch
支持场景化字段和结构化参数
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from minio import Minio
from opensearchpy import OpenSearch
import json
import os
import tempfile
import hashlib

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "knowledge_units")


def get_index_mapping():
    """获取增强后的索引映射"""
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                # 基础内容字段
                "title": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {"keyword": {"type": "keyword"}}
                },
                "summary": {"type": "text", "analyzer": "standard"},
                "full_text": {"type": "text", "analyzer": "standard"},
                "key_points": {"type": "text", "analyzer": "standard"},
                "terms": {"type": "keyword"},
                
                # 场景化字段
                "scenario_id": {"type": "keyword"},
                "scenario_tags": {"type": "keyword"},
                "solution_id": {"type": "keyword"},
                "intent_types": {"type": "keyword"},
                "material_type": {"type": "keyword"},
                "applicability_score": {"type": "float"},
                
                # 结构化参数
                "params": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "value": {"type": "float"},
                        "min": {"type": "float"},
                        "max": {"type": "float"},
                        "unit": {"type": "keyword"},
                        "type": {"type": "keyword"}
                    }
                },
                
                # 来源信息
                "source_file": {"type": "keyword"},
                "original_path": {"type": "keyword"},
                "indexed_at": {"type": "date"},
                "generated_at": {"type": "date"},
            }
        }
    }


def ensure_index_exists(os_client: OpenSearch, index_name: str):
    """确保索引存在，如果不存在则创建"""
    if not os_client.indices.exists(index=index_name):
        mapping = get_index_mapping()
        os_client.indices.create(index=index_name, body=mapping)
        print(f"Created index: {index_name}")
    else:
        # 尝试更新映射（只能添加新字段）
        try:
            new_mapping = get_index_mapping()["mappings"]
            os_client.indices.put_mapping(index=index_name, body=new_mapping)
            print(f"Updated mapping for index: {index_name}")
        except Exception as e:
            print(f"Could not update mapping (may be incompatible changes): {e}")


def validate_ku_document(ku_data: dict) -> dict:
    """
    验证并规范化KU文档
    确保所有必要字段存在且格式正确
    """
    # 确保必要的文本字段
    if not ku_data.get("title"):
        ku_data["title"] = "Untitled"
    if not ku_data.get("summary"):
        ku_data["summary"] = ku_data.get("full_text", "")[:200]
    
    # 确保数组字段
    for field in ["key_points", "terms", "scenario_tags", "intent_types"]:
        if not isinstance(ku_data.get(field), list):
            ku_data[field] = []
    
    # 确保数值字段
    if not isinstance(ku_data.get("applicability_score"), (int, float)):
        ku_data["applicability_score"] = 0.5
    else:
        # 确保在0-1范围内
        ku_data["applicability_score"] = max(0.0, min(1.0, ku_data["applicability_score"]))
    
    # 验证params格式
    params = ku_data.get("params", [])
    if isinstance(params, list):
        valid_params = []
        for p in params:
            if isinstance(p, dict) and p.get("name"):
                # 确保数值字段是数字或None
                for num_field in ["value", "min", "max"]:
                    if num_field in p:
                        try:
                            p[num_field] = float(p[num_field]) if p[num_field] is not None else None
                        except (ValueError, TypeError):
                            p[num_field] = None
                valid_params.append(p)
        ku_data["params"] = valid_params
    else:
        ku_data["params"] = []
    
    # 默认值
    if not ku_data.get("material_type"):
        ku_data["material_type"] = "general"
    if not ku_data.get("scenario_id"):
        ku_data["scenario_id"] = ""
    if not ku_data.get("solution_id"):
        ku_data["solution_id"] = ""
    
    return ku_data


def index_to_opensearch():
    """
    Index Knowledge Units from gold bucket to OpenSearch.
    """
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    
    os_client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_auth=None,
        use_ssl=False,
        verify_certs=False,
    )
    
    # 确保索引存在
    ensure_index_exists(os_client, OPENSEARCH_INDEX)
    
    # List Knowledge Units in gold bucket
    objects = list(minio_client.list_objects("gold", prefix="knowledge_units/", recursive=True))
    
    if not objects:
        print("No Knowledge Units found in gold/knowledge_units/ bucket.")
        return {"indexed": 0}
    
    indexed = 0
    errors = 0
    
    for obj in objects:
        ku_path = obj.object_name
        print(f"Indexing: {ku_path}")
        
        try:
            # 下载KU JSON
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json', encoding='utf-8') as tmp:
                minio_client.fget_object("gold", ku_path, tmp.name)
                with open(tmp.name, 'r', encoding='utf-8') as f:
                    ku_data = json.load(f)
                os.unlink(tmp.name)
            
            # 验证并规范化文档
            ku_data = validate_ku_document(ku_data)
            
            # 生成文档ID（基于来源路径）
            doc_id = hashlib.md5(ku_path.encode()).hexdigest()
            
            # 添加索引时间
            ku_data["indexed_at"] = datetime.utcnow().isoformat()
            
            # 如果没有source_file，使用路径
            if not ku_data.get("source_file"):
                ku_data["source_file"] = ku_path
            
            # 索引到OpenSearch
            os_client.index(
                index=OPENSEARCH_INDEX,
                id=doc_id,
                body=ku_data,
                refresh=True
            )
            
            print(f"  Indexed: {ku_data.get('title', 'N/A')[:40]}...")
            print(f"    Scenario: {ku_data.get('scenario_id')} | Type: {ku_data.get('material_type')}")
            print(f"    Params: {len(ku_data.get('params', []))} | Score: {ku_data.get('applicability_score'):.2f}")
            indexed += 1
            
        except Exception as e:
            print(f"  Error indexing {ku_path}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
    
    # 刷新索引
    os_client.indices.refresh(index=OPENSEARCH_INDEX)
    
    result = {"indexed": indexed, "errors": errors, "total": len(objects)}
    print(f"Indexing complete: {result}")
    return result


with DAG(
    "index_to_opensearch",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "indexing"],
    doc_md="""
    ## Index to OpenSearch DAG
    
    Indexes Knowledge Units from the gold bucket to OpenSearch for retrieval.
    Supports enhanced fields for scenario-based retrieval.
    
    ### Input:
    - `gold/knowledge_units/{path}.json` - Structured Knowledge Units
    
    ### Indexed Fields:
    - Content: title, summary, full_text, key_points, terms
    - Scenario: scenario_id, scenario_tags, solution_id
    - Intent: intent_types, material_type, applicability_score
    - Params: nested structured parameters
    - Meta: source_file, original_path, indexed_at
    
    ### Usage:
    Run after expand_and_rewrite_to_gold DAG to make KUs searchable.
    """
) as dag:
    
    index_task = PythonOperator(
        task_id="index_knowledge_units",
        python_callable=index_to_opensearch,
    )
