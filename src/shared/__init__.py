"""
Shared module - cross-cutting concerns and utilities.

This module provides shared functionality used across the application:
- Context variables for request/trace IDs
- Logging utilities with Loguru
"""

from .context import (
    get_request_id,
    get_trace_id,
    request_id_var,
    set_request_id,
    set_trace_id,
    trace_id_var,
)
from .logging import (
    get_logger,
    log_generation_completed,
    log_generation_failed,
    log_generation_started,
    logger,
    setup_logger,
)

__all__ = [
    # Context
    "get_request_id",
    "get_trace_id",
    "request_id_var",
    "set_request_id",
    "set_trace_id",
    "trace_id_var",
    # Logging
    "logger",
    "setup_logger",
    "get_logger",
    "log_generation_started",
    "log_generation_completed",
    "log_generation_failed",
]
