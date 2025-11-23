from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from valentotbot.config import Settings

AsyncSessionFactory = async_sessionmaker[AsyncSession]


def build_connection_string(settings: Settings) -> str:
    user = quote_plus(settings.postgres_user)
    password = quote_plus(settings.postgres_password)
    host = settings.postgres_host
    port = settings.postgres_port
    db = settings.postgres_db
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def get_async_engine(settings: Settings) -> AsyncEngine:
    """Create a new async SQLAlchemy engine."""
    url = build_connection_string(settings)
    return create_async_engine(url, echo=False, future=True)


def get_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    """Create an async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False, autocommit=False)


def get_session_maker(settings: Settings) -> AsyncSessionFactory:
    """Convenience factory to produce sessions based on settings."""
    engine = get_async_engine(settings)
    return get_session_factory(engine)
