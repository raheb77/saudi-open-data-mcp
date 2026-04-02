"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    """Configure process-local logging for structured JSON-line messages."""

    resolved_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    if not root_logger.handlers:
        logging.basicConfig(level=resolved_level, format="%(message)s")


def get_logger(name: str) -> logging.Logger:
    """Return a module logger for local structured event logging."""

    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured JSON log event with deterministic field ordering."""

    payload = {
        "event": event,
        "level": logging.getLevelName(level).lower(),
        "logger": logger.name,
        **fields,
    }
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
