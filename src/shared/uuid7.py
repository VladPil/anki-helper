"""UUID7 implementation for time-ordered UUIDs."""

import time
import uuid
from typing import Any

from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def uuid7() -> uuid.UUID:
    """Generate UUID7 (time-ordered UUID).

    UUID7 provides time-ordered UUIDs that are suitable for use as
    database primary keys while maintaining chronological ordering.

    The format follows the UUID version 7 specification:
    - 48 bits: Unix timestamp in milliseconds
    - 4 bits: Version (7)
    - 12 bits: Random
    - 2 bits: Variant (RFC 4122)
    - 62 bits: Random

    Returns:
        A new UUID7 instance.
    """
    timestamp_ms = int(time.time() * 1000)
    uuid_int = timestamp_ms << 80
    uuid_int |= 0x7000 << 64
    random_bits = uuid.uuid4().int & ((1 << 62) - 1)
    uuid_int |= random_bits
    uuid_int = (uuid_int & ~(0x3 << 62)) | (0x2 << 62)
    return uuid.UUID(int=uuid_int)


class UUID7(TypeDecorator):
    """SQLAlchemy TypeDecorator for UUID7 columns.

    This type decorator handles conversion between Python UUID objects
    and PostgreSQL UUID columns, with special handling for UUID7.

    Example:
        class User(Base):
            id: Mapped[uuid.UUID] = mapped_column(UUID7, primary_key=True, default=uuid7)
    """

    impl = PG_UUID
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        """Convert Python UUID to database format.

        Args:
            value: The UUID value to convert, or None.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            String representation of the UUID, or None.
        """
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value: Any, dialect) -> uuid.UUID | None:
        """Convert database value to Python UUID.

        Args:
            value: The database value to convert, or None.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            Python UUID object, or None.
        """
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
