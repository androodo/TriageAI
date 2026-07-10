"""FailureLog model — parsed and structured failure data with embedding."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

# pgvector is registered via sqlalchemy/dialects/postgresql/vector
# The type will be used after pgvector is installed
try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None  # type: ignore[assignment, misc]

from app.config import settings


class FailureLog(Base, TimestampMixin):
    """Structured failure log data extracted from raw CI output.

    Includes parsed error patterns, stack traces, exception names,
    and a vector embedding for similarity search.
    """

    __tablename__ = "failure_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ci_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ci_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ── Raw + cleaned log ───────────────────────────────────────────────────────
    raw_log_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_log_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Extracted patterns ──────────────────────────────────────────────────────
    extracted_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stack_traces: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    exception_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    failed_tests: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    timeout_indicators: Mapped[bool] = mapped_column(default=False)
    dependency_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    infrastructure_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # ── Embedding ───────────────────────────────────────────────────────────────
    if Vector is not None:
        embedding: Mapped[list[float] | None] = mapped_column(
            Vector(settings.embedding_dimensions),
            nullable=True,
        )
    else:
        embedding: Mapped[list[float] | None] = mapped_column(
            nullable=True,
        )

    # ── Relationship ────────────────────────────────────────────────────────────
    ci_run: Mapped["CIRun"] = relationship("CIRun", back_populates="failure_log")

    def __repr__(self) -> str:
        return f"<FailureLog(ci_run_id={self.ci_run_id}, exceptions={len(self.exception_names)})>"


# Resolve forward references
from app.models.ci_run import CIRun  # noqa: E402, F401