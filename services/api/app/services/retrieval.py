from opensearchpy.helpers import scan
from ..clients.opensearch_client import os_client
from ..config import settings


def search(query: str, filters=None, top_k=5):
    # Search fields matching the indexed document structure
    must = [{"multi_match": {"query": query, "fields": ["title^3", "summary^2", "full_text", "terms", "key_points"]}}]
    if filters:
        for k, v in filters.items():
            must.append({"term": {k: v}})
    body = {"query": {"bool": {"must": must}}, "size": top_k}
    res = os_client.search(index=settings.os_index, body=body)
    hits = []
    for hit in res["hits"]["hits"]:
        src = hit["_source"]
        hits.append({
            "id": hit.get("_id"),
            "title": src.get("title", "Untitled"),
            "summary": src.get("summary", ""),
            "body": src.get("full_text", ""),
            "score": hit.get("_score"),
            "tags": src.get("terms", []),
            "key_points": src.get("key_points", []),
            "source_file": src.get("source_file", ""),
        })
    return hits
