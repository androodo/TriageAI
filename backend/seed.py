"""Seed script — populates the database with demo CI run data.

Usage:
    python -m seed
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.ci_run import CIRun, CIStatus
from app.models.failure_log import FailureLog
from app.models.triage_result import TriageResult, FailureCategory
from app.services.log_parser import LogParser
from app.services.llm import llm_provider


async def seed() -> None:
    """Load seed data and insert into the database."""
    seed_file = Path(__file__).parent / "seed_data" / "seed_runs.json"
    raw_data = json.loads(seed_file.read_text())

    parser = LogParser()
    async with AsyncSessionLocal() as db:
        for record in raw_data:
            triage_data = record.pop("triage", None)
            raw_log = record["raw_log_text"]
            parsed = parser.parse(raw_log)

            ci_run = CIRun(
                repo_name=record["repo_name"],
                branch=record["branch"],
                commit_sha=record["commit_sha"],
                pipeline_id=record["pipeline_id"],
                environment=record["environment"],
                status=CIStatus(record["status"]),
                test_suite_name=record["test_suite_name"],
                failed_test_names=record["failed_test_names"],
                timestamp=datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00")),
            )
            db.add(ci_run)
            await db.flush()

            if ci_run.status == CIStatus.FAILED:
                # Generate a fake embedding (no real LLM calls during seeding)
                embedding = await llm_provider.embed(parsed.cleaned_log_text[:500])

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
                    embedding=embedding,
                )
                db.add(failure_log)
                await db.flush()

                if triage_data:
                    triage = TriageResult(
                        ci_run_id=ci_run.id,
                        failure_category=FailureCategory(triage_data["failure_category"]),
                        confidence_score=triage_data["confidence_score"],
                        summary=triage_data["summary"],
                        root_cause=triage_data["root_cause"],
                        suggested_steps=triage_data["suggested_steps"],
                        owner_guess=triage_data.get("owner_guess"),
                        issue_title=triage_data["issue_title"],
                        issue_body=triage_data["issue_body"],
                        model_used="seed-data (pre-computed)",
                    )
                    db.add(triage)

            await db.commit()
            print(f"  ✓ Seeded: {ci_run.repo_name} / {ci_run.branch} ({ci_run.status.value})")

    print(f"\n✅ Seeded {len(raw_data)} CI runs")


if __name__ == "__main__":
    print("🌱 Seeding BuildLens AI database...")
    asyncio.run(seed())