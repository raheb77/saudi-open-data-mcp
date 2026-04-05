"""Shared result-metadata enums for the current MCP core tool outputs."""

from __future__ import annotations

from enum import StrEnum


class ResultDataOrigin(StrEnum):
    """Consistent operator-facing origin metadata when a result has data provenance."""

    LOCAL_SNAPSHOT = "local_snapshot"
    LIVE_REFRESH = "live_refresh"
    STALE_SNAPSHOT = "stale_snapshot"


class ResultDegradationReason(StrEnum):
    """Explicit degraded-state reasons when a result is usable but not ideal."""

    NORMALIZATION_LIMITED = "normalization_limited"
    STALE_FALLBACK_AFTER_REFRESH_FAILURE = "stale_fallback_after_refresh_failure"
