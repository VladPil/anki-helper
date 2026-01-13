"""Domain exceptions for AnkiRAG Agent."""

from typing import Optional


class AnkiConnectError(Exception):
    """Exception raised for AnkiConnect API errors.

    Raised when communication with Anki via AnkiConnect fails,
    including connection errors, timeouts, and API-level errors.
    """
    pass


class APIError(Exception):
    """Exception raised for backend API errors.

    Raised when communication with the AnkiRAG backend API fails,
    including authentication errors, network issues, and server errors.

    Attributes:
        status_code: HTTP status code if available, None otherwise.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
