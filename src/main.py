"""FastAPI application entry point"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all routers from api/
from src.api import auth as auth_router
from src.api import cards as cards_router
from src.api import chat as chat_router
from src.api import decks as decks_router
from src.api import generation as generation_router
from src.api import prompts as prompts_router
from src.api import rag as rag_router
from src.api import sync as sync_router
from src.api import system as system_router
from src.api import templates as templates_router
from src.api import users as users_router
from src.core.cache import close_cache, setup_cache
from src.core.config import settings
from src.core.database import db_manager
from src.core.exceptions import setup_exception_handlers
from src.core.logging import get_structured_logger, setup_logging
from src.core.middleware import RequestTracingMiddleware
from src.core.openapi import API_METADATA, TAGS_METADATA
from src.core.telemetry import setup_telemetry

# Import all models first to ensure proper mapper configuration
# This prevents "Foreign key could not find table" errors
from src.modules.auth.models import RefreshToken  # noqa: F401
from src.modules.cards.models import Card  # noqa: F401
from src.modules.chat.models import ChatMessage, ChatSession  # noqa: F401
from src.modules.decks.models import Deck  # noqa: F401
from src.modules.prompts.models import Prompt, PromptExecution  # noqa: F401
from src.modules.templates.models import CardTemplate  # noqa: F401
from src.modules.users.models import User, UserPreferences  # noqa: F401
from src.services.llm.models import EmbeddingModel, LLMModel  # noqa: F401

logger = get_structured_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app.name}...")

    # Initialize database
    db_manager.init()
    logger.info("Database connection pool initialized")

    # Initialize cache
    await setup_cache(settings)
    logger.info("Cache initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_cache()
    logger.info("Cache closed")
    await db_manager.close()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title=API_METADATA["title"],
        description=API_METADATA["description"],
        version=API_METADATA["version"],
        openapi_tags=TAGS_METADATA,
        debug=settings.app.debug,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.app.debug else None,
        redoc_url="/api/redoc" if settings.app.debug else None,
        openapi_url="/api/openapi.json" if settings.app.debug else None,
        redirect_slashes=False,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom request tracing middleware
    app.add_middleware(RequestTracingMiddleware)

    # Setup OpenTelemetry tracing
    setup_telemetry(app)

    # Register exception handlers
    setup_exception_handlers(app)

    # Include API routers with /api prefix
    app.include_router(auth_router.router, prefix="/api")
    app.include_router(users_router.router, prefix="/api")
    app.include_router(decks_router.router, prefix="/api")
    app.include_router(cards_router.router, prefix="/api")
    app.include_router(templates_router.router, prefix="/api")
    app.include_router(prompts_router.router, prefix="/api")
    app.include_router(chat_router.router, prefix="/api")
    app.include_router(generation_router.router, prefix="/api")
    app.include_router(rag_router.router, prefix="/api")
    app.include_router(sync_router.router, prefix="/api")

    # System router (no /api prefix - accessible at root)
    app.include_router(system_router.router)

    return app


# Create the application instance
app = create_app()
