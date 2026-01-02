"""
Index to OpenSearch DAG
将gold bucket中的知识单元索引到OpenSearch
支持场景化字段和结构化参数
同时在数据库中创建对应的KU记录
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
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "knowledge_units")

# Database configuration
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "adf")
DB_USER = os.getenv("POSTGRES_USER", "adf")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "adfpass")


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_index_mapping():
    """获取增强后的索引映射"""
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                # 数据库关联ID
                "ku_id": {"type": "integer"},
                
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
                "bronze_path": {"type": "keyword"},
                "silver_text_path": {"type": "keyword"},
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


def create_or_update_ku_record(conn, ku_data: dict, source_path: str) -> int:
    """
    在数据库中创建或更新KU记录
    返回数据库中的 ku_id
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 检查是否已存在（基于source_file）
        source_file = ku_data.get("source_file") or source_path
        cur.execute("""
            SELECT id FROM knowledge_units 
            WHERE source_file = %s
            LIMIT 1
        """, (source_file,))
        existing = cur.fetchone()
        
        title = ku_data.get("title", "")[:500]  # 限制长度
        summary = ku_data.get("summary", "")
        body_markdown = ku_data.get("full_text", "")
        ku_type = ku_data.get("material_type", "general")
        product_id = ku_data.get("solution_id") or ku_data.get("scenario_id")
        tags = ku_data.get("terms", [])
        scenario_tags = ku_data.get("scenario_tags", [])
        key_points = ku_data.get("key_points", [])
        params = ku_data.get("params", [])
        
        if existing:
            # 更新现有记录
            cur.execute("""
                UPDATE knowledge_units SET
                    title = %s,
                    summary = %s,
                    body_markdown = %s,
                    ku_type = %s,
                    product_id = %s,
                    tags_json = %s,
                    scenario_tags = %s,
                    key_points_json = %s,
                    params_json = %s,
                    status = 'published',
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id
            """, (
                title, summary, body_markdown, ku_type, product_id,
                json.dumps(tags), json.dumps(scenario_tags),
                json.dumps(key_points), json.dumps(params),
                existing["id"]
            ))
            ku_id = cur.fetchone()["id"]
            print(f"  Updated existing KU record: {ku_id}")
        else:
            # 创建新记录
            cur.execute("""
                INSERT INTO knowledge_units (
                    title, summary, body_markdown, ku_type, product_id,
                    tags_json, scenario_tags, key_points_json, params_json,
                    source_file, status, created_by, version
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', 'pipeline', 1
                )
                RETURNING id
            """, (
                title, summary, body_markdown, ku_type, product_id,
                json.dumps(tags), json.dumps(scenario_tags),
                json.dumps(key_points), json.dumps(params),
                source_file
            ))
            ku_id = cur.fetchone()["id"]
            print(f"  Created new KU record: {ku_id}")
        
        conn.commit()
        return ku_id


def index_to_opensearch():
    """
    Index Knowledge Units from gold bucket to OpenSearch.
    Also creates/updates corresponding KU records in the database.
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
    
    # 获取数据库连接
    db_conn = None
    try:
        db_conn = get_db_connection()
        print("Connected to database")
    except Exception as e:
        print(f"Warning: Could not connect to database: {e}")
        print("Will index to OpenSearch without creating DB records")
    
    # 确保索引存在
    ensure_index_exists(os_client, OPENSEARCH_INDEX)
    
    # List Knowledge Units in gold bucket
    objects = list(minio_client.list_objects("gold", prefix="knowledge_units/", recursive=True))
    
    if not objects:
        print("No Knowledge Units found in gold/knowledge_units/ bucket.")
        return {"indexed": 0}
    
    indexed = 0
    errors = 0
    db_records_created = 0
    
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
            
            # 创建数据库KU记录并获取ku_id
            ku_id = None
            if db_conn:
                try:
                    ku_id = create_or_update_ku_record(db_conn, ku_data, ku_path)
                    ku_data["ku_id"] = ku_id
                    db_records_created += 1
                except Exception as db_err:
                    print(f"  Warning: Could not create DB record: {db_err}")
            
            # 索引到OpenSearch
            os_client.index(
                index=OPENSEARCH_INDEX,
                id=doc_id,
                body=ku_data,
                refresh=True
            )
            
            print(f"  Indexed: {ku_data.get('title', 'N/A')[:40]}...")
            print(f"    Scenario: {ku_data.get('scenario_id')} | Type: {ku_data.get('material_type')}")
            print(f"    Params: {len(ku_data.get('params', []))} | DB KU ID: {ku_id or 'N/A'}")
            indexed += 1
            
        except Exception as e:
            print(f"  Error indexing {ku_path}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
    
    # 关闭数据库连接
    if db_conn:
        db_conn.close()
    
    # 刷新索引
    os_client.indices.refresh(index=OPENSEARCH_INDEX)
    
    result = {
        "indexed": indexed, 
        "errors": errors, 
        "total": len(objects),
        "db_records": db_records_created
    }
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
