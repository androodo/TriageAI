"""Pydantic schemas for CI Run endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.ci_run import CIStatus


class CIRunCreate(BaseModel):
    """Payload for creating a new CI run via POST /api/runs/ingest."""

    repo_name: Annotated[str, Field(max_length=255, examples=["acme/my-service"])]
    branch: Annotated[str, Field(max_length=255, examples=["main", "feat/auth"])]
    commit_sha: Annotated[str, Field(max_length=64, examples=["a3f8c2d9e"])]
    pipeline_id: Annotated[str, Field(max_length=255, examples=["12345"])]
    environment: Annotated[str, Field(max_length=100, examples=["production", "staging"])]
    status: CIStatus = Field(examples=["failed"])
    test_suite_name: Annotated[str, Field(max_length=255, examples=["integration", "unit"])]
    failed_test_names: list[str] = Field(
        default_factory=list,
        examples=[["test_payment_flow", "test_checkout_timeout"]],
    )
    raw_log_text: Annotated[str, Field(examples=["FAILED tests/test_payment.py ..."])]
    timestamp: datetime = Field(examples=["2025-01-15T14:32:00Z"])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "repo_name": "acme/my-service",
                    "branch": "main",
                    "commit_sha": "a3f8c2d9e",
                    "pipeline_id": "12345",
                    "environment": "production",
                    "status": "failed",
                    "test_suite_name": "integration",
                    "failed_test_names": ["test_payment_flow", "test_checkout_timeout"],
                    "raw_log_text": "FAILED tests/test_payment.py::test_payment_flow\nError: AssertionError...",
                    "timestamp": "2025-01-15T14:32:00Z",
                }
            ]
        }
    }


class FailureLogSummary(BaseModel):
    """Summary of a FailureLog for embedding in CIRunResponse."""

    id: UUID
    cleaned_log_text: str = ""
    exception_names: list[str] = Field(default_factory=list)
    failed_tests: list[str] = Field(default_factory=list)
    timeout_indicators: bool = False
    dependency_errors: list[str] = Field(default_factory=list)
    infrastructure_errors: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TriageResultSummary(BaseModel):
    """Summary of a TriageResult for embedding in CIRunResponse."""

    id: UUID
    failure_category: str
    summary: str
    root_cause: str = ""
    suggested_steps: list[str] = Field(default_factory=list)
    confidence_score: float
    owner_guess: str | None = None
    issue_title: str | None = None
    issue_body: str | None = None

    model_config = {"from_attributes": True}


class IssueDraftSummary(BaseModel):
    """Summary of an IssueDraft for embedding in CIRunResponse."""

    id: UUID
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    assignee_guess: str | None = None
    format: str

    model_config = {"from_attributes": True}


class CIRunResponse(BaseModel):
    """Full CI run response with all related data."""

    id: UUID
    repo_name: str
    branch: str
    commit_sha: str
    pipeline_id: str
    environment: str
    status: CIStatus
    test_suite_name: str
    failed_test_names: list[str]
    timestamp: datetime
    created_at: datetime
    updated_at: datetime
    failure_log: FailureLogSummary | None = None
    triage_result: TriageResultSummary | None = None
    issue_draft: IssueDraftSummary | None = None

    model_config = {"from_attributes": True}


class CIRunListItem(BaseModel):
    """Minimal CI run data for the list view."""

    id: UUID
    repo_name: str
    branch: str
    commit_sha: str
    environment: str
    status: CIStatus
    test_suite_name: str
    timestamp: datetime
    triage_category: str | None = None
    triage_summary: str | None = None

    model_config = {"from_attributes": True}


class CIRunListResponse(BaseModel):
    """Paginated list of CI runs."""

    items: list[CIRunListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CIRunIngestResponse(BaseModel):
    """Response after ingesting a CI run."""

    id: UUID
    message: str = "CI run ingested successfully"
    triage_available: bool = False

    model_config = {"from_attributes": True}


class CIRunFilterParams(BaseModel):
    """Query filters for GET /api/runs."""

    status: CIStatus | None = None
    repo_name: str | None = None
    environment: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)