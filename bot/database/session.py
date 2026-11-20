from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import settings
from bot.database.base import Base


def get_engine(url: str = settings.DATABASE_URL) -> AsyncEngine:
    """
    Создает асинхронный движок SQLAlchemy.
    """
    engine = create_async_engine(
        url,
        echo=False,
        future=True,
    )

    # Включаем поддержку внешних ключей для SQLite
    if "sqlite" in url:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: AsyncEngine = get_engine()

# Фабрика асинхронных сессий
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор асинхронной сессии для использования в сервисах или middleware.
    """
    async with async_session_factory() as session:
        yield session


async def init_models(db_engine: AsyncEngine = engine) -> None:
    """
    Создание таблиц напрямую (для тестов или первичного запуска без Alembic).
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
