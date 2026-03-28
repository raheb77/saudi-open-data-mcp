"""Logging helpers."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure basic structured logging for the scaffold."""

    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
