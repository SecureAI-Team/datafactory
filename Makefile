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
	$(COMPOSE) run --rm api alembic upgrade head
	docker run --rm -v $(PWD):/work -w /work python:3.11-slim python scripts/create_buckets.py
	docker run --rm -v $(PWD):/work -w /work python:3.11-slim python scripts/create_opensearch_index.py
	docker run --rm -v $(PWD):/work -w /work python:3.11-slim python scripts/seed_data.py

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
	./scripts/smoke_test.sh
