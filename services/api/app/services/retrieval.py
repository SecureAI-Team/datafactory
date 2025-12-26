import logging
from opensearchpy.helpers import scan
from opensearchpy.exceptions import RequestError
from ..clients.opensearch_client import os_client
from ..config import settings

logger = logging.getLogger(__name__)


def search(query: str, filters=None, top_k=5):
    """
    Search knowledge units in OpenSearch.
    Uses simple_query_string to avoid maxClauseCount issues with long queries.
    """
    # Truncate query to avoid too many clauses
    query_truncated = query[:200] if len(query) > 200 else query
    
    # Use simple_query_string which is more robust for user input
    search_query = {
        "simple_query_string": {
            "query": query_truncated,
            "fields": ["title^3", "summary^2", "full_text", "terms", "key_points"],
            "default_operator": "or"
        }
    }
    
    if filters:
        must = [search_query]
        for k, v in filters.items():
            must.append({"term": {k: v}})
        body = {"query": {"bool": {"must": must}}, "size": top_k}
    else:
        body = {"query": search_query, "size": top_k}
    
    try:
        res = os_client.search(index=settings.os_index, body=body)
    except RequestError as e:
        logger.error(f"OpenSearch query error: {e}")
        # Fallback to match_all if query fails
        try:
            res = os_client.search(index=settings.os_index, body={"query": {"match_all": {}}, "size": top_k})
        except Exception:
            return []
    except Exception as e:
        logger.error(f"OpenSearch error: {e}")
        return []
    
    hits = []
    for hit in res.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
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
