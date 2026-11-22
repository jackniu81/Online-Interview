"""Async SQLAlchemy engine and session management."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings

engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """Create engine/session factory (idempotent, called from app lifespan)."""
    global engine, SessionLocal
    if engine is not None:
        return
    # NullPool: 避免跨事件循环复用连接（pytest 每个测试新循环 + Windows proactor 兼容）
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def dispose_db() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session."""
    assert SessionLocal is not None, "call init_db() first"
    async with SessionLocal() as session:
        yield session
