"""BuildLens AI — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import configure_logging

from app.config import settings
from app.database import engine
from app.routers import health, runs
from app.utils.logging import configure_logging as _configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown."""
    _configure_logging()
    # Verify database connection on startup
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        print("✓ Database connection verified")
    except Exception as e:
        print(f"⚠ Database connection failed: {e}")
    yield
    # Cleanup
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI app."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-powered CI failure triage platform. Ingest CI runs, get AI diagnoses, "
            "find similar historical failures, and generate actionable issue drafts."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()