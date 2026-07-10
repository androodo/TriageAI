"""Base model infrastructure — Base class and TimestampMixin.

No imports from app.database or app.config to avoid circular dependencies.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared base for all SQLAlchemy models."""
    pass


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )