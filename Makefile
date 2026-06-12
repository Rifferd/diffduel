# DiffDuel — корневой Makefile.
# Цели с ##-комментарием попадают в `make help` (цель по умолчанию).

COMPOSE_FILE := infra/compose/docker-compose.yml
API_DIR      := apps/api

.DEFAULT_GOAL := help

.PHONY: help up down logs ps api-install api-lint api-test api-dev

help: ## Показать список доступных целей
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ───────────────────────── Инфраструктура (compose) ─────────────────────────

up: ## Поднять dev-стек (postgres, redis, redpanda, minio) в фоне
	docker compose -f $(COMPOSE_FILE) up -d

down: ## Остановить dev-стек (данные в volumes сохраняются)
	docker compose -f $(COMPOSE_FILE) down

logs: ## Хвост логов всех сервисов стека
	docker compose -f $(COMPOSE_FILE) logs -f --tail=100

ps: ## Статус контейнеров стека
	docker compose -f $(COMPOSE_FILE) ps

# ───────────────────────── Core API (apps/api, uv) ─────────────────────────

api-install: ## Установить зависимости API (uv sync --dev)
	cd $(API_DIR) && uv sync --dev

api-lint: ## Линт API: ruff check + ruff format --check + mypy src
	cd $(API_DIR) && uv run ruff check .
	cd $(API_DIR) && uv run ruff format --check .
	cd $(API_DIR) && uv run mypy src

api-test: ## Тесты API (pytest)
	cd $(API_DIR) && uv run pytest

api-dev: ## Запустить API в dev-режиме (uvicorn --reload на :8000)
	cd $(API_DIR) && uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
