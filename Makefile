# 从 .env 文件加载环境变量（如果存在）
-include .env
export

# 默认值（如果 .env 不存在）
POSTGRES_USER ?= adf
POSTGRES_PASSWORD ?= adfpass
POSTGRES_DB ?= adf
MINIO_ROOT_USER ?= minio
MINIO_ROOT_PASSWORD ?= minio123
BASIC_AUTH_USER ?= dev
BASIC_AUTH_PASS ?= devpass

COMPOSE ?= $(shell if command -v docker-compose >/dev/null 2>&1; then echo docker-compose; elif command -v docker >/dev/null 2>&1; then echo "docker compose"; else echo docker-compose; fi)

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

# 运行完整 Pipeline V2 (从上传到索引，含参数提取)
pipeline:
	@echo "=== 运行 Pipeline V2: ingest -> extract -> params -> expand -> index ==="
	$(COMPOSE) exec -T airflow airflow dags trigger ingest_to_bronze
	@echo "Pipeline 已触发，请在 Airflow UI 查看进度: http://localhost:8080"

# 顺序执行完整 Pipeline（等待每步完成）
pipeline-full:
	@echo "=== [1/5] Ingest to Bronze ==="
	$(COMPOSE) exec -T airflow airflow dags trigger ingest_to_bronze --conf '{}'
	@sleep 5
	@echo "=== [2/5] Extract to Silver ==="
	$(COMPOSE) exec -T airflow airflow dags trigger extract_to_silver --conf '{}'
	@sleep 5
	@echo "=== [3/5] Extract Parameters ==="
	$(COMPOSE) exec -T airflow airflow dags trigger extract_params --conf '{}'
	@sleep 3
	@echo "=== [4/5] Expand to Gold ==="
	$(COMPOSE) exec -T airflow airflow dags trigger expand_and_rewrite_to_gold --conf '{}'
	@sleep 10
	@echo "=== [5/5] Index to OpenSearch ==="
	$(COMPOSE) exec -T airflow airflow dags trigger index_to_opensearch --conf '{}'
	@echo "Pipeline 已触发，请在 Airflow UI 查看进度"

# 手动运行 Pipeline 各阶段
pipeline-ingest:
	$(COMPOSE) exec -T airflow airflow dags trigger ingest_to_bronze --conf '{}'

pipeline-extract:
	$(COMPOSE) exec -T airflow airflow dags trigger extract_to_silver --conf '{}'

pipeline-params:
	$(COMPOSE) exec -T airflow airflow dags trigger extract_params --conf '{}'

pipeline-expand:
	$(COMPOSE) exec -T airflow airflow dags trigger expand_and_rewrite_to_gold --conf '{}'

pipeline-index:
	$(COMPOSE) exec -T airflow airflow dags trigger index_to_opensearch --conf '{}'

# 查看 MinIO buckets 内容
buckets:
	@$(COMPOSE) exec -T api python -c "\
from minio import Minio; \
import os; \
c = Minio('minio:9000', access_key=os.getenv('MINIO_ROOT_USER'), secret_key=os.getenv('MINIO_ROOT_PASSWORD'), secure=False); \
[print(f'=== {b} ===' + chr(10) + chr(10).join(['  ' + o.object_name for o in c.list_objects(b, recursive=True)])) for b in ['uploads', 'bronze', 'silver', 'gold']]"

# 查看 OpenSearch 索引状态
index-status:
	@curl -s "http://localhost:9200/knowledge_units/_count" | python3 -m json.tool
	@echo ""
	@curl -s "http://localhost:9200/knowledge_units/_search?size=3&pretty"

# 重建 OpenSearch 索引（新字段结构）
index-recreate:
	@echo "=== 重建 OpenSearch 索引 ==="
	$(COMPOSE) run --rm -v $(PWD):/work -w /work \
		-e OPENSEARCH_URL=http://opensearch:9200 \
		-e OPENSEARCH_INDEX=knowledge_units \
		api python scripts/create_opensearch_index.py --force

# Pipeline V2 迁移（已部署环境升级）
migrate-v2:
	@echo "=== Pipeline V2 迁移 ==="
	@echo "这将备份当前索引，重建索引结构，并准备重新处理数据"
	@read -p "确认继续? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(COMPOSE) run --rm -v $(PWD):/work -w /work \
		-e MINIO_ENDPOINT=minio:9000 \
		-e MINIO_ROOT_USER=$(MINIO_ROOT_USER) \
		-e MINIO_ROOT_PASSWORD=$(MINIO_ROOT_PASSWORD) \
		-e OPENSEARCH_HOST=opensearch \
		-e OPENSEARCH_PORT=9200 \
		-e OPENSEARCH_INDEX=knowledge_units \
		api python scripts/migrate_pipeline_v2.py --full-migrate
	@echo ""
	@echo "迁移完成，请运行 make pipeline-full 重新处理数据"

# 迁移状态检查
migrate-status:
	$(COMPOSE) run --rm -v $(PWD):/work -w /work \
		-e MINIO_ENDPOINT=minio:9000 \
		-e MINIO_ROOT_USER=$(MINIO_ROOT_USER) \
		-e MINIO_ROOT_PASSWORD=$(MINIO_ROOT_PASSWORD) \
		-e OPENSEARCH_HOST=opensearch \
		-e OPENSEARCH_PORT=9200 \
		-e OPENSEARCH_INDEX=knowledge_units \
		api python scripts/migrate_pipeline_v2.py --status

# Phase 1 升级（意图识别增强 + 场景化检索路由）
upgrade-phase1:
	@echo "=== Phase 1 升级: 意图识别增强 + 场景化检索路由 ==="
	$(COMPOSE) build --no-cache api
	$(COMPOSE) up -d api
	@sleep 5
	@echo ""
	@echo "验证新模块..."
	$(COMPOSE) exec -T api python -c "\
from app.services.intent_recognizer import recognize_intent, IntentType; \
result = recognize_intent('AOI设备功率是多少'); \
print(f'Intent: {result.intent_type.value}'); \
print(f'Scenarios: {result.scenario_ids}'); \
print(f'Entities: {result.entities}'); \
assert result.intent_type == IntentType.PARAMETER_QUERY, 'Intent recognition failed'; \
print('✓ Intent recognition OK')"
	@echo ""
	@echo "=== Phase 1 升级完成 ==="
	@echo "新增功能:"
	@echo "  - 增强意图识别（规则+LLM混合，新增参数查询/计算选型意图）"
	@echo "  - 场景化检索路由（根据意图动态调整检索策略）"
	@echo "  - 澄清问卷引擎（动态生成澄清问题）"
	@echo ""
	@echo "调试接口:"
	@echo "  POST /v1/debug/recognize-intent - 测试意图识别"
	@echo "  POST /v1/debug/search           - 测试场景化检索"
	@echo "  GET  /v1/debug/index-stats      - 索引统计信息"

# 验证 Phase 1 升级
verify-phase1:
	python scripts/upgrade_phase1.py --verify-only

# 重新部署 Airflow DAGs（更新代码后）
reload-dags:
	@echo "=== 重新加载 Airflow DAGs ==="
	$(COMPOSE) restart airflow
	@sleep 5
	$(COMPOSE) exec -T airflow airflow dags list
	@echo "DAGs 已重新加载"

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
	@echo "  Pipeline V2 (场景化增强):"
	@echo "    make pipeline         - 触发完整 Pipeline"
	@echo "    make pipeline-full    - 顺序执行全部步骤"
	@echo "    make pipeline-ingest  - 1. 上传到Bronze（解析元数据）"
	@echo "    make pipeline-extract - 2. 提取文本到Silver（识别材料类型）"
	@echo "    make pipeline-params  - 3. 提取结构化参数"
	@echo "    make pipeline-expand  - 4. LLM生成KU到Gold（场景标注）"
	@echo "    make pipeline-index   - 5. 索引到OpenSearch"
	@echo ""
	@echo "  迁移（已部署环境升级）:"
	@echo "    make migrate-status   - 查看迁移状态"
	@echo "    make migrate-v2       - 执行V2迁移（备份+重建+清理）"
	@echo "    make upgrade-phase1   - 升级到Phase1（意图识别+场景路由）"
	@echo "    make index-recreate   - 仅重建索引结构"
	@echo "    make reload-dags      - 重新加载DAG代码"
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
