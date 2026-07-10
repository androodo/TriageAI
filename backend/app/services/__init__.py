"""CI Run API router — ingestion, listing, detail, triage, similarity, issue draft."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.ci_run import CIRun, CIStatus
from app.models.failure_log import FailureLog
from app.models.issue_draft import IssueDraft, IssueFormat
from app.models.triage_result import TriageResult
from app.schemas.ci_run import (
    CIRunCreate,
    CIRunIngestResponse,
    CIRunListItem,
    CIRunListResponse,
    CIRunResponse,
    FailureLogSummary,
    IssueDraftSummary,
    TriageResultSummary,
)
from app.schemas.issue_draft import IssueDraftRequest, IssueDraftResponse
from app.schemas.similar import SimilarFailureItem, SimilarFailuresResponse
from app.schemas.triage import TriageRequest, TriageResultResponse
from app.services.issue_draft import IssueDraftService
from app.services.log_parser import LogParser
from app.services.similarity import SimilarityService
from app.services.triage import TriageService
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/runs", tags=["CI Runs"])


# ── Ingestion ─────────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=CIRunIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a CI run",
    description="Accept CI run data, parse logs, store embeddings, return the created run.",
)
async def ingest_ci_run(
    payload: CIRunCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CIRunIngestResponse:
    """Ingest a new CI run: parse logs, generate embeddings, store everything."""
    log.info(
        "Ingesting CI run",
        repo=payload.repo_name,
        branch=payload.branch,
        status=payload.status.value,
    )

    # Parse the raw log
    parser = LogParser()
    parsed = parser.parse(payload.raw_log_text)

    # Create the CI run record
    ci_run = CIRun(
        repo_name=payload.repo_name,
        branch=payload.branch,
        commit_sha=payload.commit_sha,
        pipeline_id=payload.pipeline_id,
        environment=payload.environment,
        status=payload.status,
        test_suite_name=payload.test_suite_name,
        failed_test_names=payload.failed_test_names,
        timestamp=payload.timestamp,
    )
    db.add(ci_run)
    await db.flush()  # Get the ID

    # Only create failure log for failed runs
    if payload.status == CIStatus.FAILED:
        failure_log = FailureLog(
            ci_run_id=ci_run.id,
            raw_log_text=parsed.raw_log_text,
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

        # Generate and store embedding asynchronously
        if parsed.cleaned_log_text:
            try:
                similarity_svc = SimilarityService(db)
                embedding = await similarity_svc.get_embedding(parsed.cleaned_log_text)
                failure_log.embedding = embedding
            except Exception as e:
                log.warning("Embedding generation failed", error=str(e))

    await db.commit()
    await db.refresh(ci_run)

    log.info("CI run ingested", run_id=str(ci_run.id))

    return CIRunIngestResponse(
        id=ci_run.id,
        message="CI run ingested successfully",
        triage_available=(payload.status == CIStatus.FAILED),
    )


# ── List ───────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=CIRunListResponse,
    summary="List CI runs",
    description="Return a paginated list of CI runs with optional filters.",
)
async def list_ci_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: CIStatus | None = None,
    repo_name: str | None = None,
    environment: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CIRunListResponse:
    """List all CI runs with optional filtering and pagination."""
    # Build base query
    query = select(CIRun).options(
        selectinload(CIRun.failure_log),
        selectinload(CIRun.triage_result),
    )
    count_query = select(func.count(CIRun.id))

    # Apply filters
    if status:
        query = query.where(CIRun.status == status)
        count_query = count_query.where(CIRun.status == status)
    if repo_name:
        query = query.where(CIRun.repo_name.ilike(f"%{repo_name}%"))
        count_query = count_query.where(CIRun.repo_name.ilike(f"%{repo_name}%"))
    if environment:
        query = query.where(CIRun.environment == environment)
        count_query = count_query.where(CIRun.environment == environment)

    # Order by timestamp descending
    query = query.order_by(CIRun.timestamp.desc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute both queries
    result = await db.execute(query)
    rows = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    items: list[CIRunListItem] = []
    for run in rows:
        triage_cat = None
        triage_sum = None
        if run.triage_result:
            triage_cat = run.triage_result.failure_category.value
            triage_sum = run.triage_result.summary

        items.append(CIRunListItem(
            id=run.id,
            repo_name=run.repo_name,
            branch=run.branch,
            commit_sha=run.commit_sha,
            environment=run.environment,
            status=run.status,
            test_suite_name=run.test_suite_name,
            timestamp=run.timestamp,
            triage_category=triage_cat,
            triage_summary=triage_sum,
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return CIRunListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Detail ─────────────────────────────────────────────────────────────────────

@router.get(
    "/{run_id}",
    response_model=CIRunResponse,
    summary="Get a CI run by ID",
    description="Return full details of a single CI run including failure log, triage, and issue draft.",
)
async def get_ci_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CIRunResponse:
    """Get a single CI run with all related data."""
    result = await db.execute(
        select(CIRun)
        .options(
            selectinload(CIRun.failure_log),
            selectinload(CIRun.triage_result),
            selectinload(CIRun.issue_draft),
        )
        .where(CIRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CI run {run_id} not found",
        )

    failure_log_summary = None
    if run.failure_log:
        failure_log_summary = FailureLogSummary(
            id=run.failure_log.id,
            exception_names=run.failure_log.exception_names,
            failed_tests=run.failure_log.failed_tests,
            timeout_indicators=run.failure_log.timeout_indicators,
            dependency_errors=run.failure_log.dependency_errors,
            infrastructure_errors=run.failure_log.infrastructure_errors,
        )

    triage_summary = None
    if run.triage_result:
        triage_summary = TriageResultSummary(
            id=run.triage_result.id,
            failure_category=run.triage_result.failure_category.value,
            summary=run.triage_result.summary,
            confidence_score=run.triage_result.confidence_score,
            owner_guess=run.triage_result.owner_guess,
        )

    issue_summary = None
    if run.issue_draft:
        issue_summary = IssueDraftSummary(
            id=run.issue_draft.id,
            title=run.issue_draft.title,
            format=run.issue_draft.format.value,
        )

    return CIRunResponse(
        id=run.id,
        repo_name=run.repo_name,
        branch=run.branch,
        commit_sha=run.commit_sha,
        pipeline_id=run.pipeline_id,
        environment=run.environment,
        status=run.status,
        test_suite_name=run.test_suite_name,
        failed_test_names=run.failed_test_names,
        timestamp=run.timestamp,
        created_at=run.created_at,
        updated_at=run.updated_at,
        failure_log=failure_log_summary,
        triage_result=triage_summary,
        issue_draft=issue_summary,
    )


# ── Triage ─────────────────────────────────────────────────────────────────────

@router.post(
    "/{run_id}/triage",
    response_model=TriageResultResponse,
    summary="Run AI triage on a CI failure",
    description="Classify the failure, identify root cause, and generate actionable debugging steps.",
)
async def triage_ci_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: TriageRequest = TriageRequest(),
) -> TriageResultResponse:
    """Run AI triage on a failed CI run."""
    # Fetch the run with failure log
    result = await db.execute(
        select(CIRun)
        .options(selectinload(CIRun.failure_log))
        .where(CIRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    if run.status != CIStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail="Triage is only available for failed CI runs",
        )

    if run.failure_log is None:
        raise HTTPException(
            status_code=400,
            detail="No failure log found for this CI run",
        )

    # Check for existing triage result
    if run.triage_result and not params.force:
        return TriageResultResponse.model_validate(run.triage_result)

    # Run AI triage
    triage_svc = TriageService()
    triage_data = await triage_svc.triage(
        cleaned_log_text=run.failure_log.cleaned_log_text,
        stack_traces=run.failure_log.stack_traces,
        exception_names=run.failure_log.exception_names,
        failed_tests=run.failure_log.failed_tests or run.failed_test_names,
        repo_name=run.repo_name,
        branch=run.branch,
        commit_sha=run.commit_sha,
        environment=run.environment,
        test_suite_name=run.test_suite_name,
    )

    from app.models.triage_result import FailureCategory
    from app.config import settings

    category = FailureCategory(triage_data["failure_category"])

    triage_result = TriageResult(
        ci_run_id=run.id,
        failure_category=category,
        confidence_score=triage_data["confidence_score"],
        summary=triage_data["summary"],
        root_cause=triage_data["root_cause"],
        suggested_steps=triage_data["suggested_steps"],
        owner_guess=triage_data.get("owner_guess"),
        issue_title=triage_data["issue_title"],
        issue_body=triage_data["issue_body"],
        model_used=settings.llm_model,
    )

    db.add(triage_result)
    run.triage_result = triage_result
    await db.commit()
    await db.refresh(triage_result)

    log.info("Triage complete", run_id=str(run_id), category=category.value)

    return TriageResultResponse.model_validate(triage_result)


# ── Similar Failures ───────────────────────────────────────────────────────────

@router.get(
    "/{run_id}/similar",
    response_model=SimilarFailuresResponse,
    summary="Find similar historical failures",
    description="Use vector embeddings to retrieve the top-5 most similar past failures.",
)
async def find_similar_failures(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=5, ge=1, le=20),
) -> SimilarFailuresResponse:
    """Find similar historical failures using vector similarity search."""
    # Fetch the run with its failure log
    result = await db.execute(
        select(CIRun)
        .options(selectinload(CIRun.failure_log))
        .where(CIRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    if run.failure_log is None or not run.failure_log.cleaned_log_text:
        raise HTTPException(
            status_code=400,
            detail="No failure log available for similarity search",
        )

    similarity_svc = SimilarityService(db)

    # Get embedding (use stored one or generate)
    if run.failure_log.embedding:
        embedding = run.failure_log.embedding
    else:
        embedding = await similarity_svc.get_embedding(run.failure_log.cleaned_log_text)
        run.failure_log.embedding = embedding
        await db.commit()

    similar_raw = await similarity_svc.find_similar(
        ci_run_id=run.id,
        current_embedding=embedding,
        repo_name=run.repo_name,
        limit=limit,
    )

    items = [SimilarFailureItem(**item) for item in similar_raw]

    return SimilarFailuresResponse(
        query_ci_run_id=run.id,
        count=len(items),
        items=items,
    )


# ── Issue Draft ────────────────────────────────────────────────────────────────

@router.post(
    "/{run_id}/issue-draft",
    response_model=IssueDraftResponse,
    summary="Generate an issue draft from triage results",
    description="Create a formatted GitHub/Jira issue draft based on the triage analysis.",
)
async def generate_issue_draft(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: IssueDraftRequest = IssueDraftRequest(),
) -> IssueDraftResponse:
    """Generate an issue draft from triage data."""
    # Fetch run with triage result
    result = await db.execute(
        select(CIRun)
        .options(
            selectinload(CIRun.triage_result),
            selectinload(CIRun.failure_log),
        )
        .where(CIRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail=f"CI run {run_id} not found")

    if run.triage_result is None:
        raise HTTPException(
            status_code=400,
            detail="Run triage first before generating an issue draft",
        )

    if run.issue_draft and not params.force:
        return IssueDraftResponse.model_validate(run.issue_draft)

    # Fetch similar failures for context
    similar_raw: list[dict] = []
    if run.failure_log and run.failure_log.embedding:
        try:
            sim_svc = SimilarityService(db)
            similar_raw = await sim_svc.find_similar(
                ci_run_id=run.id,
                current_embedding=run.failure_log.embedding,
                repo_name=run.repo_name,
                limit=3,
            )
        except Exception as e:
            log.warning("Similar failures fetch failed during issue draft", error=str(e))

    draft_svc = IssueDraftService()
    draft_data = await draft_svc.generate(
        triage_data={
            "failure_category": run.triage_result.failure_category.value,
            "confidence_score": run.triage_result.confidence_score,
            "summary": run.triage_result.summary,
            "root_cause": run.triage_result.root_cause,
            "suggested_steps": run.triage_result.suggested_steps,
            "owner_guess": run.triage_result.owner_guess,
        },
        repo_name=run.repo_name,
        branch=run.branch,
        commit_sha=run.commit_sha,
        test_suite_name=run.test_suite_name,
        failed_tests=run.failed_test_names,
        similar_failures=similar_raw,
        format=params.format,
    )

    issue_draft = IssueDraft(
        ci_run_id=run.id,
        title=draft_data["title"],
        body=draft_data["body"],
        labels=draft_data.get("labels", []),
        assignee_guess=draft_data.get("assignee_guess"),
        format=params.format,
    )

    db.add(issue_draft)
    run.issue_draft = issue_draft
    await db.commit()
    await db.refresh(issue_draft)

    log.info("Issue draft generated", run_id=str(run_id), format=params.format.value)

    return IssueDraftResponse.model_validate(issue_draft)