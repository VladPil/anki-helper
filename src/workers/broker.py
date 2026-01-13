"""FastStream Redis broker configuration.

This module configures the FastStream application with Redis broker
for handling background tasks.
"""

from __future__ import annotations

from faststream import FastStream
from faststream.redis import RedisBroker

from src.core.config import settings

# Create Redis broker with connection from settings
broker = RedisBroker(settings.redis.url)

# Create FastStream application
app = FastStream(broker)

__all__ = ["app", "broker"]
