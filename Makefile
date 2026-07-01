# =============================================================================
# Kairon Frete — Makefile
# Alvos são a interface única de dev. `make help` lista tudo.
# =============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash

# Roda comandos python dentro do venv do poetry.
PY := poetry run

.PHONY: help
help: ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Instala dependências (poetry) + pre-commit hooks
	poetry install --with dev,ui
	$(PY) pre-commit install

.PHONY: lint
lint: ## Ruff lint + format check
	$(PY) ruff check src tests ui scripts
	$(PY) ruff format --check src tests ui scripts

.PHONY: fmt
fmt: ## Ruff auto-format + fix
	$(PY) ruff format src tests ui scripts
	$(PY) ruff check --fix src tests ui scripts

.PHONY: typecheck
typecheck: ## mypy
	$(PY) mypy src tests

.PHONY: test
test: ## pytest com cobertura (falha se < 70%)
	$(PY) pytest

.PHONY: run-api
run-api: ## Sobe a API FastAPI local (hot reload) em :8000
	$(PY) uvicorn kairon.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run-ui
run-ui: ## Sobe a UI Streamlit local em :8501
	$(PY) streamlit run ui/app.py --server.port 8501

.PHONY: etl-anp
etl-anp: ## Roda o ETL ANP uma vez (baixa CSV, normaliza, grava)
	$(PY) python -m kairon.ingestion.flows.anp_flow

.PHONY: db-migrate
db-migrate: ## Aplica migrations Alembic (upgrade head)
	$(PY) alembic upgrade head

.PHONY: db-revision
db-revision: ## Cria migration vazia: make db-revision m="mensagem"
	$(PY) alembic revision -m "$(m)"

.PHONY: seed
seed: ## Popula Postgres com dados sintéticos
	$(PY) python scripts/seed_synthetic_data.py

.PHONY: docker-up
docker-up: ## Sobe toda a stack (api, ui, worker, postgres, redis)
	docker compose up -d --build

.PHONY: docker-down
docker-down: ## Derruba a stack (mantém volumes)
	docker compose down

.PHONY: docker-nuke
docker-nuke: ## Derruba a stack E apaga volumes (reset total)
	docker compose down -v
