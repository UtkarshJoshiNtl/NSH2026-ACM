"""
backend/logging_config.py — Structured Logging Configuration
===========================================================
Configures structured logging with correlation IDs for distributed tracing.
"""

import logging
import uuid
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger
from backend.config import settings

# Context variable for correlation ID
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def filter(self, record):
        record.correlation_id = correlation_id.get()
        return True


def setup_logging():
    """Configure structured JSON logging with correlation IDs."""

    # Create formatter
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(correlation_id)s",
        timestamp=True,
    )

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())

    logger.addHandler(handler)

    return logger


def get_correlation_id() -> str:
    """Get or create a correlation ID for the current request."""
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str):
    """Set the correlation ID for the current request."""
    correlation_id.set(cid)
