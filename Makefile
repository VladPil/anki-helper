.PHONY: help init check-env up down restart ps build logs dev dev-frontend dev-agent test lint migrate clean

# =============================================================================
# Конфигурация
# =============================================================================
DOCKER_DIR := .docker
COMPOSE_FILE := $(DOCKER_DIR)/compose/docker-compose.yml
COMPOSE_PROD := $(DOCKER_DIR)/compose/docker-compose.prod.yml
COMPOSE_MON := $(DOCKER_DIR)/compose/docker-compose.monitoring.yml
COMPOSE_AGENT := $(DOCKER_DIR)/compose/docker-compose.agent.yml
ENV_FILE := .env
ENV_EXAMPLE := $(DOCKER_DIR)/configs/env/.env.example

# Docker compose команда
DC := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)
DC_PROD := docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_PROD) --env-file $(ENV_FILE)
DC_MON := docker compose -f $(COMPOSE_MON) --env-file $(ENV_FILE)
DC_AGENT := docker compose -f $(COMPOSE_AGENT) --env-file $(ENV_FILE)

# Цвета
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
CYAN := \033[0;36m
NC := \033[0m

# =============================================================================
# Проверка .env
# =============================================================================
check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)✗ Файл .env не найден!$(NC)"; \
		echo "$(YELLOW)→ Выполните: make init$(NC)"; \
		exit 1; \
	fi

# =============================================================================
# Help
# =============================================================================
help:
	@echo "$(CYAN)╔══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(CYAN)║                        AnkiRAG Makefile                          ║$(NC)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Инициализация:$(NC)"
	@echo "  make init              Создать .env из шаблона"
	@echo ""
	@echo "$(GREEN)Docker (требуется .env):$(NC)"
	@echo "  make up                Запустить все (backend + frontend + infra)"
	@echo "  make up-infra          Только инфраструктура (postgres, redis)"
	@echo "  make up-backend        Backend + инфраструктура"
	@echo "  make up-monitoring     Добавить мониторинг"
	@echo "  make down              Остановить все"
	@echo "  make restart           Перезапустить"
	@echo "  make ps                Статус сервисов"
	@echo "  make build             Собрать образы"
	@echo ""
	@echo "$(GREEN)Локальная разработка (без Docker):$(NC)"
	@echo "  make dev               Backend (uvicorn с hot-reload)"
	@echo "  make dev-frontend      Frontend (vite)"
	@echo "  make dev-agent         Local-agent (PyQt6)"
	@echo ""
	@echo "$(GREEN)Логи:$(NC)"
	@echo "  make logs              Все логи"
	@echo "  make logs-backend      Backend"
	@echo "  make logs-frontend     Frontend"
	@echo "  make logs-db           PostgreSQL"
	@echo ""
	@echo "$(GREEN)База данных:$(NC)"
	@echo "  make migrate           Применить миграции"
	@echo "  make migration name=x  Создать миграцию"
	@echo "  make migrate-down      Откатить миграцию"
	@echo "  make db-shell          PostgreSQL shell"
	@echo "  make redis-cli         Redis CLI"
	@echo ""
	@echo "$(GREEN)Тесты:$(NC)"
	@echo "  make test              Все тесты"
	@echo "  make test-unit         Unit тесты"
	@echo "  make test-cov          С coverage"
	@echo ""
	@echo "$(GREEN)Code Quality:$(NC)"
	@echo "  make lint              Проверка (ruff)"
	@echo "  make format            Форматирование"
	@echo "  make typecheck         Типы (mypy)"
	@echo ""
	@echo "$(GREEN)Production:$(NC)"
	@echo "  make prod              Запуск production"
	@echo "  make prod-logs         Production логи"
	@echo ""
	@echo "$(GREEN)Очистка:$(NC)"
	@echo "  make clean             Удалить volumes"
	@echo "  make clean-all         Полная очистка"
	@echo ""

# =============================================================================
# Инициализация
# =============================================================================
init:
	@if [ -f $(ENV_FILE) ]; then \
		echo "$(YELLOW)Файл .env уже существует. Перезаписать? [y/N]$(NC)"; \
		read answer; \
		if [ "$$answer" != "y" ] && [ "$$answer" != "Y" ]; then \
			echo "Отменено."; \
			exit 0; \
		fi; \
	fi
	@cp $(ENV_EXAMPLE) $(ENV_FILE)
	@echo "$(GREEN)✓ Создан .env из шаблона$(NC)"
	@echo "$(YELLOW)→ Отредактируйте .env под ваше окружение$(NC)"

# =============================================================================
# Docker - Запуск
# =============================================================================
up: check-env
	@echo "$(GREEN)Запуск всех сервисов...$(NC)"
	$(DC) up -d

up-infra: check-env
	@echo "$(GREEN)Запуск инфраструктуры...$(NC)"
	$(DC) up -d postgres redis

up-backend: check-env
	@echo "$(GREEN)Запуск backend + инфраструктура...$(NC)"
	$(DC) up -d postgres redis backend

up-frontend: check-env
	@echo "$(GREEN)Запуск frontend...$(NC)"
	$(DC) up -d frontend

up-monitoring: check-env
	@echo "$(GREEN)Запуск мониторинга...$(NC)"
	$(DC) up -d
	$(DC_MON) up -d

down:
	@echo "$(YELLOW)Остановка сервисов...$(NC)"
	-$(DC) down 2>/dev/null
	-$(DC_MON) down 2>/dev/null

restart: down up

ps: check-env
	$(DC) ps

build: check-env
	$(DC) build

# =============================================================================
# Локальная разработка (без Docker)
# =============================================================================
dev: check-env
	@echo "$(GREEN)Запуск backend локально...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "$(GREEN)Запуск frontend локально...$(NC)"
	cd frontend && npm run dev

dev-agent: check-env
	@echo "$(GREEN)Запуск local-agent локально...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd local-agent && uv run python -m src.main

# =============================================================================
# Логи
# =============================================================================
logs: check-env
	$(DC) logs -f

logs-backend: check-env
	$(DC) logs -f backend

logs-frontend: check-env
	$(DC) logs -f frontend

logs-db: check-env
	$(DC) logs -f postgres

logs-redis: check-env
	$(DC) logs -f redis

# =============================================================================
# База данных
# =============================================================================
ALEMBIC_CFG := src/migrations/alembic.ini

migrate: check-env
	@echo "$(GREEN)Применение миграций...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m alembic -c $(ALEMBIC_CFG) upgrade head

migration: check-env
ifndef name
	$(error $(RED)Укажите имя: make migration name="add_users"$(NC))
endif
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m alembic -c $(ALEMBIC_CFG) revision --autogenerate -m "$(name)"

migrate-down: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m alembic -c $(ALEMBIC_CFG) downgrade -1

db-shell: check-env
	$(DC) exec postgres psql -U $${POSTGRES_USER:-ankirag} -d $${POSTGRES_DB:-ankirag}

redis-cli: check-env
	$(DC) exec redis redis-cli

# =============================================================================
# Тесты
# =============================================================================
test: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m pytest src/tests/ -v

test-unit: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m pytest src/tests/unit/ -v

test-integration: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m pytest src/tests/integration/ -v

test-cov: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	uv run python -m pytest src/tests/ -v --cov=src --cov-report=html --cov-report=term

# =============================================================================
# Code Quality
# =============================================================================
lint:
	uv run ruff check src/

format:
	uv run ruff check src/ --fix
	uv run ruff format src/

typecheck:
	uv run mypy src/

# =============================================================================
# Production
# =============================================================================
prod: check-env
	@echo "$(GREEN)Запуск production...$(NC)"
	$(DC_PROD) up -d

prod-build: check-env
	$(DC_PROD) build

prod-logs: check-env
	$(DC_PROD) logs -f

# =============================================================================
# Agent
# =============================================================================
agent: check-env
	$(DC_AGENT) up --build

agent-dev: check-env
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd local-agent && uv run python -m src.main

# =============================================================================
# Очистка
# =============================================================================
clean:
	@echo "$(YELLOW)Остановка и удаление volumes...$(NC)"
	-$(DC) down -v 2>/dev/null
	-$(DC_MON) down -v 2>/dev/null
	docker system prune -f

clean-all:
	@echo "$(RED)ВНИМАНИЕ: Будут удалены ВСЕ контейнеры, volumes и images!$(NC)"
	@echo "Продолжить? [y/N]"
	@read answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		$(DC) down -v --rmi all 2>/dev/null || true; \
		$(DC_MON) down -v --rmi all 2>/dev/null || true; \
		docker system prune -af; \
		echo "$(GREEN)✓ Очистка завершена$(NC)"; \
	else \
		echo "Отменено."; \
	fi

# =============================================================================
# Shell
# =============================================================================
shell: check-env
	$(DC) exec backend bash

shell-frontend: check-env
	$(DC) exec frontend sh
