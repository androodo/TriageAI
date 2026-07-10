"""SQLAlchemy async engine, session factory, and get_db dependency.

This module sets up the database connection pool and session factory.
All models import Base from app.models.base instead, to avoid circular imports.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Async engine — used throughout the app
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()