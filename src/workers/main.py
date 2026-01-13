"""FastStream worker entry point.

This module is the main entry point for the FastStream worker process.
It initializes all task handlers and starts the worker.
"""

from __future__ import annotations

from src.core.logging import setup_logging

# Import task handlers to register them with the broker
from src.workers import (
    generation,  # noqa: F401
    indexing,  # noqa: F401
    sync,  # noqa: F401
)
from src.workers.broker import app


@app.on_startup
async def startup() -> None:
    """Initialize worker on startup."""
    setup_logging()


@app.on_shutdown
async def shutdown() -> None:
    """Cleanup on shutdown."""
    pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(app.run())
