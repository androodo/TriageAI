"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import settings

LOG_LEVEL = getattr(logging, settings.log_level.upper(), logging.INFO)


def configure_logging() -> None:
    """Configure structlog for the application."""

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=LOG_LEVEL,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_level == "DEBUG"
                else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict[str, Any],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given name."""
    return structlog.get_logger(name)