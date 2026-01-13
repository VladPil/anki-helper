"""FastStream workers for background task processing.

This package contains FastStream workers for handling long-running tasks:
- Card generation
- Anki synchronization
- Embedding indexing
"""

from src.workers.broker import app, broker

__all__ = ["app", "broker"]
