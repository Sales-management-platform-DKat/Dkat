"""MySQL connection pool (SQLAlchemy async + aiomysql) and session/transaction helpers.

Usage in a router:
    async def handler(db: AsyncSession = Depends(get_db)): ...

Multi-step write that must succeed or fail together:
    async with transaction(db):
        await repo.decrease_stock(db, ...)
        await repo.create_sale(db, ...)
    # commit on success, rollback when an exception is raised
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DB_ECHO,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Note: reads need no commit. Writes must use `transaction(db)` (or commit explicitly).
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Run a block in a transaction: commit on success, rollback on error.

    If the session is already inside a transaction (autobegin after a previous query),
    a SAVEPOINT is used, so it can be nested safely.
    """
    if session.in_transaction():
        async with session.begin_nested():
            yield session
        await session.commit()
    else:
        async with session.begin():
            yield session


@asynccontextmanager
async def standalone_transaction() -> AsyncIterator[AsyncSession]:
    """Open a new session + transaction outside a request (worker, script, seed)."""
    async with SessionLocal() as session, session.begin():
        yield session


async def ping_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_engine() -> None:
    await engine.dispose()
