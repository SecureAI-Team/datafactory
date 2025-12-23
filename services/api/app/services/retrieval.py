from opensearchpy.helpers import scan
from ..clients.opensearch_client import os_client
from ..config import settings


def search(query: str, filters=None, top_k=5):
    must = [{"multi_match": {"query": query, "fields": ["title^2", "body", "tags"]}}]
    if filters:
        for k, v in filters.items():
            must.append({"term": {k: v}})
    body = {"query": {"bool": {"must": must}}, "size": top_k}
    res = os_client.search(index=settings.os_index, body=body)
    hits = []
    for hit in res["hits"]["hits"]:
        src = hit["_source"]
        hits.append({
            "id": src.get("id"),
            "title": src.get("title"),
            "summary": src.get("summary"),
            "body": src.get("body"),
            "score": hit.get("_score"),
            "tags": src.get("tags", []),
        })
    return hits
