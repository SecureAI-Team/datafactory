import json, uuid, os, datetime
from minio import Minio
from opensearchpy import OpenSearch
import httpx
from .utils import load_text
from .llm import grounded_expand, structured_rewrite

minio_client = Minio("minio:9000", access_key=os.getenv("MINIO_ROOT_USER","minio"), secret_key=os.getenv("MINIO_ROOT_PASSWORD","minio123"), secure=False)
os_client = OpenSearch(hosts=[{"host": os.getenv("OPENSEARCH_HOST","opensearch"), "port": int(os.getenv("OPENSEARCH_PORT",9200))}], use_ssl=False, verify_certs=False)


def ingest_to_bronze(file_path, key):
    minio_client.fput_object("bronze", key, file_path)
    return key


def extract_to_silver(key):
    data = minio_client.get_object("bronze", key).read()
    tika_resp = httpx.put("http://tika:9998/rmeta/text", content=data, headers={"Accept": "application/json"})
    meta = tika_resp.json()[0]
    text = meta.get("X-TIKA:content", "")
    silver_key = key.replace("uploads/", "silver/") + ".json"
    payload = json.dumps({"text": text, "meta": meta})
    minio_client.put_object("silver", silver_key, data=payload.encode(), length=len(payload))
    return silver_key


def unstructured_partition(silver_key):
    obj = minio_client.get_object("silver", silver_key).read().decode()
    payload = json.loads(obj)
    res = httpx.post("http://unstructured:8000/general/v0/general", json={"text": payload.get("text", "")})
    elems = res.json()
    key = silver_key.replace("silver/", "silver/parts_")
    body = json.dumps(elems)
    minio_client.put_object("silver", key, data=body.encode(), length=len(body))
    return key


def expand_and_rewrite(silver_key):
    silver_obj = json.loads(minio_client.get_object("silver", silver_key).read().decode())
    text = silver_obj.get("text", "")
    expanded = grounded_expand(text)
    ku_json, ku_md = structured_rewrite(expanded)
    gid = str(uuid.uuid4())
    json_key = f"gold/ku/{gid}/ku.json"
    md_key = f"gold/ku/{gid}/ku.md"
    minio_client.put_object("gold", json_key, data=json.dumps(ku_json).encode(), length=len(json.dumps(ku_json)))
    minio_client.put_object("gold", md_key, data=ku_md.encode(), length=len(ku_md))
    return gid, json_key, md_key, ku_json


def dq_validate(ku_json):
    evidence = ku_json.get("evidence_map", {}) or {}
    coverage = 1.0 if evidence else 0.0
    return coverage >= 0.9


def index_to_opensearch(ku_json, ku_id):
    doc = {
        "id": ku_id,
        "title": ku_json.get("title"),
        "summary": ku_json.get("summary"),
        "body": ku_json.get("body_markdown"),
        "tags": ku_json.get("tags"),
        "glossary_terms": ku_json.get("glossary_terms"),
        "source_refs": ku_json.get("source_refs"),
        "updated_at": ku_json.get("updated_at", datetime.datetime.utcnow().isoformat()),
    }
    os_client.index(index=os.getenv("OPENSEARCH_INDEX","knowledge_units"), id=ku_id, body=doc, refresh=True)
    return True
