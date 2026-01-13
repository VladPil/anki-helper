"""
Context variables for request tracing across the application.

This module provides context variables for trace IDs and request IDs
that can be accessed from anywhere in the codebase during request processing.
"""

from contextvars import ContextVar

# Context variables for distributed tracing
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_trace_id() -> str:
    """Get current trace ID from context.

    Returns:
        Trace ID string or empty string if not set.
    """
    return trace_id_var.get()


def get_request_id() -> str:
    """Get current request ID from context.

    Returns:
        Request ID string or empty string if not set.
    """
    return request_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace ID in context.

    Args:
        trace_id: Trace ID to set.
    """
    trace_id_var.set(trace_id)


def set_request_id(request_id: str) -> None:
    """Set request ID in context.

    Args:
        request_id: Request ID to set.
    """
    request_id_var.set(request_id)
