# Docker-инфраструктура AnkiRAG

## Структура директории

```
.docker/
├── compose/                    # Docker Compose файлы
│   ├── docker-compose.yml      # Основной (backend + frontend + infra)
│   ├── docker-compose.prod.yml # Production override
│   ├── docker-compose.monitoring.yml  # Мониторинг (Loki, Prometheus, Grafana)
│   └── docker-compose.agent.yml       # PyQt6 локальный агент
│
├── services/                   # Dockerfile'ы
│   ├── backend/
│   │   └── Dockerfile          # Multi-stage (dev + prod)
│   ├── frontend/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   └── local-agent/
│       └── Dockerfile
│
├── configs/
│   ├── env/                    # ENV файлы
│   │   ├── .env.local          # Локальная разработка
│   │   ├── .env.prod           # Production (gitignored)
│   │   └── .env.example        # Шаблон
│   │
│   ├── monitoring/             # Конфиги мониторинга
│   │   ├── prometheus.yml
│   │   ├── loki-config.yml
│   │   └── promtail-config.yml
│   │
│   └── grafana/
│       └── provisioning/
│
├── .dockerignore
└── README.md
```

## Быстрый старт

### Локальная разработка

```bash
# Запуск всех сервисов
make up

# Или напрямую
docker compose -f .docker/compose/docker-compose.yml up -d

# С мониторингом
make up-monitoring
```

### Остановка

```bash
make down
```

## Сервисы

| Сервис     | Порт | Описание                   |
|------------|------|----------------------------|
| PostgreSQL | 5433 | БД с pgvector              |
| Redis      | 6379 | Кэширование                |
| Backend    | 8000 | FastAPI API                |
| Frontend   | 5173 | Vite dev server            |
| Debugger   | 5678 | Python debugger (debugpy)  |

### Мониторинг (опционально)

| Сервис     | Порт | Описание           |
|------------|------|--------------------|
| Grafana    | 3000 | Дашборды           |
| Prometheus | 9090 | Метрики            |
| Loki       | 3100 | Логи               |

## Конфигурация

### ENV файлы

Все файлы находятся в `.docker/configs/env/`:

| Файл          | Назначение                    |
|---------------|-------------------------------|
| `.env.local`  | Локальная разработка          |
| `.env.prod`   | Production (не в git)         |
| `.env.example`| Шаблон для создания новых env |

### Создание production конфига

```bash
cp .docker/configs/env/.env.example .docker/configs/env/.env.prod
# Отредактировать значения
```

## Makefile команды

```bash
# Docker
make up              # Запуск сервисов
make up-monitoring   # + мониторинг
make down            # Остановка
make ps              # Статус
make build           # Сборка образов

# Разработка
make dev             # Запуск с билдом (foreground)
make dev-d           # Запуск с билдом (detached)
make dev-backend     # Только backend + infra

# Логи
make logs            # Все логи
make logs-backend    # Backend логи

# База данных
make migrate         # Применить миграции
make migration name="add_users"  # Создать миграцию
make db-shell        # PostgreSQL shell
make redis-cli       # Redis CLI

# Тесты
make test            # Все тесты
make test-unit       # Unit тесты
make test-cov        # С coverage

# Code quality
make lint            # Проверка кода
make format          # Форматирование
make typecheck       # Проверка типов

# Production
make prod            # Запуск production
make prod-logs       # Production логи

# Agent
make agent           # Локальный агент (Docker)
make agent-dev       # Локальный агент (native)

# Очистка
make clean           # Остановить и удалить volumes
make clean-all       # Полная очистка
```

## Production

```bash
# Запуск production стека
docker compose -f .docker/compose/docker-compose.yml \
               -f .docker/compose/docker-compose.prod.yml up -d

# Или через make
make prod
```

## Бэкапы

```bash
# Создать бэкап БД
docker compose -f .docker/compose/docker-compose.yml \
               -f .docker/compose/docker-compose.prod.yml \
               --profile backup run backup
```

Бэкапы сохраняются в `.docker/backups/`.
