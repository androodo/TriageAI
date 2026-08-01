"""CIRun model — represents a single CI pipeline execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CIStatus(str, Enum):
    """Status of a CI run."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CIRun(Base, TimestampMixin):
    """Represents a single CI pipeline execution.

    One CIRun may have at most one FailureLog, one TriageResult,
    and one IssueDraft.
    """

    __tablename__ = "ci_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # ── Source metadata ─────────────────────────────────────────────────────────
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_id: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[CIStatus] = mapped_column(
        SAEnum(
            CIStatus,
            name="ci_status",
            values_callable=lambda enum: [e.value for e in enum],
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )
    test_suite_name: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_test_names: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────────
    failure_log: Mapped["FailureLog | None"] = relationship(
        "FailureLog",
        back_populates="ci_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    triage_result: Mapped["TriageResult | None"] = relationship(
        "TriageResult",
        back_populates="ci_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    issue_draft: Mapped["IssueDraft | None"] = relationship(
        "IssueDraft",
        back_populates="ci_run",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<CIRun(id={self.id}, repo={self.repo_name}, "
            f"branch={self.branch}, status={self.status.value})>"
        )


# Forward reference to avoid circular imports at runtime
from app.models.failure_log import FailureLog  # noqa: E402, F401
from app.models.triage_result import TriageResult  # noqa: E402, F401
from app.models.issue_draft import IssueDraft  # noqa: E402, F401