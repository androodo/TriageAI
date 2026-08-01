"""Application-wide settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for the TriageAI backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://buildlens:buildlens_dev@localhost:5432/buildlens"
    database_url_sync: str = "postgresql+psycopg2://buildlens:buildlens_dev@localhost:5432/buildlens"

    # ── LLM / AI ────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # ── Application ─────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_name: str = "TriageAI"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── Pagination defaults ──────────────────────────────────────────────────────
    default_page_size: int = 20
    max_page_size: int = 100

    # ── Similarity search ───────────────────────────────────────────────────────
    similar_failures_count: int = 5
    similarity_search_filter: str | None = None  # "repo" or "global"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()