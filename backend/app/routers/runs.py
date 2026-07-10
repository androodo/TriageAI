"""Runs router — all CI run endpoints: ingest, list, detail, triage, similar, issue-draft."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.ci_run import CIStatus, CIRun
from app.models.failure_log import FailureLog
from app.models.issue_draft import IssueDraft, IssueFormat
from app.models.triage_result import TriageResult
from app.schemas.ci_run import (
    CIRunCreate,
    CIRunFilterParams,
    CIRunIngestResponse,
    CIRunListItem,
    CIRunListResponse,
    CIRunResponse,
)
from app.schemas.issue_draft import IssueDraftRequest, IssueDraftResponse
from app.schemas.similar import SimilarFailuresResponse
from app.schemas.triage import TriageRequest, TriageResultResponse
from app.services.issue_draft import IssueDraftService
from app.services.log_parser import LogParser
from app.services.llm import llm_provider
from app.services.similarity import SimilarityService
from app.services.triage import TriageService
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/runs", tags=["CI Runs"])


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Build a paginated response dict."""
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


# ─────────────────────────────────────────────────────────────────────────────────
#                            POST /api/runs/ingest
# ─────────────────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=CIRunIngestResponse, status_code=201)
async def ingest_ci_run(
    data: CIRunCreate,
    db: AsyncSession = Depends(get_db),
) -> CIRunIngestResponse:
    """Ingest a CI run with raw log text, parse it, and store in the database.

    This endpoint is called by CI pipelines to report test results.
    """
    log.info("Ingesting CI run", repo=data.repo_name, branch=data.branch, status=data.status.value)

    # Create the CI run
    ci_run = CIRun(
        repo_name=data.repo_name,
        branch=data.branch,
        commit_sha=data.commit_sha,
        pipeline_id=data.pipeline_id,
        environment=data.environment,
        status=data.status,
        test_suite_name=data.test_suite_name,
        failed_test_names=data.failed_test_names,
        timestamp=data.timestamp or datetime.utcnow(),
    )
    db.add(ci_run)
    await db.flush()

    triage_available = False

    if data.status == CIStatus.FAILED and data.raw_log_text:
        # Parse the failure log
        parser = LogParser()
        parsed = parser.parse(data.raw_log_text)

        # Store the failure log
        failure_log = FailureLog(
            ci_run_id=ci_run.id,
            raw_log_text=data.raw_log_text,
            cleaned_log_text=parsed.cleaned_log_text,
            extracted_errors=parsed.extracted_errors,
            stack_traces=parsed.stack_traces,
            exception_names=parsed.exception_names,
            failed_tests=parsed.failed_tests,
            timeout_indicators=parsed.timeout_indicators,
            dependency_errors=parsed.dependency_errors,
            infrastructure_errors=parsed.infrastructure_errors,
        )
        db.add(failure_log)
        await db.flush()

        # Generate embedding and store
        try:
            embedding = await llm_provider.embed(parsed.cleaned_log_text[:12000])
            from sqlalchemy import text
            await db.execute(
                text("UPDATE failure_logs SET embedding = :embedding WHERE id = :id"),
                {"embedding": embedding, "id": str(failure_log.id)},
            )
        except Exception as e:
            log.warning("Failed to generate embedding", error=str(e))

        # Auto-triage on ingest
        try:
            triage_svc = TriageService()
            triage_result = await triage_svc.triage(
                cleaned_log_text=parsed.cleaned_log_text,
                stack_traces=parsed.stack_traces,
                exception_names=parsed.exception_names,
                failed_tests=parsed.failed_tests,
                repo_name=ci_run.repo_name,
                branch=ci_run.branch,
                commit_sha=ci_run.commit_sha,
                environment=ci_run.environment,
                test_suite_name=ci_run.test_suite_name,
            )

            triage = TriageResult(
                ci_run_id=ci_run.id,
                failure_category=triage_result["failure_category"],
                confidence_score=triage_result["confidence_score"],
                owner_guess=triage_result.get("owner_guess"),
                summary=triage_result["summary"],
                root_cause=triage_result["root_cause"],
                suggested_steps=triage_result["suggested_steps"],
                issue_title=triage_result["issue_title"],
                issue_body=triage_result["issue_body"],
                model_used=type(llm_provider).__name__,
            )
            db.add(triage)
            triage_available = True
            log.info("Auto-triage complete", category=triage_result["failure_category"])
        except Exception as e:
            log.warning("Auto-triage failed", error=str(e))

    await db.commit()
    log.info("CI run ingested successfully", run_id=str(ci_run.id))
    return CIRunIngestResponse(id=ci_run.id, message="CI run ingested successfully", triage_available=triage_available)


# ─────────────────────────────────────────────────────────────────────────────────
#                            GET /api/runs
# ─────────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=CIRunListResponse)
async def list_ci_runs(
    db: AsyncSession = Depends(get_db),
    status: CIStatus | None = None,
    repo_name: str | None = None,
    environment: str | None = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> CIRunListResponse:
    """List CI runs with optional filtering and pagination.

    Filters:
    - `status`: Filter by passed/failed/skipped
    - `repo_name`: Filter by repository name
    - `environment`: Filter by deployment environment (production, staging, etc.)
    """
    # Build base query
    query = select(CIRun)

    # Apply filters
    where_clauses: list = []
    if status:
        where_clauses.append(CIRun.status == status)
    if repo_name:
        where_clauses.append(CIRun.repo_name == repo_name)
    if environment:
        where_clauses.append(CIRun.environment == environment)

    if where_clauses:
        query = query.where(*where_clauses)

    # Count total
    count_query = select(func.count(CIRun.id)).where(*where_clauses)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(CIRun.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    ci_runs = result.scalars().all()

    # Build response items (join triage for summary if available)
    items: list[CIRunListItem] = []
    for run in ci_runs:
        item = CIRunListItem(
            id=run.id,
            repo_name=run.repo_name,
            branch=run.branch,
            commit_sha=run.commit_sha,
            environment=run.environment,
            status=run.status,
            test_suite_name=run.test_suite_name,
            timestamp=run.timestamp,
        )
        # Add triage summary if present
        if run.triage_result:
            item.triage_category = run.triage_result.failure_category.value
            item.triage_summary = run.triage_result.summary
        items.append(item)

    return paginated_response(items, total, page, page_size)


# ─────────────────────────────────────────────────────────────────────────────────
#                            GET /api/runs/{id}
# ─────────────────────────────────────────────────────────────────────────────────

@router.get("/{run_id}", response_model=CIRunResponse)
async def get_ci_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CIRunResponse:
    """Get full details for a single CI run including failure logs and triage results."""
    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    ci_run = result.scalar_one_or_none()

    if not ci_run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    # Build response with optional related objects
    return CIRunResponse(
        id=ci_run.id,
        repo_name=ci_run.repo_name,
        branch=ci_run.branch,
        commit_sha=ci_run.commit_sha,
        pipeline_id=ci_run.pipeline_id,
        environment=ci_run.environment,
        status=ci_run.status,
        test_suite_name=ci_run.test_suite_name,
        failed_test_names=ci_run.failed_test_names,
        timestamp=ci_run.timestamp,
        created_at=ci_run.created_at,
        updated_at=ci_run.updated_at,
        failure_log=ci_run.failure_log,
        triage_result=ci_run.triage_result,
        issue_draft=ci_run.issue_draft,
    )


# ─────────────────────────────────────────────────────────────────────────────────
#                        POST /api/runs/{id}/triage
# ─────────────────────────────────────────────────────────────────────────────────

@router.post("/{run_id}/triage", response_model=TriageResultResponse)
async def triage_ci_run(
    run_id: UUID,
    request: TriageRequest,
    db: AsyncSession = Depends(get_db),
) -> TriageResultResponse:
    """Run AI-powered failure triage on a failed CI run.

    Returns:
    - Failure category (test assertion, bug, flaky test, dependency, infrastructure, timeout)
    - Confidence score (0.0-1.0)
    - Root cause analysis
    - Suggested debugging steps
    - Estimated owner/team
    - Generated issue title and body
    """
    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    ci_run = result.scalar_one_or_none()

    if not ci_run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    # Check if triage already exists
    if ci_run.triage_result and not request.force:
        log.info("Triage already exists, returning cached", run_id=str(run_id))
        return TriageResultResponse.model_validate(ci_run.triage_result)

    # Need a failure log to triage
    if not ci_run.failure_log:
        raise HTTPException(status_code=400, detail="No failure log available for this run")

    fl = ci_run.failure_log
    triage_svc = TriageService()
    triage_result = await triage_svc.triage(
        cleaned_log_text=fl.cleaned_log_text,
        stack_traces=fl.stack_traces,
        exception_names=fl.exception_names,
        failed_tests=fl.failed_tests,
        repo_name=ci_run.repo_name,
        branch=ci_run.branch,
        commit_sha=ci_run.commit_sha,
        environment=ci_run.environment,
        test_suite_name=ci_run.test_suite_name,
    )

    # Create or update triage result
    if ci_run.triage_result:
        triage = ci_run.triage_result
        triage.failure_category = triage_result["failure_category"]
        triage.confidence_score = triage_result["confidence_score"]
        triage.owner_guess = triage_result.get("owner_guess")
        triage.summary = triage_result["summary"]
        triage.root_cause = triage_result["root_cause"]
        triage.suggested_steps = triage_result["suggested_steps"]
        triage.issue_title = triage_result["issue_title"]
        triage.issue_body = triage_result["issue_body"]
        triage.model_used = type(llm_provider).__name__
    else:
        triage = TriageResult(
            ci_run_id=ci_run.id,
            failure_category=triage_result["failure_category"],
            confidence_score=triage_result["confidence_score"],
            owner_guess=triage_result.get("owner_guess"),
            summary=triage_result["summary"],
            root_cause=triage_result["root_cause"],
            suggested_steps=triage_result["suggested_steps"],
            issue_title=triage_result["issue_title"],
            issue_body=triage_result["issue_body"],
            model_used=type(llm_provider).__name__,
        )
        db.add(triage)

    await db.commit()
    log.info("Triage complete", run_id=str(run_id), category=triage_result["failure_category"])
    return TriageResultResponse.model_validate(triage)


# ─────────────────────────────────────────────────────────────────────────────────
#                       GET /api/runs/{id}/similar
# ─────────────────────────────────────────────────────────────────────────────────

@router.get("/{run_id}/similar", response_model=SimilarFailuresResponse)
async def find_similar_failures(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SimilarFailuresResponse:
    """Find similar historical failures using vector embeddings.

    Returns the top 5 most similar past failures with similarity scores,
    including their root cause categories and suggested steps.
    """
    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    ci_run = result.scalar_one_or_none()

    if not ci_run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    if not ci_run.failure_log or not ci_run.failure_log.embedding:
        raise HTTPException(status_code=400, detail="No failure log or embedding available")

    embedding: list[float] = ci_run.failure_log.embedding or []
    similarity_svc = SimilarityService(db)

    similar = await similarity_svc.find_similar(
        ci_run_id=ci_run.id,
        current_embedding=embedding,
        repo_name=settings.similarity_search_filter or ci_run.repo_name,
        limit=settings.similar_failures_count,
    )

    log.info("Found similar failures", count=len(similar), run_id=str(run_id))

    return SimilarFailuresResponse(
        query_ci_run_id=ci_run.id,
        count=len(similar),
        items=similar,
    )


# ─────────────────────────────────────────────────────────────────────────────────
#                    POST /api/runs/{id}/issue-draft
# ─────────────────────────────────────────────────────────────────────────────────

@router.post("/{run_id}/issue-draft", response_model=IssueDraftResponse)
async def generate_issue_draft(
    run_id: UUID,
    request: IssueDraftRequest,
    db: AsyncSession = Depends(get_db),
) -> IssueDraftResponse:
    """Generate a ready-to-file GitHub or Jira issue draft from triage results.

    The draft includes:
    - Issue title
    - Full markdown body with sections for summary, root cause, steps to reproduce
    - Suggested labels (bug, ci-failure, area/*)
    - Assignee/team guess
    """
    result = await db.execute(select(CIRun).where(CIRun.id == run_id))
    ci_run = result.scalar_one_or_none()

    if not ci_run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    # Check if issue draft already exists
    if ci_run.issue_draft and not request.force:
        return IssueDraftResponse.model_validate(ci_run.issue_draft)

    # Need triage to generate issue draft
    if not ci_run.triage_result:
        raise HTTPException(status_code=400, detail="No triage result available — run triage first")

    tr = ci_run.triage_result

    # Fetch similar failures if available
    similarity_svc = SimilarityService(db)
    similar_failures = []
    if ci_run.failure_log and ci_run.failure_log.embedding:
        similar_failures = await similarity_svc.find_similar(
            ci_run_id=ci_run.id,
            current_embedding=ci_run.failure_log.embedding,
            repo_name=ci_run.repo_name,
            limit=3,
        )

    # Generate issue draft
    issue_draft_svc = IssueDraftService()
    draft_data = await issue_draft_svc.generate(
        triage_data={
            "failure_category": tr.failure_category.value,
            "confidence_score": tr.confidence_score,
            "summary": tr.summary,
            "root_cause": tr.root_cause,
            "suggested_steps": tr.suggested_steps,
            "owner_guess": tr.owner_guess,
        },
        repo_name=ci_run.repo_name,
        branch=ci_run.branch,
        commit_sha=ci_run.commit_sha,
        test_suite_name=ci_run.test_suite_name,
        failed_tests=ci_run.failed_test_names,
        similar_failures=similar_failures,
        format=request.format,
    )

    # Create or update issue draft
    title = draft_data.get("title", "CI failure — manual investigation required")
    body = draft_data.get("body", "")
    labels = draft_data.get("labels", ["bug", "ci-failure"])
    assignee_guess = draft_data.get("assignee_guess")

    if ci_run.issue_draft:
        draft = ci_run.issue_draft
        draft.title = title
        draft.body = body
        draft.labels = labels
        draft.assignee_guess = assignee_guess
        draft.format = request.format
    else:
        draft = IssueDraft(
            ci_run_id=ci_run.id,
            title=title,
            body=body,
            labels=labels,
            assignee_guess=assignee_guess,
            format=request.format,
        )
        db.add(draft)

    await db.commit()
    log.info("Issue draft generated", run_id=str(run_id), format=request.format.value)

    return IssueDraftResponse.model_validate(draft)