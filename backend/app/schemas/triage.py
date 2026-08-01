"""Pydantic schemas for triage endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.triage_result import FailureCategory


class TriageResultResponse(BaseModel):
    """Full TriageAI result response."""

    id: UUID
    ci_run_id: UUID
    failure_category: FailureCategory
    confidence_score: float = Field(ge=0.0, le=1.0)
    owner_guess: str | None = None
    summary: str
    root_cause: str
    suggested_steps: list[str]
    issue_title: str
    issue_body: str
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TriageRequest(BaseModel):
    """Optional parameters for the triage endpoint."""

    force: bool = Field(
        default=False,
        description="Re-run triage even if a result already exists",
    )