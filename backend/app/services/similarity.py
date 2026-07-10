"""Similarity Service — vector similarity search for finding related failures."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ci_run import CIRun
from app.models.failure_log import FailureLog
from app.models.triage_result import TriageResult
from app.services.llm import llm_provider
from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


class SimilarityService:
    """Finds similar historical failures using vector embeddings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._llm = llm_provider

    async def get_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text."""
        return await self._llm.embed(text)

    async def find_similar(
        self,
        ci_run_id: UUID,
        current_embedding: list[float],
        *,
        repo_name: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find the most similar historical failures to the given embedding.

        Uses cosine similarity via pgvector's <=> operator.
        Filters to the same repo if provided, excludes the current run.
        """
        # Build the embedding as a PostgreSQL array literal
        embedding_str = "[" + ",".join(str(x) for x in current_embedding) + "]"

        # pgvector cosine distance query
        query = text(f"""
            WITH current AS (
                SELECT embedding <=> :embedding AS distance,
                       fl.ci_run_id,
                       fl.cleaned_log_text,
                       fl.exception_names,
                       fl.failed_tests
                FROM failure_logs fl
                JOIN ci_runs cr ON cr.id = fl.ci_run_id
                WHERE fl.embedding IS NOT NULL
                  AND fl.ci_run_id != :ci_run_id
                  {"AND cr.repo_name = :repo_name" if repo_name else ""}
                ORDER BY fl.embedding <=> :embedding
                LIMIT :limit
            )
            SELECT
                c.distance AS similarity_score,
                c.ci_run_id,
                c.cleaned_log_text,
                c.exception_names,
                c.failed_tests,
                cr.repo_name,
                cr.branch,
                cr.commit_sha,
                cr.test_suite_name,
                cr.timestamp,
                cr.failed_test_names,
                tr.failure_category,
                tr.summary AS triage_summary,
                tr.root_cause
            FROM current c
            JOIN ci_runs cr ON cr.id = c.ci_run_id
            LEFT JOIN triage_results tr ON tr.ci_run_id = c.ci_run_id
        """)

        params: dict = {
            "embedding": embedding_str,
            "ci_run_id": str(ci_run_id),
            "limit": limit,
        }
        if repo_name:
            params["repo_name"] = repo_name

        result = await self._db.execute(query, params)
        rows = result.fetchall()

        similar: list[dict] = []
        for row in rows:
            # pgvector <=> returns cosine distance: 0 = identical, 2 = opposite
            # Convert to a 0-1 similarity score
            raw_distance = row.similarity_score if row.similarity_score is not None else 0.0
            similarity = max(0.0, 1.0 - raw_distance / 2.0)
            similar.append({
                "ci_run_id": row.ci_run_id,
                "repo_name": row.repo_name,
                "branch": row.branch,
                "commit_sha": row.commit_sha,
                "test_suite_name": row.test_suite_name,
                "timestamp": row.timestamp,
                "similarity_score": round(similarity, 4),
                "failure_category": row.failure_category,
                "summary": row.triage_summary,
                "root_cause": row.root_cause,
                "suggested_steps": [],
                "failed_test_names": row.failed_test_names or [],
                "exception_names": row.exception_names or [],
            })

        log.info("Found similar failures", count=len(similar), query_id=str(ci_run_id))
        return similar

    async def upsert_embedding(
        self,
        failure_log_id: UUID,
        embedding: list[float],
    ) -> None:
        """Store or update the embedding vector for a failure log."""
        await self._db.execute(
            text("UPDATE failure_logs SET embedding = :embedding WHERE id = :id"),
            {"embedding": embedding, "id": str(failure_log_id)},
        )