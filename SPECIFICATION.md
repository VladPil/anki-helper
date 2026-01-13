# AnkiRAG - Техническая Спецификация

> **Версия**: 1.0.0
> **Дата**: Январь 2026
> **Статус**: В разработке

---

## Содержание

1. [Обзор проекта](#1-обзор-проекта)
2. [Архитектура системы](#2-архитектура-системы)
3. [Структура проекта](#3-структура-проекта)
4. [Модели данных](#4-модели-данных)
5. [API Reference](#5-api-reference)
6. [Бизнес-процессы](#6-бизнес-процессы)
7. [Интеграции](#7-интеграции)
8. [Технологический стек](#8-технологический-стек)
9. [Развёртывание](#9-развёртывание)
10. [Конфигурация](#10-конфигурация)

---

## 1. Обзор проекта

### 1.1 Назначение

**AnkiRAG** — интеллектуальная система для автоматической генерации учебных карточек Anki с использованием технологий искусственного интеллекта.

### 1.2 Ключевые возможности

| Функция | Описание |
|---------|----------|
| **AI-генерация карточек** | Автоматическое создание карточек по заданной теме с использованием LLM |
| **RAG-поиск** | Семантический поиск по существующим карточкам для контекста и предотвращения дубликатов |
| **Проверка фактов** | Верификация сгенерированного контента через Perplexity AI |
| **Чат с контекстом** | Интерактивный чат с RAG для изучения материалов |
| **Синхронизация с Anki** | Двусторонняя синхронизация через AnkiConnect |
| **Импорт .apkg** | Загрузка существующих колод из Anki |
| **Иерархические колоды** | Древовидная структура колод с неограниченной вложенностью |
| **Шаблоны карточек** | Кастомизируемые шаблоны (Basic, Cloze, Custom) |
| **Управление промптами** | Версионируемые промпты для генерации |

### 1.3 Целевая аудитория

- Студенты и преподаватели
- Самообучающиеся специалисты
- Создатели образовательного контента
- Пользователи Anki, желающие автоматизировать создание карточек

---

## 2. Архитектура системы

### 2.1 Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              КЛИЕНТЫ                                        │
├─────────────────┬─────────────────────┬─────────────────────────────────────┤
│   Web Frontend  │    Local Agent      │           External API              │
│   (Vue 3 SPA)   │  (PyQt6 Desktop)    │         (REST/SSE)                  │
└────────┬────────┴──────────┬──────────┴──────────────┬──────────────────────┘
         │                   │                         │
         └───────────────────┼─────────────────────────┘
                             │ HTTPS/WSS
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY                                        │
│                        (FastAPI + Uvicorn)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Auth  │  Users  │  Decks  │  Cards  │  Generation  │  Chat  │  Sync  │ RAG │
└────────┴─────────┴─────────┴─────────┴──────────────┴────────┴────────┴─────┘
                             │
         ┌───────────────────┼───────────────────┬───────────────────┐
         ▼                   ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │     Redis       │ │   ARQ Worker    │ │    SOP_LLM      │
│   + pgvector    │ │   (Cache/MQ)    │ │  (Background)   │ │   (LLM API)     │
└─────────────────┘ └────────┬────────┘ └────────┬────────┘ └─────────────────┘
                             │                   │                 │
                             └───────────────────┘                 │
                                    ▲                              │
                                    │ jobs                         │
                                    └──────────────────────────────┘
                                                   │
                             ┌─────────────────────┼─────────────────┐
                             ▼                     ▼                 ▼
                      ┌───────────┐         ┌───────────┐     ┌───────────┐
                      │  OpenAI   │         │ Anthropic │     │ Perplexity│
                      └───────────┘         └───────────┘     └───────────┘
```

### 2.2 Компоненты системы

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Backend API** | FastAPI | REST API, SSE streaming, бизнес-логика |
| **Frontend** | Vue 3 + Vite | SPA веб-интерфейс |
| **Local Agent** | PyQt6 | Desktop-приложение для синхронизации с Anki |
| **Database** | PostgreSQL 16 + pgvector | Хранение данных и векторный поиск |
| **Cache** | Redis 7 | Кэширование, очереди задач |
| **Task Queue** | ARQ | Фоновые задачи (генерация, синхронизация) |
| **LLM Gateway** | SOP_LLM | Унифицированный доступ к LLM провайдерам |

### 2.3 Паттерны проектирования

- **Layered Architecture** — разделение на слои (API, Modules, Services, Core)
- **Repository Pattern** — абстракция доступа к данным
- **Service Layer** — инкапсуляция бизнес-логики
- **Dependency Injection** — FastAPI Depends
- **Event-Driven** — SSE для real-time обновлений
- **CQRS** — разделение команд и запросов в генерации

### 2.4 Task Queue (ARQ)

Для выполнения долгих операций используется [ARQ](https://arq-docs.helpmanual.io/) — асинхронная очередь задач на базе Redis.

**Задачи, обрабатываемые через очередь:**
- Генерация карточек (долгие LLM вызовы)
- Синхронизация с Anki
- Индексация embeddings при импорте .apkg

**Преимущества:**
- Не блокирует API при долгих операциях
- Автоматические retry при ошибках
- Возможность отслеживания прогресса через SSE

---

## 3. Структура проекта

```
anki-helper/
├── src/                          # Backend (FastAPI)
│   ├── api/                      # REST API маршруты
│   │   ├── __init__.py
│   │   ├── auth.py              # POST /auth/register, /login, /refresh, /logout
│   │   ├── users.py             # GET/PATCH /users/me, [ADMIN] /users/*
│   │   ├── decks.py             # CRUD /decks/*, GET /decks/tree
│   │   ├── cards.py             # CRUD /cards/*, /cards/bulk/*, /cards/{id}/approve
│   │   ├── generation.py        # POST /generate, GET /generate/jobs/*
│   │   ├── chat.py              # /chat/sessions/*, SSE messages
│   │   ├── sync.py              # /sync/push, /sync/pull, /sync/import
│   │   ├── rag.py               # /rag/search, /rag/duplicates, /rag/index
│   │   ├── prompts.py           # CRUD /prompts/*
│   │   ├── templates.py         # CRUD /templates/*
│   │   └── system.py            # /health, /metrics
│   │
│   ├── workers/                  # ARQ workers
│   │   ├── __init__.py
│   │   ├── settings.py           # ARQ configuration
│   │   ├── generation.py         # Card generation tasks
│   │   ├── sync.py               # Anki sync tasks
│   │   └── indexing.py           # Embedding indexing tasks
│   │
│   ├── modules/                  # Бизнес-модули (домены)
│   │   ├── auth/                # Аутентификация
│   │   │   ├── models.py        # RefreshToken
│   │   │   ├── schemas.py       # LoginRequest, TokenResponse
│   │   │   ├── service.py       # AuthService
│   │   │   └── dependencies.py  # get_current_user, require_admin
│   │   │
│   │   ├── users/               # Пользователи
│   │   │   ├── models.py        # User, UserPreferences
│   │   │   ├── schemas.py       # UserCreate, UserResponse
│   │   │   └── service.py       # UserService
│   │   │
│   │   ├── decks/               # Колоды
│   │   │   ├── models.py        # Deck (иерархическая)
│   │   │   ├── schemas.py       # DeckCreate, DeckTreeResponse
│   │   │   └── service.py       # DeckService
│   │   │
│   │   ├── cards/               # Карточки
│   │   │   ├── models.py        # Card, CardGenerationInfo, CardEmbedding
│   │   │   ├── schemas.py       # CardCreate, CardBulkCreate
│   │   │   └── service.py       # CardService
│   │   │
│   │   ├── templates/           # Шаблоны карточек
│   │   │   ├── models.py        # CardTemplate, TemplateField
│   │   │   ├── schemas.py       # TemplateCreate
│   │   │   └── service.py       # TemplateService
│   │   │
│   │   ├── prompts/             # LLM промпты
│   │   │   ├── models.py        # Prompt, PromptExecution
│   │   │   ├── schemas.py       # PromptCreate
│   │   │   └── service.py       # PromptService
│   │   │
│   │   ├── generation/          # Генерация карточек
│   │   │   ├── schemas.py       # GenerationRequest
│   │   │   ├── service.py       # GenerationService
│   │   │   └── workflows/       # LangGraph workflows
│   │   │       ├── card_generator.py
│   │   │       └── fact_checker.py
│   │   │
│   │   ├── chat/                # Чат с RAG
│   │   │   ├── models.py        # ChatSession, ChatMessage
│   │   │   ├── schemas.py       # ChatMessageCreate
│   │   │   ├── service.py       # ChatService
│   │   │   └── workflows/
│   │   │       └── chat_workflow.py
│   │   │
│   │   └── sync/                # Синхронизация с Anki
│   │       ├── schemas.py       # SyncPushRequest, ImportRequest
│   │       ├── service.py       # SyncService
│   │       └── apkg_parser.py   # Парсинг .apkg файлов
│   │
│   ├── services/                # Внешние интеграции
│   │   ├── llm/                 # LLM клиент
│   │   │   ├── client.py        # SopLLMClient
│   │   │   ├── models.py        # LLMModel, EmbeddingModel
│   │   │   └── schemas.py       # LLMResponse
│   │   │
│   │   └── rag/                 # RAG сервис
│   │       ├── service.py       # RAGService
│   │       ├── embeddings.py    # EmbeddingService
│   │       ├── indexer.py       # CardIndexer
│   │       ├── retriever.py     # CardRetriever
│   │       └── schemas.py       # SearchRequest
│   │
│   ├── core/                    # Инфраструктура
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── database.py          # SQLAlchemy async setup
│   │   ├── security.py          # JWT, password hashing
│   │   ├── dependencies.py      # FastAPI dependencies
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── middleware.py        # Request tracing
│   │   ├── logging.py           # Structured logging
│   │   ├── metrics.py           # Prometheus
│   │   └── telemetry.py         # OpenTelemetry
│   │
│   ├── shared/                  # Общие компоненты
│   │   ├── schemas.py           # BaseSchema, PaginatedResponse
│   │   ├── repository.py        # BaseRepository
│   │   ├── mixins.py            # UUIDMixin, TimestampMixin
│   │   ├── uuid7.py             # UUID7 генерация
│   │   └── errors/              # Error handlers
│   │
│   ├── migrations/              # Alembic миграции
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── tests/                   # Тесты
│   │   ├── conftest.py
│   │   ├── unit/
│   │   └── integration/
│   │
│   └── main.py                  # FastAPI application
│
├── frontend/                    # Vue 3 SPA
│   ├── src/
│   │   ├── views/               # Страницы
│   │   ├── components/          # Компоненты
│   │   ├── stores/              # Pinia stores
│   │   ├── api/                 # HTTP клиенты
│   │   └── router/
│   ├── package.json
│   └── vite.config.js
│
├── local-agent/                 # PyQt6 Desktop App
│   ├── src/
│   │   ├── clients/             # AnkiConnect, Backend API
│   │   ├── core/                # Sync logic
│   │   ├── config/
│   │   └── ui/                  # System tray UI
│   └── pyproject.toml
│
├── .docker/                     # Docker конфигурация
│   ├── compose/
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.prod.yml
│   │   └── docker-compose.monitoring.yml
│   ├── services/
│   │   ├── backend/Dockerfile
│   │   └── frontend/Dockerfile
│   └── configs/env/
│
├── Makefile                     # Команды управления
├── pyproject.toml               # Python dependencies
└── .env                         # Environment variables
```

---

## 4. Модели данных

### 4.1 ER-диаграмма

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │ user_preferences│       │ refresh_tokens  │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK, UUID7)  │──┐    │ id (PK)         │       │ id (PK)         │
│ email (UNIQUE)  │  │    │ user_id (FK)────│───────│ user_id (FK)────│──┐
│ hashed_password │  │    │ preferred_lang  │       │ token (UNIQUE)  │  │
│ display_name    │  │    │ default_model   │       │ expires_at      │  │
│ is_active       │  │    │ default_embedder│       │ revoked         │  │
│ created_at      │  │    └─────────────────┘       └─────────────────┘  │
│ deleted_at      │  │                                                   │
└─────────────────┘  │                                                   │
         │           │                                                   │
         │           └───────────────────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐       ┌─────────────────┐
│     decks       │       │     cards       │
├─────────────────┤       ├─────────────────┤
│ id (PK, UUID7)  │──┐    │ id (PK, UUID7)  │──┐
│ name            │  │    │ deck_id (FK)────│──│────┐
│ description     │  │    │ template_id (FK)│  │    │
│ owner_id (FK)───│──│────│ fields (JSONB)  │  │    │
│ parent_id (FK)──│──┘    │ status (ENUM)   │  │    │
│ anki_deck_id    │  self │ tags (ARRAY)    │  │    │
│ created_at      │  ref  │ anki_card_id    │  │    │
│ deleted_at      │       │ created_at      │  │    │
└─────────────────┘       │ deleted_at      │  │    │
         │                └─────────────────┘  │    │
         │                        │            │    │
         └────────────────────────│────────────┘    │
                                  │ 1:1             │
                    ┌─────────────┴──────┐          │
                    ▼                    ▼          │
         ┌─────────────────┐  ┌─────────────────┐   │
         │card_generation_ │  │ card_embeddings │   │
         │     info        │  ├─────────────────┤   │
         ├─────────────────┤  │ id (PK)         │   │
         │ id (PK)         │  │ card_id (FK,UQ) │   │
         │ card_id (FK,UQ) │  │ embedder_id (FK)│   │
         │ prompt_id (FK)  │  │ content_text    │   │
         │ model_id (FK)   │  │ vector (pgvec)  │   │
         │ user_request    │  └─────────────────┘   │
         │ fact_check_res  │                        │
         └─────────────────┘                        │
                                                    │
┌─────────────────┐       ┌─────────────────┐       │
│ card_templates  │       │ template_fields │       │
├─────────────────┤       ├─────────────────┤       │
│ id (PK, UUID7)  │───────│ id (PK)         │       │
│ name (UNIQUE)   │  1:N  │ template_id (FK)│───────┘
│ display_name    │       │ name            │
│ fields_schema   │       │ field_type      │
│ front_template  │       │ is_required     │
│ back_template   │       │ order           │
│ css             │       └─────────────────┘
│ is_system       │
│ owner_id (FK)   │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│    prompts      │       │prompt_executions│
├─────────────────┤       ├─────────────────┤
│ id (PK, UUID7)  │───────│ id (PK)         │
│ name (UNIQUE)   │  1:N  │ prompt_id (FK)  │
│ category (ENUM) │       │ user_id (FK)    │
│ system_prompt   │       │ model_id (FK)   │
│ user_prompt_tpl │       │ rendered_system │
│ variables_schema│       │ rendered_user   │
│ temperature     │       │ variables       │
│ max_tokens      │       │ response_text   │
│ is_active       │       │ input_tokens    │
│ version         │       │ output_tokens   │
│ parent_id (FK)──│───┐   │ latency_ms      │
└─────────────────┘   │   └─────────────────┘
         │            │
         └────────────┘ self-ref (versioning)

┌─────────────────┐       ┌─────────────────┐
│  chat_sessions  │       │  chat_messages  │
├─────────────────┤       ├─────────────────┤
│ id (PK, UUID7)  │───────│ id (PK)         │
│ user_id (FK)    │  1:N  │ session_id (FK) │
│ title           │       │ role (ENUM)     │
│ context (JSONB) │       │ content         │
│ created_at      │       │ tokens          │
│ updated_at      │       │ created_at      │
└─────────────────┘       └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│   llm_models    │       │embedding_models │
├─────────────────┤       ├─────────────────┤
│ id (PK, UUID7)  │       │ id (PK, UUID7)  │
│ provider        │       │ provider        │
│ name            │       │ name            │
│ version         │       │ version         │
│ api_endpoint    │       │ dimensions      │
│ max_tokens      │       │ api_endpoint    │
│ context_window  │       └─────────────────┘
└─────────────────┘
```

### 4.2 Описание таблиц

#### users
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID7 | Первичный ключ |
| email | VARCHAR(255) | Уникальный email |
| hashed_password | VARCHAR(255) | bcrypt хеш пароля |
| display_name | VARCHAR(100) | Отображаемое имя |
| is_active | BOOLEAN | Статус активности |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |
| deleted_at | TIMESTAMP | Soft delete |

#### decks
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID7 | Первичный ключ |
| name | VARCHAR(255) | Название колоды |
| description | TEXT | Описание |
| owner_id | UUID | FK → users.id |
| parent_id | UUID | FK → decks.id (иерархия) |
| anki_deck_id | BIGINT | ID в Anki после синхронизации |
| created_at | TIMESTAMP | Дата создания |
| deleted_at | TIMESTAMP | Soft delete |

#### cards
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID7 | Первичный ключ |
| deck_id | UUID | FK → decks.id |
| template_id | UUID | FK → card_templates.id |
| fields | JSONB | Значения полей карточки |
| status | ENUM | draft/approved/rejected/synced/sync_failed |
| tags | VARCHAR[] | Массив тегов |
| anki_card_id | BIGINT | ID карточки в Anki |
| anki_note_id | BIGINT | ID заметки в Anki |
| sync_error | TEXT | Причина ошибки синхронизации |
| sync_attempts | INTEGER | Количество попыток синхронизации |
| created_by | VARCHAR | Audit: кто создал |
| updated_by | VARCHAR | Audit: кто обновил |

#### card_templates
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID7 | Первичный ключ |
| name | VARCHAR(100) | Уникальное имя (Basic, Cloze) |
| display_name | VARCHAR(255) | Отображаемое имя |
| fields_schema | JSONB | JSON Schema полей |
| front_template | TEXT | HTML/Jinja2 шаблон лицевой стороны |
| back_template | TEXT | HTML/Jinja2 шаблон оборотной стороны |
| css | TEXT | CSS стили |
| is_system | BOOLEAN | Системный (не удаляется) |

#### prompts
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID7 | Первичный ключ |
| name | VARCHAR(100) | Уникальный идентификатор |
| category | ENUM | generation/fact_check/chat/improvement |
| system_prompt | TEXT | System message для LLM |
| user_prompt_template | TEXT | Jinja2 шаблон user message |
| variables_schema | JSONB | JSON Schema переменных |
| temperature | FLOAT | Температура (0.0-2.0) |
| max_tokens | INTEGER | Лимит токенов |
| version | INTEGER | Версия промпта |
| parent_id | UUID | FK → prompts.id (версионирование) |

### 4.3 Статусы карточек

```
┌─────────┐     approve()     ┌──────────┐     sync()     ┌────────┐
│  DRAFT  │ ───────────────▶ │ APPROVED │ ─────────────▶ │ SYNCED │
└─────────┘                   └──────────┘                └────────┘
     │                              │                          ▲
     │ reject()                     │ reject()                 │ retry
     ▼                              ▼                          │
┌──────────┐                  ┌──────────┐               ┌─────────────┐
│ REJECTED │                  │ REJECTED │               │ SYNC_FAILED │
└──────────┘                  └──────────┘               └─────────────┘
                                                               ▲
                                                               │ sync error
                                                               │
                                                         ┌──────────┐
                                                         │ APPROVED │
                                                         └──────────┘
```

---

## 5. API Reference

### 5.1 Аутентификация

Все защищённые эндпоинты требуют заголовок:
```
Authorization: Bearer <access_token>
```

#### POST /api/auth/register
Регистрация нового пользователя.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "display_name": "John Doe"
}
```

**Response (201):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### POST /api/auth/login
Вход в систему.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200):** `TokenResponse`

#### POST /api/auth/refresh
Обновление токенов.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):** `TokenResponse`

#### POST /api/auth/logout
Выход из системы (отзыв refresh token).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "message": "Successfully logged out"
}
```

---

### 5.2 Колоды (Decks)

#### POST /api/decks/
Создание колоды.

**Request:**
```json
{
  "name": "Python Programming",
  "description": "Карточки по Python",
  "parent_id": "uuid-of-parent-deck"  // optional
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Python Programming",
  "description": "Карточки по Python",
  "owner_id": "user-uuid",
  "parent_id": "parent-uuid",
  "cards_count": 0,
  "created_at": "2026-01-12T10:00:00Z"
}
```

#### GET /api/decks/tree
Получение иерархии колод.

**Response (200):**
```json
[
  {
    "id": "root-deck-uuid",
    "name": "Programming",
    "children": [
      {
        "id": "child-deck-uuid",
        "name": "Python",
        "children": []
      }
    ]
  }
]
```

---

### 5.3 Карточки (Cards)

#### POST /api/cards/
Создание карточки.

**Request:**
```json
{
  "deck_id": "deck-uuid",
  "template_id": "template-uuid",
  "fields": {
    "Front": "Что такое list comprehension?",
    "Back": "Синтаксический сахар для создания списков: [x for x in range(10)]"
  },
  "tags": ["python", "syntax"]
}
```

**Response (201):** `CardResponse`

#### POST /api/cards/bulk
Массовое создание карточек.

**Request:**
```json
{
  "deck_id": "deck-uuid",
  "template_id": "template-uuid",
  "cards": [
    {
      "fields": {"Front": "Q1", "Back": "A1"},
      "tags": ["tag1"]
    },
    {
      "fields": {"Front": "Q2", "Back": "A2"},
      "tags": ["tag2"]
    }
  ]
}
```

**Response (201):**
```json
{
  "created": [...],
  "failed": [...],
  "total_created": 2,
  "total_failed": 0
}
```

#### POST /api/cards/{card_id}/approve
Одобрение карточки.

**Response (200):** `CardResponse` со статусом `approved`

#### POST /api/cards/{card_id}/reject
Отклонение карточки.

**Request:**
```json
{
  "reason": "Некорректная информация"
}
```

---

### 5.4 Генерация (Generation)

#### POST /api/generate
Запуск генерации карточек.

**Request:**
```json
{
  "idempotency_key": "client-generated-uuid",  // optional, предотвращает дубли при retry
  "topic": "Async/await в Python",
  "num_cards": 10,
  "deck_id": "deck-uuid",           // optional
  "prompt_id": "prompt-uuid",       // optional
  "language": "ru",
  "difficulty": "intermediate",     // beginner/intermediate/advanced
  "fact_check": true,
  "include_sources": true
}
```

**Поведение idempotency_key:**
- Если `idempotency_key` уже существует и job completed — возвращается существующий результат
- Если job in progress — возвращается текущий статус
- TTL для idempotency keys: 24 часа

**Response (202):**
```json
{
  "job_id": "job-uuid",
  "status": "pending",
  "message": "Generation job created"
}
```

#### GET /api/generate/jobs/{job_id}
Получение статуса и результатов.

**Response (200):**
```json
{
  "id": "job-uuid",
  "status": "completed",
  "progress": 100,
  "total_cards": 10,
  "completed_cards": 10,
  "cards": [...],
  "errors": []
}
```

#### GET /api/generate/stream (SSE)
Потоковая генерация с real-time обновлениями.

**Query параметры:**
- `job_id` — ID задачи генерации
- `resume_from` — (optional) номер карточки для возобновления после reconnect

**Events:**
```
event: progress
data: {"current": 3, "total": 10, "message": "Generating card 3...", "resume_token": "job-uuid:3"}

event: card
data: {"id": "...", "fields": {...}, "fact_check": {...}}

event: complete
data: {"total_created": 10, "total_failed": 0}

event: error
data: {"message": "Generation failed", "code": "LLM_ERROR"}
```

**Возобновление после disconnect:**
```
GET /api/generate/stream?job_id=xxx&resume_from=3
```
Клиент сохраняет `resume_token` из последнего `progress` event и использует его при переподключении.

---

### 5.5 Чат (Chat)

#### POST /api/chat/sessions
Создание сессии чата.

**Request:**
```json
{
  "title": "Изучаем Python",
  "context": {
    "deck_id": "deck-uuid",
    "topic": "async programming"
  }
}
```

#### POST /api/chat/sessions/{session_id}/messages (SSE)
Отправка сообщения с потоковым ответом.

**Request:**
```json
{
  "content": "Объясни разницу между async и threading"
}
```

**Events:**
```
event: content
data: {"chunk": "Основное различие между "}

event: content
data: {"chunk": "async и threading заключается в..."}

event: metadata
data: {"tokens": 150, "sources": [...]}

event: done
data: {"message_id": "msg-uuid"}
```

---

### 5.6 Синхронизация (Sync)

#### POST /api/sync/push
Отправка карточек в Anki.

**Request:**
```json
{
  "card_ids": ["card-uuid-1", "card-uuid-2"]
}
```

**Response (202):**
```json
{
  "task_id": "sync-task-uuid",
  "status": "queued",
  "cards_count": 2
}
```

#### POST /api/sync/import
Импорт .apkg файла.

**Request:** `multipart/form-data`
- `file`: .apkg файл
- `deck_id`: UUID (optional)
- `create_deck`: boolean
- `overwrite`: boolean
- `tags`: string[]

**Response (201):**
```json
{
  "imported_count": 150,
  "deck_id": "created-deck-uuid",
  "cards": [...]
}
```

---

### 5.7 RAG

#### POST /api/rag/search
Семантический поиск по карточкам.

**Request:**
```json
{
  "query": "async await coroutine",
  "top_k": 10,
  "include_sources": true
}
```

**Response (200):**
```json
{
  "results": [
    {
      "card_id": "card-uuid",
      "score": 0.92,
      "fields": {"Front": "...", "Back": "..."},
      "deck_name": "Python"
    }
  ],
  "query": "async await coroutine"
}
```

#### POST /api/rag/duplicates
Проверка на дубликаты.

**Request:**
```json
{
  "card_ids": ["new-card-uuid-1", "new-card-uuid-2"]
}
```

**Response (200):**
```json
{
  "duplicates": [
    {
      "card_id": "new-card-uuid-1",
      "similar_to": "existing-card-uuid",
      "similarity": 0.95
    }
  ]
}
```

---

### 5.8 Rate Limiting

Базовый rate limiting для защиты от случайного abuse (не enterprise-решение).

| Endpoint | Лимит | Описание |
|----------|-------|----------|
| `POST /api/generate` | 10/hour per user | Защита бюджета LLM |
| `POST /api/chat/*/messages` | 60/hour per user | Защита бюджета LLM |
| Остальные | без лимита | |

**Реализация:** простой Redis counter с TTL, middleware в FastAPI.

**При превышении лимита:**
- HTTP 429 Too Many Requests
- Заголовок `Retry-After` с временем до сброса лимита

---

### 5.9 Health Check

#### GET /api/health
Проверка состояния сервиса.

**Response (200):**
```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok",
  "arq_workers": 2
}
```

Если какой-либо компонент недоступен — возвращается HTTP 503 с `"status": "unhealthy"`.

---

## 6. Бизнес-процессы

### 6.1 Регистрация пользователя

```
┌──────────┐      ┌─────────────┐      ┌─────────────┐      ┌──────────┐
│  Client  │      │   AuthAPI   │      │ AuthService │      │    DB    │
└────┬─────┘      └──────┬──────┘      └──────┬──────┘      └────┬─────┘
     │                   │                    │                  │
     │  POST /register   │                    │                  │
     │──────────────────▶│                    │                  │
     │                   │  register(req)     │                  │
     │                   │───────────────────▶│                  │
     │                   │                    │  check email     │
     │                   │                    │─────────────────▶│
     │                   │                    │◀─────────────────│
     │                   │                    │                  │
     │                   │                    │  hash password   │
     │                   │                    │─────┐            │
     │                   │                    │◀────┘            │
     │                   │                    │                  │
     │                   │                    │  create user     │
     │                   │                    │─────────────────▶│
     │                   │                    │◀─────────────────│
     │                   │                    │                  │
     │                   │                    │  create prefs    │
     │                   │                    │─────────────────▶│
     │                   │                    │◀─────────────────│
     │                   │                    │                  │
     │                   │                    │  create tokens   │
     │                   │                    │─────────────────▶│
     │                   │◀───────────────────│◀─────────────────│
     │  TokenResponse    │                    │                  │
     │◀──────────────────│                    │                  │
```

### 6.2 Генерация карточек

```
┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌───────┐    ┌─────┐
│  Client  │    │ GenAPI    │    │ GenService  │    │  RAG  │    │ LLM │
└────┬─────┘    └─────┬─────┘    └──────┬──────┘    └───┬───┘    └──┬──┘
     │                │                 │               │          │
     │ POST /generate │                 │               │          │
     │───────────────▶│                 │               │          │
     │                │  create_job()   │               │          │
     │                │────────────────▶│               │          │
     │  {job_id}      │◀────────────────│               │          │
     │◀───────────────│                 │               │          │
     │                │                 │               │          │
     │                │     ┌───────────┴───────────┐   │          │
     │                │     │   Background Task     │   │          │
     │                │     └───────────┬───────────┘   │          │
     │                │                 │               │          │
     │                │                 │ get_context() │          │
     │                │                 │──────────────▶│          │
     │                │                 │◀──────────────│          │
     │                │                 │               │          │
     │                │                 │         generate()       │
     │                │                 │─────────────────────────▶│
     │                │                 │◀─────────────────────────│
     │                │                 │               │          │
     │                │                 │ check_dups()  │          │
     │                │                 │──────────────▶│          │
     │                │                 │◀──────────────│          │
     │                │                 │               │          │
     │                │                 │       fact_check()       │
     │                │                 │─────────────────────────▶│
     │                │                 │◀─────────────────────────│
     │                │                 │               │          │
     │                │                 │  save_cards() │          │
     │                │                 │──────┐        │          │
     │                │                 │◀─────┘        │          │
     │                │                 │               │          │
     │ GET /jobs/{id} │                 │               │          │
     │───────────────▶│                 │               │          │
     │  {cards: [...]}│                 │               │          │
     │◀───────────────│                 │               │          │
```

### 6.3 Синхронизация с Anki

```
┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌─────────────┐
│  Client  │    │  SyncAPI  │    │ SyncService │    │ AnkiConnect │
└────┬─────┘    └─────┬─────┘    └──────┬──────┘    └──────┬──────┘
     │                │                 │                  │
     │ POST /push     │                 │                  │
     │───────────────▶│                 │                  │
     │                │  push_cards()   │                  │
     │                │────────────────▶│                  │
     │                │                 │                  │
     │                │                 │  validate cards  │
     │                │                 │──────┐           │
     │                │                 │◀─────┘           │
     │                │                 │                  │
     │  {task_id}     │◀────────────────│                  │
     │◀───────────────│                 │                  │
     │                │                 │                  │
     │ POST /execute  │                 │                  │
     │───────────────▶│                 │                  │
     │                │  sync_to_anki() │                  │
     │                │────────────────▶│                  │
     │                │                 │                  │
     │                │                 │  createDeck()    │
     │                │                 │─────────────────▶│
     │                │                 │◀─────────────────│
     │                │                 │                  │
     │                │                 │  addNotes()      │
     │                │                 │─────────────────▶│
     │                │                 │◀─────────────────│
     │                │                 │                  │
     │                │                 │  update status   │
     │                │                 │──────┐           │
     │                │                 │◀─────┘           │
     │                │                 │                  │
     │  SyncResult    │◀────────────────│                  │
     │◀───────────────│                 │                  │
```

### 6.4 Обработка ошибок синхронизации с Anki

**Сценарии:**

1. **AnkiConnect недоступен**
   - Задача уходит в retry queue
   - 3 попытки с exponential backoff: 1m, 5m, 15m
   - После исчерпания retry — статус `sync_failed`

2. **Partial failure** (часть карточек синхронизировалась)
   - Успешные карточки получают статус `synced`
   - Неуспешные — `sync_failed` с причиной в поле `sync_error`

3. **Rollback не делаем**
   - Слишком сложно для проекта такого масштаба
   - Вместо этого показываем пользователю что синхронизировалось, а что нет

**Дополнительные поля в модели cards:**

| Поле | Тип | Описание |
|------|-----|----------|
| sync_error | TEXT | Причина ошибки синхронизации |
| sync_attempts | INTEGER | Количество попыток синхронизации |

### 6.5 Обработка ошибок LLM

**Retry policy:**
- 3 попытки с exponential backoff: 1s, 3s, 10s
- Timeout: 60s на один LLM вызов

**При исчерпании retry:**
- Job переходит в статус `failed`
- Частично сгенерированные карточки сохраняются со статусом `draft`
- Пользователь может запустить генерацию заново или использовать частичный результат

---

## 7. Интеграции

### 7.1 SOP_LLM (LLM Gateway)

**Назначение:** Унифицированный доступ к различным LLM провайдерам.

**Поддерживаемые провайдеры:**
- OpenAI (GPT-4, GPT-4o, GPT-3.5-turbo)
- Anthropic (Claude 3, Claude 3.5)
- Local GGUF models
- Perplexity AI (fact-checking)

**API Client:** `src/services/llm/client.py`

```python
class SopLLMClient:
    async def complete(prompt: str, model: str) -> str
    async def stream(prompt: str, model: str) -> AsyncIterator[str]
    async def structured(prompt: str, schema: dict) -> dict
    async def embed(text: str, model: str) -> list[float]
    async def fact_check(claim: str) -> FactCheckResult
```

**Конфигурация:**
```env
SOP_LLM_API_BASE_URL=http://localhost:8001
SOP_LLM_TIMEOUT=300
SOP_LLM_DEFAULT_MODEL=gpt-4o
SOP_LLM_DEFAULT_TEMPERATURE=0.7
```

### 7.2 RAG Service

**Назначение:** Семантический поиск и предотвращение дубликатов.

**Компоненты:**
- `EmbeddingService` — генерация векторных представлений
- `CardIndexer` — индексация карточек в pgvector
- `CardRetriever` — поиск похожих карточек

**Алгоритм поиска:**
1. Генерация embedding для запроса
2. Cosine similarity поиск в pgvector
3. Ранжирование по score
4. Фильтрация по threshold (0.7 по умолчанию)

**Конфигурация:**
```env
EMBEDDING_MODEL=multilingual-e5-large
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=100
```

### 7.3 AnkiConnect

**Назначение:** Двусторонняя синхронизация с Anki.

**Требования:**
- Anki Desktop установлен и запущен
- AnkiConnect addon (код: 2055492159)

**API Endpoint:** `http://localhost:8765`

**Поддерживаемые операции:**
| Операция | Описание |
|----------|----------|
| `deckNames` | Получить список колод |
| `createDeck` | Создать колоду |
| `addNote` | Добавить карточку |
| `updateNote` | Обновить карточку |
| `findNotes` | Поиск заметок |
| `sync` | Синхронизация с AnkiWeb |

### 7.4 .apkg Parser

**Назначение:** Импорт существующих колод из Anki.

**Формат .apkg:**
```
archive.apkg (ZIP)
├── collection.anki2    # SQLite база данных
├── collection.anki21   # Для новых версий
└── media/              # Медиафайлы
    ├── 0               # Изображения
    ├── 1               # Аудио
    └── ...
```

**Извлекаемые данные:**
- Структура колод
- Заметки и карточки
- Шаблоны (note types)
- Теги
- Медиафайлы

---

## 8. Технологический стек

### 8.1 Backend

| Технология | Версия | Назначение |
|------------|--------|------------|
| Python | 3.12+ | Язык программирования |
| FastAPI | 0.115+ | Web framework |
| Uvicorn | 0.32+ | ASGI server |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.18+ | Миграции БД |
| Pydantic | 2.9+ | Валидация данных |
| LangGraph | 0.2+ | LLM workflows |
| httpx | 0.27+ | Async HTTP client |
| python-jose | 3.3+ | JWT токены |
| passlib | 1.7+ | Хеширование паролей |
| structlog | 24.4+ | Логирование |

### 8.2 Database

| Технология | Версия | Назначение |
|------------|--------|------------|
| PostgreSQL | 16+ | Основная БД |
| pgvector | 0.7+ | Векторный поиск |
| Redis | 7+ | Кэширование |

### 8.3 Frontend

| Технология | Версия | Назначение |
|------------|--------|------------|
| Vue.js | 3.4+ | UI framework |
| Vite | 5.0+ | Build tool |
| Pinia | 2.1+ | State management |
| Vue Router | 4.2+ | Routing |
| Axios | 1.6+ | HTTP client |
| TailwindCSS | 3.4+ | Стили |
| DaisyUI | 4.4+ | UI компоненты |

### 8.4 Local Agent

| Технология | Версия | Назначение |
|------------|--------|------------|
| PyQt6 | 6.6+ | GUI framework |
| httpx | 0.27+ | HTTP client |
| keyring | 24+ | Secure storage |

### 8.5 DevOps

| Технология | Версия | Назначение |
|------------|--------|------------|
| Docker | 24+ | Контейнеризация |
| Docker Compose | 2.20+ | Оркестрация |
| uv | 0.4+ | Package manager |
| Ruff | 0.8+ | Linter/Formatter |
| pytest | 8.0+ | Тестирование |
| mypy | 1.13+ | Type checking |

### 8.6 Observability

| Технология | Назначение |
|------------|------------|
| OpenTelemetry | Distributed tracing |
| Prometheus | Метрики |
| Grafana | Визуализация |
| Loki | Логи |

---

## 9. Развёртывание

### 9.1 Требования

**Hardware:**
- CPU: 2+ cores
- RAM: 4GB+ (8GB рекомендуется)
- Disk: 20GB+

**Software:**
- Docker 24+
- Docker Compose 2.20+
- Make

### 9.2 Быстрый старт

```bash
# 1. Клонирование репозитория
git clone https://github.com/your-org/anki-helper.git
cd anki-helper

# 2. Инициализация окружения
make init

# 3. Редактирование .env (опционально)
nano .env

# 4. Запуск инфраструктуры
make up-infra

# 5. Применение миграций
make migrate

# 6. Запуск backend
make dev

# 7. В отдельном терминале - frontend
make dev-frontend
```

### 9.3 Docker Compose

```bash
# Запуск всех сервисов
make up

# Только инфраструктура (DB + Redis)
make up-infra

# С мониторингом
make up-monitoring

# Production режим
make prod
```

### 9.4 Порты

| Сервис | Порт | Описание |
|--------|------|----------|
| Backend API | 8000 | REST API |
| Frontend | 5173 | Vite dev server |
| PostgreSQL | 5434 | База данных |
| Redis | 6380 | Кэш |
| Debugger | 5678 | Python debugpy |
| Grafana | 3000 | Дашборды |
| Prometheus | 9090 | Метрики |

### 9.5 Makefile команды

```bash
# Инициализация
make init              # Создать .env из шаблона

# Docker
make up                # Запустить все сервисы
make up-infra          # Только postgres + redis
make down              # Остановить
make ps                # Статус
make build             # Пересобрать образы

# Разработка
make dev               # Backend (uvicorn hot-reload)
make dev-frontend      # Frontend (vite)
make dev-agent         # Local agent (PyQt6)
make worker            # Запустить ARQ worker
make worker-dev        # Worker с hot-reload

# База данных
make migrate           # Применить миграции
make migration name=x  # Создать миграцию
make db-shell          # PostgreSQL CLI

# Тесты
make test              # Все тесты
make test-unit         # Unit тесты
make test-cov          # С coverage

# Качество кода
make lint              # Проверка (ruff)
make format            # Форматирование
make typecheck         # Типы (mypy)

# Логи
make logs              # Все логи
make logs-backend      # Только backend
```

---

## 10. Конфигурация

### 10.1 Переменные окружения

```env
# =============================================================================
# Application
# =============================================================================
APP_NAME=AnkiRAG
APP_DEBUG=true
APP_CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# =============================================================================
# Database (PostgreSQL)
# =============================================================================
DB_HOST=localhost
DB_PORT=5434
DB_NAME=ankirag
DB_USER=ankirag
DB_PASSWORD=ankirag_secret
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# =============================================================================
# Redis
# =============================================================================
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_PASSWORD=
REDIS_DB=0

# =============================================================================
# JWT Authentication
# =============================================================================
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# =============================================================================
# SOP_LLM Service
# =============================================================================
SOP_LLM_API_BASE_URL=http://localhost:8001
SOP_LLM_TIMEOUT=300
SOP_LLM_DEFAULT_MODEL=gpt-4o
SOP_LLM_DEFAULT_TEMPERATURE=0.7
SOP_LLM_DEFAULT_MAX_TOKENS=4096

# =============================================================================
# Embeddings
# =============================================================================
EMBEDDING_MODEL=multilingual-e5-large
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=100

# =============================================================================
# Fact-checking (Perplexity)
# =============================================================================
PERPLEXITY_MODEL=llama-3.1-sonar-large-128k-online

# =============================================================================
# Task Queue (ARQ)
# =============================================================================
ARQ_REDIS_HOST=${REDIS_HOST}
ARQ_REDIS_PORT=${REDIS_PORT}
ARQ_MAX_JOBS=10
ARQ_JOB_TIMEOUT=600  # 10 минут на job
ARQ_RETRY_ATTEMPTS=3

# =============================================================================
# Rate Limiting
# =============================================================================
RATE_LIMIT_GENERATION=10/hour
RATE_LIMIT_CHAT=60/hour

# =============================================================================
# Logging
# =============================================================================
LOG_LEVEL=DEBUG
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Observability
# =============================================================================
OTEL_ENABLED=false
OTEL_SERVICE_NAME=ankirag
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
METRICS_ENABLED=true
```

### 10.2 Системные шаблоны карточек

При инициализации создаются системные шаблоны:

**Basic:**
```html
<!-- Front -->
<div class="front">{{Front}}</div>

<!-- Back -->
<div class="back">
  {{FrontSide}}
  <hr id="answer">
  {{Back}}
</div>
```

**Cloze:**
```html
<!-- Front -->
<div class="cloze">{{cloze:Text}}</div>

<!-- Back -->
<div class="cloze">{{cloze:Text}}</div>
<div class="extra">{{Extra}}</div>
```

### 10.3 Системные промпты

**card_generator (generation):**
```
You are an expert at creating educational flashcards.
Create {num_cards} flashcards about {topic}.
Each card should have a clear question on the front
and a concise, accurate answer on the back.
Language: {language}
Difficulty: {difficulty}
```

**fact_checker (fact_check):**
```
Verify the following claim and provide sources:
Claim: {claim}
Return confidence score (0-1) and supporting evidence.
```

**chat_assistant (chat):**
```
You are a helpful study assistant. Use the provided
context from the user's flashcards to answer questions.
Context: {context}
```

---

## Приложения

### A. Коды ошибок

| Код | HTTP | Описание |
|-----|------|----------|
| `AUTH_001` | 401 | Invalid credentials |
| `AUTH_002` | 401 | Token expired |
| `AUTH_003` | 403 | User inactive |
| `USER_001` | 409 | Email already exists |
| `USER_002` | 404 | User not found |
| `DECK_001` | 404 | Deck not found |
| `DECK_002` | 403 | Access denied |
| `DECK_003` | 400 | Circular reference |
| `CARD_001` | 404 | Card not found |
| `CARD_002` | 400 | Invalid status transition |
| `GEN_001` | 500 | LLM error |
| `GEN_002` | 400 | Invalid generation request |
| `SYNC_001` | 503 | AnkiConnect unavailable |
| `SYNC_002` | 400 | Invalid .apkg file |
| `RAG_001` | 500 | Embedding error |

### B. Статусы задач генерации

| Статус | Описание |
|--------|----------|
| `pending` | Задача создана, ожидает выполнения |
| `running` | Генерация в процессе |
| `completed` | Успешно завершена |
| `failed` | Завершена с ошибкой |
| `cancelled` | Отменена пользователем |

### C. Роли пользователей

| Роль | Права |
|------|-------|
| `user` | CRUD своих колод и карточек |
| `admin` | Управление всеми пользователями, системные настройки |

### D. ARQ Task States

| Статус | Описание |
|--------|----------|
| `queued` | В очереди, ожидает выполнения |
| `running` | Выполняется |
| `completed` | Завершена успешно |
| `failed` | Ошибка после всех retry |
| `deferred` | Отложена (retry) |

---

*Документ создан: Январь 2026*
*Последнее обновление: Январь 2026*
