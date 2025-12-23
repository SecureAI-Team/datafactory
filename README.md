# AI Data Factory (single-VM, docker-compose)

## One-command quickstart (dev)
```bash
git clone https://example.com/ai-data-factory.git
cd ai-data-factory
cp .env.example .env
# 可根据需要修改 .env 中 BASIC_AUTH_USER/PASS、UPSTREAM_LLM_API_KEY 等
make init up
```

After containers are healthy (via nginx):
- API: http://localhost/api/docs
- Chat (Open WebUI): http://localhost/chat (basic auth: `.env` 的 BASIC_AUTH_USER/PASS，默认 dev/devpass)
- Portal (Budibase): http://localhost/portal
- Airflow: http://localhost/airflow
- Langfuse: http://localhost/langfuse
- OpenMetadata: http://localhost/openmetadata
- GE Data Docs: http://localhost/dq-docs
- OpenSearch (guarded): http://localhost/opensearch
- MinIO console (guarded): http://localhost/minio
- n8n: http://localhost/n8n

## Services
- FastAPI app (ingest, KU, retrieval, gateway, feedback)
- Airflow orchestrates bronze→silver→gold→publish→index
- Great Expectations for DQ gates
- MinIO for bronze/silver/gold/artifacts
- OpenSearch for retrieval
- Tika + Unstructured for extraction/partition
- Langfuse for tracing + prompt mgmt
- OpenMetadata for catalog + tasks
- Budibase portal for upload/review/publish UI
- Open WebUI for chat via our gateway
- n8n sample workflow for review notifications

## Make targets
- `make up`/`down`/`logs`
- `make init` (create buckets, index, migrations, seed)
- `make reset` (danger: wipes volumes)
- `make seed-demo`
- `make test` (API unit stubs)
- `make eval` (promptfoo multi-turn)
- `make lint`

## Resource profile
Fits in single ECS (8 vCPU/16GB recommended). Disable optional: set `DISABLE_BUDIBASE=1`, `DISABLE_OPENMETADATA=1`, `DISABLE_LANGFUSE=1` then `docker-compose up`.

## Auth & roles
JWT roles: `DATA_OPS`, `BD_SALES` via `X-API-Key`/`Authorization`. Open WebUI behind nginx basic auth (dev). Budibase users map to roles (see `services/budibase/setup-notes.md`).

## Data flow
Upload -> MinIO bronze -> Airflow Tika extract -> Unstructured partition -> LLM grounded expansion -> structured rewrite -> GE DQ -> publish KU -> OpenSearch index -> Gateway retrieval -> Chat.

## Smoke test
```bash
make smoke
```
Runs upload+pipeline+search+chat+GE checkpoint.

## TLS (optional)
`infra/nginx/gen-self-signed.sh` then set `ENABLE_TLS=1` in `.env`.

