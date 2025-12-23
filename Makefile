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
	docker run --rm --entrypoint htpasswd httpd:2 -Bbn $(BASIC_AUTH_USER) $(BASIC_AUTH_PASS) > infra/nginx/.htpasswd
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
	./scripts/smoke_test.sh
