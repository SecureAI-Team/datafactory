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
    
    # Ensure index exists
    if not os_client.indices.exists(index=OPENSEARCH_INDEX):
        os_client.indices.create(
            index=OPENSEARCH_INDEX,
            body={
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "ik_max_word"},
                        "summary": {"type": "text", "analyzer": "ik_max_word"},
                        "key_points": {"type": "text"},
                        "terms": {"type": "keyword"},
                        "full_text": {"type": "text", "analyzer": "ik_max_word"},
                        "source_file": {"type": "keyword"},
                        "indexed_at": {"type": "date"}
                    }
                }
            }
        )
        print(f"Created index: {OPENSEARCH_INDEX}")
    
    # List Knowledge Units in gold bucket
    objects = list(minio_client.list_objects("gold", prefix="knowledge_units/", recursive=True))
    
    if not objects:
        print("No Knowledge Units found in gold/knowledge_units/ bucket.")
        return {"indexed": 0}
    
    indexed = 0
    for obj in objects:
        print(f"Indexing: {obj.object_name}")
        
        try:
            # Download KU JSON
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmp:
                minio_client.fget_object("gold", obj.object_name, tmp.name)
                with open(tmp.name, 'r') as f:
                    ku_data = json.load(f)
                os.unlink(tmp.name)
            
            # Generate document ID from source file
            doc_id = hashlib.md5(obj.object_name.encode()).hexdigest()
            
            # Add metadata
            ku_data["source_file"] = obj.object_name
            ku_data["indexed_at"] = datetime.utcnow().isoformat()
            
            # Index to OpenSearch
            os_client.index(
                index=OPENSEARCH_INDEX,
                id=doc_id,
                body=ku_data,
                refresh=True
            )
            
            print(f"Indexed document {doc_id}")
            indexed += 1
            
        except Exception as e:
            print(f"Error indexing {obj.object_name}: {e}")
    
    # Refresh index
    os_client.indices.refresh(index=OPENSEARCH_INDEX)
    
    return {"indexed": indexed}

with DAG(
    "index_to_opensearch",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pipeline", "indexing"],
    doc_md="""
    ## Index to OpenSearch DAG
    
    Indexes Knowledge Units from the gold bucket to OpenSearch for retrieval.
    """
) as dag:
    
    index_task = PythonOperator(
        task_id="index_knowledge_units",
        python_callable=index_to_opensearch,
    )
