from opensearchpy import OpenSearch
client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}], use_ssl=False, verify_certs=False)
body = {
  "mappings": {
    "properties": {
      "title": {"type": "text"},
      "summary": {"type": "text"},
      "body": {"type": "text"},
      "tags": {"type": "keyword"},
      "glossary_terms": {"type": "keyword"},
      "source_refs": {"type": "nested"},
      "updated_at": {"type": "date"}
    }
  }
}
client.indices.create(index="knowledge_units", body=body, ignore=400)
print("index ready")
