"""Pydantic schemas for issue draft endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.issue_draft import IssueFormat


class IssueDraftRequest(BaseModel):
    """Parameters for issue draft generation."""

    format: IssueFormat = Field(
        default=IssueFormat.GITHUB,
        description="Target issue system format",
    )
    force: bool = Field(
        default=False,
        description="Regenerate even if a draft already exists",
    )


class IssueDraftResponse(BaseModel):
    """Generated issue draft response."""

    id: UUID
    ci_run_id: UUID
    title: str
    body: str
    labels: list[str]
    assignee_guess: str | None = None
    format: IssueFormat
    created_at: datetime

    model_config = {"from_attributes": True}