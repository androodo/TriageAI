"""IssueDraft model — generated GitHub/Jira issue from triage result."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IssueFormat(str, Enum):
    """Output format for the issue draft."""

    GITHUB = "github"
    JIRA = "jira"


class IssueDraft(Base, TimestampMixin):
    """A generated GitHub or Jira issue draft from a CI run's triage result.

    Stored so users can review, edit, and copy the draft before filing.
    """

    __tablename__ = "issue_drafts"

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

    # ── Content ─────────────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    labels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assignee_guess: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Format ──────────────────────────────────────────────────────────────────
    format: Mapped[IssueFormat] = mapped_column(
        default=IssueFormat.GITHUB,
        nullable=False,
    )

    # ── Relationship ────────────────────────────────────────────────────────────
    ci_run: Mapped["CIRun"] = relationship("CIRun", back_populates="issue_draft")

    def __repr__(self) -> str:
        return (
            f"<IssueDraft(ci_run_id={self.ci_run_id}, "
            f"format={self.format.value}, title={self.title[:40]!r})>"
        )


from app.models.ci_run import CIRun  # noqa: E402, F401