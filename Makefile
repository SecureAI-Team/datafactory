POSTGRES_USER ?= adf
POSTGRES_PASSWORD ?= adfpass
POSTGRES_DB ?= adf
MINIO_ROOT_USER ?= minio
MINIO_ROOT_PASSWORD ?= minio123
BASIC_AUTH_USER ?= dev
BASIC_AUTH_PASS ?= devpass

COMPOSE ?= $(shell if command -v docker-compose >/dev/null 2>&1; then echo docker-compose; elif command -v docker >/dev/null 2>&1; then echo "docker compose"; else echo docker-compose; fi)
export COMPOSE

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

init:
	$(COMPOSE) up -d postgres minio opensearch
	sh scripts/wait_for.sh localhost 5432
	sh scripts/wait_for.sh localhost 9200
	sh scripts/wait_for.sh localhost 9000
	# ensure airflow DB exists
	$(COMPOSE) exec -T postgres psql -U $(POSTGRES_USER) -tc "SELECT 1 FROM pg_database WHERE datname='airflow';" | grep -q 1 || $(COMPOSE) exec -T postgres psql -U $(POSTGRES_USER) -c "CREATE DATABASE airflow;"
	$(COMPOSE) run --rm api alembic upgrade head
	$(COMPOSE) run --rm -v $(PWD):/work -w /work -e MINIO_URL=http://minio:9000 api python scripts/create_buckets.py
	$(COMPOSE) run --rm -v $(PWD):/work -w /work -e OPENSEARCH_URL=http://opensearch:9200 -e OPENSEARCH_INDEX=knowledge_units api python scripts/create_opensearch_index.py
	$(COMPOSE) run --rm -v $(PWD):/work -w /work -e MINIO_URL=http://minio:9000 api python scripts/seed_data.py
	# generate nginx basic auth file for /chat
	mkdir -p infra/nginx
	docker run --rm --entrypoint htpasswd httpd:2 -Bbn "$(BASIC_AUTH_USER)" "$(BASIC_AUTH_PASS)" > infra/nginx/.htpasswd
	$(COMPOSE) restart nginx

reset:
	$(COMPOSE) down -v

seed-demo:
	python scripts/seed_data.py

test:
	$(COMPOSE) run --rm api pytest -q

eval:
	promptfoo eval --config services/eval/promptfoo.yaml || (echo "Install promptfoo: npm install -g promptfoo"; exit 1)

lint:
	$(COMPOSE) run --rm api ruff check .

smoke:
	bash scripts/smoke_test.sh

user-sim:
	bash scripts/user_simulation.sh

# 服务初始化向导 (Langfuse, n8n, Budibase)
setup:
	bash scripts/setup_services.sh

# 验证 RAG 流程
verify:
	bash scripts/verify_rag.sh

# 运行完整 Pipeline (从上传到索引)
pipeline:
	@echo "=== 运行 Pipeline: ingest -> extract -> expand -> index ==="
	$(COMPOSE) exec airflow airflow dags trigger ingest_to_bronze
	@echo "Pipeline 已触发，请在 Airflow UI 查看进度: http://localhost:8080"

# 手动运行 Pipeline 各阶段
pipeline-ingest:
	$(COMPOSE) exec airflow airflow tasks test ingest_to_bronze ingest_files $(shell date +%Y-%m-%d)

pipeline-extract:
	$(COMPOSE) exec airflow airflow tasks test extract_to_silver extract_text $(shell date +%Y-%m-%d)

pipeline-expand:
	$(COMPOSE) exec airflow airflow tasks test expand_and_rewrite_to_gold expand_and_rewrite $(shell date +%Y-%m-%d)

pipeline-index:
	$(COMPOSE) exec airflow airflow tasks test index_to_opensearch index_knowledge_units $(shell date +%Y-%m-%d)

# 查看 MinIO buckets 内容
buckets:
	@docker run --rm --network $$(docker network ls --filter name=datafactory -q | head -1) --entrypoint sh \
		minio/mc:latest -c "mc alias set m http://minio:9000 $(MINIO_ROOT_USER) $(MINIO_ROOT_PASSWORD) && \
		echo '=== uploads ===' && mc ls m/uploads/ && \
		echo '=== bronze ===' && mc ls m/bronze/ && \
		echo '=== silver ===' && mc ls m/silver/ && \
		echo '=== gold ===' && mc ls m/gold/"

# 查看 OpenSearch 索引状态
index-status:
	@curl -s "http://localhost:9200/knowledge_units/_count" | python3 -m json.tool
	@echo ""
	@curl -s "http://localhost:9200/knowledge_units/_search?size=3&pretty"

status:
	@echo "=== Container Status ==="
	$(COMPOSE) ps
	@echo ""
	@echo "=== Service URLs ==="
	@echo "Open WebUI:    http://localhost/ (via nginx) or http://localhost:3001"
	@echo "FastAPI Docs:  http://localhost:8000/docs"
	@echo "Langfuse:      http://localhost:3000"
	@echo "n8n:           http://localhost:5678"
	@echo "Airflow:       http://localhost:8080"
	@echo "MinIO Console: http://localhost:9001"
	@echo "Budibase:      http://localhost:10000"
	@echo ""
	@echo "=== Quick Commands ==="
	@echo "make setup    - 服务初始化向导"
	@echo "make verify   - 验证 RAG 流程"
	@echo "make pipeline - 运行完整 Pipeline"
	@echo "make buckets  - 查看 MinIO 存储"

help:
	@echo "AI Data Factory - 可用命令:"
	@echo ""
	@echo "  基础操作:"
	@echo "    make up        - 启动所有服务"
	@echo "    make down      - 停止所有服务"
	@echo "    make logs      - 查看日志"
	@echo "    make status    - 查看状态和 URLs"
	@echo ""
	@echo "  初始化:"
	@echo "    make init      - 初始化数据库、存储"
	@echo "    make setup     - 服务配置向导 (Langfuse/n8n/Budibase)"
	@echo ""
	@echo "  Pipeline:"
	@echo "    make pipeline         - 触发完整 Pipeline"
	@echo "    make pipeline-ingest  - 仅运行 ingest"
	@echo "    make pipeline-extract - 仅运行 extract"
	@echo "    make pipeline-expand  - 仅运行 expand"
	@echo "    make pipeline-index   - 仅运行 index"
	@echo ""
	@echo "  验证:"
	@echo "    make verify    - 验证 RAG 流程"
	@echo "    make smoke     - 健康检查"
	@echo "    make buckets   - 查看 MinIO 内容"
	@echo "    make index-status - 查看索引状态"
	@echo ""
	@echo "  开发:"
	@echo "    make test      - 运行测试"
	@echo "    make lint      - 代码检查"
	@echo "    make reset     - 重置所有数据"
