"""Application settings with environment variable support."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env in project root (2 levels up from this file)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Settings can be overridden via environment variables with ANKIRAG_ prefix
    or via .env file in the project root directory.

    Attributes:
        anki_connect_url: URL of the AnkiConnect API server.
        api_base_url: URL of the AnkiRAG backend API.
        sync_interval_minutes: Auto-sync interval (0 to disable).
        default_deck: Default Anki deck for imported cards.
        default_model: Default Anki note model.
    """

    model_config = SettingsConfigDict(
        env_prefix="ANKIRAG_",
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore other env vars from shared .env
    )

    anki_connect_url: str = Field(
        default="http://localhost:8765",
        description="AnkiConnect API URL",
    )

    api_base_url: str = Field(
        default="http://localhost:8080",
        description="AnkiRAG backend API URL (nginx)",
    )

    sync_interval_minutes: int = Field(
        default=30,
        description="Auto-sync interval in minutes (0 to disable)",
    )

    default_deck: str = Field(
        default="AnkiRAG",
        description="Default Anki deck for imported cards",
    )

    default_model: str = Field(
        default="Basic",
        description="Default Anki note model",
    )

    # Import settings
    import_batch_size: int = Field(
        default=100,
        description="Number of cards to read from Anki per batch",
    )

    api_batch_size: int = Field(
        default=50,
        description="Number of cards to send to API per request",
    )

    import_timeout: int = Field(
        default=120,
        description="Timeout for import API requests in seconds",
    )


# Global settings instance
settings = Settings()
