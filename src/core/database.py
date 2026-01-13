"""
Асинхронная настройка SQLAlchemy с пулом соединений.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Self

from sqlalchemy import MetaData, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from .config import settings

# Соглашения об именовании для constraints
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:
        columns = ", ".join(
            f"{col.name}={getattr(self, col.name)!r}" for col in self.__table__.columns
        )
        return f"{self.__class__.__name__}({columns})"


class DatabaseManager:
    """Менеджер базы данных с поддержкой пула соединений."""

    _instance: Self | None = None
    _engine: AsyncEngine | None = None
    _session_factory: async_sessionmaker[AsyncSession] | None = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def engine(self) -> AsyncEngine:
        """Получить движок базы данных."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Получить фабрику сессий."""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session_factory

    def init(self) -> None:
        """Инициализировать подключение к базе данных."""
        if self._engine is not None:
            return

        self._engine = create_async_engine(
            settings.db.async_url,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.app.debug,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        # Настройка событий для мониторинга пула
        self._setup_pool_events()

    def _setup_pool_events(self) -> None:
        """Настроить события пула соединений для мониторинга."""
        if self._engine is None:
            return

        sync_engine = self._engine.sync_engine

        @event.listens_for(sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
            """Обработчик нового соединения."""
            # Можно добавить метрики или логирование
            pass

        @event.listens_for(sync_engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy) -> None:  # noqa: ANN001, ARG001
            """Обработчик получения соединения из пула."""
            pass

        @event.listens_for(sync_engine, "checkin")
        def on_checkin(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
            """Обработчик возврата соединения в пул."""
            pass

    async def close(self) -> None:
        """Закрыть все соединения."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Контекстный менеджер для сессии с автоматическим коммитом/откатом."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Генератор сессий для FastAPI Depends."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        """Проверка работоспособности базы данных."""
        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_pool_status(self) -> dict[str, int | str]:
        """Получить статус пула соединений."""
        if self._engine is None:
            return {"status": "not_initialized"}

        pool = self._engine.pool
        return {
            "pool_size": pool.size(),  # type: ignore[attr-defined]
            "checked_in": pool.checkedin(),  # type: ignore[attr-defined]
            "checked_out": pool.checkedout(),  # type: ignore[attr-defined]
            "overflow": pool.overflow(),  # type: ignore[attr-defined]
            "invalid": pool.invalidatedcount() if hasattr(pool, "invalidatedcount") else 0,
        }


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()


async def init_db() -> None:
    """Инициализировать базу данных при старте приложения."""
    db_manager.init()


async def close_db() -> None:
    """Закрыть соединения при остановке приложения."""
    await db_manager.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии базы данных."""
    async for session in db_manager.get_session():
        yield session
