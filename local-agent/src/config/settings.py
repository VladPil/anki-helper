"""Application settings with environment variable support."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Settings can be overridden via environment variables with ANKIRAG_ prefix
    or via a .env file in the working directory.

    Attributes:
        anki_connect_url: URL of the AnkiConnect API server.
        api_base_url: URL of the AnkiRAG backend API.
        sync_interval_minutes: Auto-sync interval (0 to disable).
        default_deck: Default Anki deck for imported cards.
        default_model: Default Anki note model.
    """

    model_config = SettingsConfigDict(
        env_prefix="ANKIRAG_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    anki_connect_url: str = Field(
        default="http://localhost:8765",
        description="AnkiConnect API URL",
    )

    api_base_url: str = Field(
        default="http://localhost:8000",
        description="AnkiRAG backend API URL",
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


# Global settings instance
settings = Settings()
