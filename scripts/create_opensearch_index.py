import os
from urllib.parse import urlparse
from opensearchpy import OpenSearch

url = os.environ.get("OPENSEARCH_URL")
host_env = os.environ.get("OPENSEARCH_HOST", "opensearch")
port_env = os.environ.get("OPENSEARCH_PORT", "9200")

if url:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.hostname or host_env
    port = parsed.port or int(port_env)
    scheme = parsed.scheme
else:
    host = host_env
    port = int(port_env)
    scheme = "http"

index = os.environ.get("OPENSEARCH_INDEX", "knowledge_units")

client = OpenSearch(hosts=[{"host": host, "port": port, "scheme": scheme}], use_ssl=False, verify_certs=False)
body = {
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "summary": {"type": "text"},
            "body": {"type": "text"},
            "tags": {"type": "keyword"},
            "glossary_terms": {"type": "keyword"},
            "source_refs": {"type": "nested"},
            "updated_at": {"type": "date"},
        }
    }
}
client.indices.create(index=index, body=body, ignore=400)
print("index ready")
