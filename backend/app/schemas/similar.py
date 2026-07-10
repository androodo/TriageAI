"""Pydantic schemas for similar failure endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SimilarFailureItem(BaseModel):
    """A single similar failure result."""

    ci_run_id: UUID
    repo_name: str
    branch: str
    commit_sha: str
    test_suite_name: str
    timestamp: datetime
    similarity_score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score")
    failure_category: str | None = None
    summary: str | None = None
    root_cause: str | None = None
    suggested_steps: list[str] = Field(default_factory=list)
    failed_test_names: list[str] = Field(default_factory=list)
    exception_names: list[str] = Field(default_factory=list)


class SimilarFailuresResponse(BaseModel):
    """Response containing a list of similar historical failures."""

    query_ci_run_id: UUID
    count: int
    items: list[SimilarFailureItem]