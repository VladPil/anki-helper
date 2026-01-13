# AnkiRAG

An intelligent flashcard generation system that leverages RAG (Retrieval-Augmented Generation) to create high-quality Anki flashcards from various knowledge sources.

## Overview

AnkiRAG combines the power of large language models with retrieval-augmented generation to automatically create, organize, and sync flashcards with Anki. The system researches topics using Perplexity AI, generates contextually relevant flashcards using LLMs, and maintains a vector database for intelligent retrieval and deduplication.

## Features

- **Intelligent Card Generation**: Automatically generates flashcards from topics using RAG
- **Perplexity Integration**: Research and gather up-to-date information on any topic
- **Vector Search**: Semantic search and deduplication using embeddings
- **Anki Sync**: Seamless synchronization with Anki via AnkiConnect
- **Multi-User Support**: Full user authentication and authorization
- **Deck Management**: Organize cards into decks with hierarchical structure
- **Progress Tracking**: Monitor learning progress and card performance

## Architecture

```
anki-helper/
├── backend/                 # FastAPI backend service
│   ├── src/
│   │   ├── api/            # REST API endpoints
│   │   ├── core/           # Core configuration and security
│   │   ├── domain/         # Domain models and business logic
│   │   ├── infrastructure/ # External integrations (LLM, embeddings, etc.)
│   │   └── services/       # Application services
│   └── tests/              # Test suite
├── local-agent/            # Desktop sync agent
│   └── src/
│       ├── anki/           # AnkiConnect integration
│       ├── sync/           # Sync logic
│       └── ui/             # System tray interface
├── frontend/               # React frontend (optional)
└── .docker/                # Docker configurations
    ├── docker-compose.local.yml
    ├── docker-compose.prod.yml
    └── docker-compose.agent.yml
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Anki with AnkiConnect addon (for sync functionality)
- API keys for:
  - OpenAI (or compatible LLM provider)
  - Perplexity AI

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/anki-helper.git
   cd anki-helper
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your API keys and settings
   ```

3. **Start development services**
   ```bash
   make dev
   ```

4. **Apply database migrations**
   ```bash
   make migrate
   ```

5. **Access the API**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Metrics: http://localhost:9090/metrics

### Local Agent Setup

1. **Configure the agent**
   ```bash
   cp .env.agent .env.agent.local
   # Edit .env.agent.local with your settings
   ```

2. **Run the agent**
   ```bash
   make agent-dev
   ```

## Available Commands

Run `make help` to see all available commands:

| Command | Description |
|---------|-------------|
| `make dev` | Start all services in development mode |
| `make dev-d` | Start all services in detached mode |
| `make dev-backend` | Start only backend with dependencies |
| `make stop` | Stop all services |
| `make logs` | View service logs |
| `make prod` | Deploy to production |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests |
| `make test-integration` | Run integration tests |
| `make test-cov` | Run tests with coverage report |
| `make migrate` | Apply database migrations |
| `make migration name=<name>` | Create new migration |
| `make lint` | Run linter |
| `make format` | Format code |
| `make typecheck` | Run type checker |
| `make shell` | Open shell in backend container |
| `make psql` | Open PostgreSQL CLI |
| `make redis-cli` | Open Redis CLI |
| `make clean` | Remove all containers and volumes |

## API Documentation

The API documentation is available at `/docs` (Swagger UI) or `/redoc` (ReDoc) when the backend is running.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register a new user |
| `/api/v1/auth/login` | POST | Authenticate user |
| `/api/v1/decks` | GET/POST | List or create decks |
| `/api/v1/cards` | GET/POST | List or create cards |
| `/api/v1/generate` | POST | Generate cards from topic |
| `/api/v1/sync` | POST | Trigger Anki sync |

## Configuration

### Environment Variables

See `.env.example` for a complete list of configuration options. Key categories include:

- **APP_***: Application settings
- **DB_***: PostgreSQL configuration
- **REDIS_***: Redis configuration
- **JWT_***: Authentication settings
- **SOP_LLM_***: LLM provider settings
- **EMBEDDING_***: Embedding model settings
- **PERPLEXITY_***: Perplexity AI settings
- **OTEL_***: OpenTelemetry/tracing settings
- **LOG_***: Logging configuration
- **METRICS_***: Prometheus metrics settings

### Production Deployment

1. Copy and configure production environment:
   ```bash
   cp .env.prod.example .env.prod
   # Configure with production values
   ```

2. Deploy:
   ```bash
   make prod
   ```

## Development

### Code Quality

The project uses the following tools for code quality:

- **Ruff**: Linting and formatting
- **MyPy**: Static type checking
- **Pytest**: Testing framework

Run quality checks:
```bash
make lint      # Check for linting issues
make format    # Format code
make typecheck # Run type checker
```

### Testing

```bash
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
make test-cov          # Run tests with coverage
```

### Database Migrations

```bash
make migrate                    # Apply pending migrations
make migration name="add_field" # Create new migration
make migrate-down               # Rollback last migration
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`make test && make lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Guidelines

- Use conventional commit messages
- Keep commits focused and atomic
- Include tests for new features
- Update documentation as needed

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Write docstrings for public APIs
- Keep functions small and focused

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Anki](https://apps.ankiweb.net/) - The powerful flashcard application
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) - Anki plugin for external integrations
- [Perplexity AI](https://www.perplexity.ai/) - AI-powered research and knowledge retrieval
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [LangChain](https://www.langchain.com/) - LLM application framework
