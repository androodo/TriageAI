"""TriageResult model — AI-generated failure diagnosis."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FailureCategory(str, Enum):
    """Classification categories for CI failures."""

    TEST_ASSERTION_FAILURE = "test_assertion_failure"
    APPLICATION_CODE_BUG = "application_code_bug"
    FLAKY_TEST = "flaky_test"
    DEPENDENCY_CONFIGURATION_ISSUE = "dependency_configuration_issue"
    INFRASTRUCTURE_ENVIRONMENT_FAILURE = "infrastructure_environment_failure"
    TIMEOUT_PERFORMANCE_ISSUE = "timeout_performance_issue"
    UNKNOWN = "unknown"


class TriageResult(Base, TimestampMixin):
    """AI-generated failure triage for a CI run.

    Contains classification, root cause analysis, suggested next steps,
    and auto-generated issue metadata.
    """

    __tablename__ = "triage_results"

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

    # ── Classification ──────────────────────────────────────────────────────────
    failure_category: Mapped[FailureCategory] = mapped_column(
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    owner_guess: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Analysis ────────────────────────────────────────────────────────────────
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # ── Issue metadata ──────────────────────────────────────────────────────────
    issue_title: Mapped[str] = mapped_column(String(500), nullable=False)
    issue_body: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Model tracking ──────────────────────────────────────────────────────────
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Relationship ────────────────────────────────────────────────────────────
    ci_run: Mapped["CIRun"] = relationship("CIRun", back_populates="triage_result")

    def __repr__(self) -> str:
        return (
            f"<TriageResult(ci_run_id={self.ci_run_id}, "
            f"category={self.failure_category.value}, "
            f"confidence={self.confidence_score:.2f})>"
        )


from app.models.ci_run import CIRun  # noqa: E402, F401