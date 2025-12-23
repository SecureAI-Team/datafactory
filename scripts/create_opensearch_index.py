import os
from opensearchpy import OpenSearch

host = os.environ.get("OPENSEARCH_HOST", "opensearch")
port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
index = os.environ.get("OPENSEARCH_INDEX", "knowledge_units")

client = OpenSearch(hosts=[{"host": host, "port": port}], use_ssl=False, verify_certs=False)
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
