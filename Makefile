COMPOSE=docker-compose
export

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

init:
	$(COMPOSE) up -d postgres minio opensearch
	./scripts/wait_for.sh postgres 5432
	./scripts/wait_for.sh opensearch 9200
	./scripts/wait_for.sh minio 9000
	$(COMPOSE) run --rm api alembic upgrade head
	python scripts/create_buckets.py
	python scripts/create_opensearch_index.py
	python scripts/seed_data.py

reset:
	$(COMPOSE) down -v

seed-demo:
	python scripts/seed_data.py

test:
	$(COMPOSE) run --rm api pytest -q

eval:
	$(COMPOSE) run --rm api promptfoo eval --config services/eval/promptfoo.yaml

lint:
	$(COMPOSE) run --rm api ruff check .

smoke:
	./scripts/smoke_test.sh
