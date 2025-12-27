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

# ==================== Budibase 设置 ====================

# 创建 Budibase 应用模板（显示说明）
setup-budibase:
	@echo "=== Budibase 应用自动创建 ==="
	@echo ""
	@echo "步骤 1: 登录 Budibase 并获取 API Key"
	@echo "  访问: http://<ECS_IP>:10000"
	@echo "  创建管理员账户后，进入 Settings -> API -> 生成 API Key"
	@echo ""
	@echo "步骤 2: 运行自动创建脚本"
	@echo "  make setup-budibase-run BUDIBASE_API_KEY=your_api_key"
	@echo ""
	@echo "步骤 3: 在 Budibase UI 中设计界面并发布"
	@echo ""

# 运行 Budibase 自动创建脚本
setup-budibase-run:
	@if [ -z "$(BUDIBASE_API_KEY)" ]; then \
		echo "错误: 请设置 BUDIBASE_API_KEY"; \
		echo "用法: make setup-budibase-run BUDIBASE_API_KEY=your_key"; \
		exit 1; \
	fi
	$(COMPOSE) run --rm -v $(PWD):/work -w /work \
		-e BUDIBASE_URL=http://budibase:10000 \
		-e BUDIBASE_API_KEY=$(BUDIBASE_API_KEY) \
		-e API_INTERNAL_URL=http://api:8000 \
		api python scripts/setup_budibase_app.py

# ==================== n8n 设置 ====================

# 创建 n8n 工作流（显示说明）
setup-n8n:
	@echo "=== n8n 工作流自动创建 ==="
	@echo ""
	@echo "方式 1: 手动导入 JSON（推荐）"
	@echo "  1. 访问 n8n: http://<ECS_IP>:5678"
	@echo "  2. 创建账户并登录"
	@echo "  3. 点击 Import from File"
	@echo "  4. 选择 infra/n8n/workflows.json"
	@echo ""
	@echo "方式 2: API 自动创建"
	@echo "  1. 在 n8n 中启用 API (Settings -> API)"
	@echo "  2. 生成 API Key"
	@echo "  3. 运行: make setup-n8n-run N8N_API_KEY=your_key"
	@echo ""

# 运行 n8n 自动创建脚本
setup-n8n-run:
	@if [ -z "$(N8N_API_KEY)" ]; then \
		echo "错误: 请设置 N8N_API_KEY"; \
		echo "用法: make setup-n8n-run N8N_API_KEY=your_key"; \
		exit 1; \
	fi
	$(COMPOSE) run --rm -v $(PWD):/work -w /work \
		-e N8N_URL=http://n8n:5678 \
		-e N8N_API_KEY=$(N8N_API_KEY) \
		-e API_INTERNAL_URL=http://api:8000 \
		api python scripts/setup_n8n_workflows.py

# 显示 n8n 工作流 JSON（用于手动导入）
n8n-export:
	@cat infra/n8n/workflows.json

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

# Phase 2 升级（上下文管理 + 计算引擎 + 反馈优化）
upgrade-phase2:
	@echo "=== Phase 2 升级: 上下文管理 + 计算引擎 + 反馈优化 ==="
	$(COMPOSE) run --rm api alembic upgrade head || true
	$(COMPOSE) build --no-cache api
	$(COMPOSE) up -d api redis
	@sleep 5
	@echo ""
	@echo "验证新模块..."
	$(COMPOSE) exec -T api python -c "\
from app.services.calculation_engine import try_calculate; \
result = try_calculate('产能5000片/小时需要几台设备', {'需求产能': {'value': 5000}}); \
print(f'Calculation: {result.result_value if result else None}'); \
assert result and result.success, 'Calculation failed'; \
print('✓ Calculation engine OK')"
	@echo ""
	$(COMPOSE) exec -T api python -c "\
from app.services.context_manager import get_or_create_context; \
ctx = get_or_create_context('test'); \
ctx.add_turn('user', 'test'); \
print(f'Context turns: {len(ctx.turns)}'); \
print('✓ Context manager OK')"
	@echo ""
	@echo "=== Phase 2 升级完成 ==="
	@echo "新增功能:"
	@echo "  - 对话上下文管理（实体跟踪、偏好记忆、历史压缩）"
	@echo "  - 计算引擎（设备数量、精度校验、成本/ROI计算）"
	@echo "  - 反馈优化器（反馈检测、统计分析、Prompt增强）"
	@echo ""

# Phase 3 升级（结构化参数）
upgrade-phase3:
	@echo "=== Phase 3 升级: 结构化参数 ==="
	$(COMPOSE) run --rm api alembic upgrade head || true
	$(COMPOSE) build --no-cache api
	$(COMPOSE) up -d api
	@sleep 5
	@echo ""
	@echo "验证新模块..."
	$(COMPOSE) exec -T api python -c "\
from app.services.param_extractor import extract_params; \
params = extract_params('功率500W的AOI设备，精度0.01mm'); \
print(f'提取参数: {len(params)}个'); \
assert len(params) >= 2, 'Param extraction failed'; \
print('✓ Param extractor OK')"
	@echo ""
	$(COMPOSE) exec -T api python -c "\
from app.services.retrieval import smart_search; \
result = smart_search('功率500W的设备'); \
print(f'搜索策略: {result.get(\"strategy\")}'); \
print('✓ Smart search OK')"
	@echo ""
	$(COMPOSE) exec -T api python -c "\
from app.services.calculation_engine import compare_specs; \
products = [{'name': 'A', 'params': [{'name': 'power', 'value': 500}]}, {'name': 'B', 'params': [{'name': 'power', 'value': 600}]}]; \
result = compare_specs(products); \
print(f'比对结果: {result.success}'); \
print('✓ Spec comparator OK')"
	@echo ""
	@echo "=== Phase 3 升级完成 ==="
	@echo "新增功能:"
	@echo "  - 参数提取器（从查询提取参数需求）"
	@echo "  - 智能搜索（根据查询类型选择策略）"
	@echo "  - 参数化检索（参数值过滤和范围查询）"
	@echo "  - 规格比对（多产品参数对比）"
	@echo ""
	@echo "调试接口:"
	@echo "  POST /v1/debug/extract-params    - 测试参数提取"
	@echo "  POST /v1/debug/smart-search      - 智能搜索"
	@echo "  POST /v1/debug/search-by-params  - 参数化搜索"
	@echo "  POST /v1/debug/compare-specs     - 规格比对"
	@echo ""
	@echo ""

# Phase 4 升级（优化闭环）
upgrade-phase4:
	@echo "=== Phase 4 升级: 优化闭环 ==="
	$(COMPOSE) build api
	$(COMPOSE) up -d api
	@sleep 5
	@echo ""
	@echo "验证新模块..."
	$(COMPOSE) exec -T api python -c "\
from app.services.scenario_switch_detector import detect_scenario_switch; \
result = detect_scenario_switch('换个话题', ['之前的问题']); \
print(f'场景切换: {result.switch_type.value}'); \
print('✓ 场景切换检测 OK')"
	@echo ""
	$(COMPOSE) exec -T api python -c "\
from app.services.feedback_analyzer import analyze_feedback; \
report = analyze_feedback(days=1); \
print(f'健康评分: {report.health_score:.0f}'); \
print('✓ 反馈分析 OK')"
	@echo ""
	$(COMPOSE) exec -T api python -c "\
from app.services.quality_monitor import get_health_status; \
health = get_health_status(); \
print(f'系统健康: {health.healthy}, 评分: {health.score:.0f}'); \
print('✓ 质量监控 OK')"
	@echo ""
	@echo "=== Phase 4 升级完成 ==="
	@echo "新增功能:"
	@echo "  - 场景切换检测（话题转换、追问、澄清识别）"
	@echo "  - 反馈分析报表（模式识别、改进建议）"
	@echo "  - 自动Prompt优化（Few-shot生成）"
	@echo "  - 质量监控仪表盘（指标跟踪、告警）"
	@echo ""
	@echo "调试接口:"
	@echo "  POST /v1/debug/detect-switch          - 场景切换检测"
	@echo "  GET  /v1/debug/feedback-report        - 反馈分析"
	@echo "  GET  /v1/debug/optimization-suggestions - 优化建议"
	@echo "  GET  /v1/debug/health                 - 健康状态"
	@echo "  GET  /v1/debug/dashboard              - 监控仪表盘"
	@echo ""

# Phase 5 升级 - 智能能力扩展
upgrade-phase5:
	@echo "=== Phase 5 升级: 智能能力扩展 ==="
	$(COMPOSE) run --rm api alembic upgrade head || true
	$(COMPOSE) up -d neo4j || true
	$(COMPOSE) build api
	$(COMPOSE) up -d api
	@sleep 5
	@echo ""
	@echo "验证新模块..."
	$(COMPOSE) exec -T api python -c "\
from app.services.vision_service import get_vision_service; \
print('✓ VisionService OK')"
	$(COMPOSE) exec -T api python -c "\
from app.services.knowledge_graph import get_knowledge_graph; \
print('✓ KnowledgeGraph OK')"
	$(COMPOSE) exec -T api python -c "\
from app.services.recommendation_engine import get_recommendation_engine; \
print('✓ RecommendationEngine OK')"
	$(COMPOSE) exec -T api python -c "\
from app.services.summary_service import get_summary_service; \
print('✓ SummaryService OK')"
	@echo ""
	@echo "=== Phase 5 升级完成 ==="
	@echo "新增功能:"
	@echo "  - 多模态理解（图片问答、表格提取、OCR）"
	@echo "  - 知识图谱（实体/关系抽取、图谱查询）"
	@echo "  - 智能推荐（热门、协同过滤、个性化）"
	@echo "  - 对话摘要（自动摘要、历史压缩）"
	@echo ""
	@echo "新增 API:"
	@echo "  POST /v1/vision/analyze         - 图片分析"
	@echo "  GET  /v1/kg/query              - 知识图谱查询"
	@echo "  GET  /v1/recommend             - 获取推荐"
	@echo "  POST /v1/summary/generate      - 生成摘要"
	@echo ""
	@echo "服务端口:"
	@echo "  Neo4j Browser: http://localhost:7474"
	@echo ""

# 验证 Phase 2 升级
verify-phase2:
	python scripts/upgrade_phase2.py --verify-only

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
	@echo "    make upgrade-phase2   - 升级到Phase2（上下文+计算+反馈）"
	@echo "    make upgrade-phase3   - 升级到Phase3（结构化参数）"
	@echo "    make upgrade-phase4   - 升级到Phase4（优化闭环）"
	@echo "    make upgrade-phase5   - 升级到Phase5（智能能力扩展）"
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
