"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.services.llm import llm_provider

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    llm: str
    version: str


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check the health of all TriageAI dependencies."""
    # Check database connectivity
    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    # Check LLM connectivity
    llm_status = "healthy"
    provider_name = type(llm_provider).__name__
    if provider_name == "NoOpProvider":
        llm_status = "no-api-key-configured"
    else:
        try:
            await llm_provider.chat(
                [{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
        except Exception as e:
            llm_status = f"unavailable: {e}"

    overall = "healthy"
    if "unhealthy" in db_status or "unavailable" in llm_status:
        overall = "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        llm=llm_status,
        version=settings.app_version,
    )