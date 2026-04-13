"""Shared result-metadata models for the current MCP core tool outputs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ResultDataOrigin(StrEnum):
    """Consistent operator-facing origin metadata when a result has data provenance."""

    LOCAL_SNAPSHOT = "local_snapshot"
    LIVE_REFRESH = "live_refresh"
    STALE_SNAPSHOT = "stale_snapshot"


class ResultDegradationReason(StrEnum):
    """Explicit degraded-state reasons when a result is usable but not ideal."""

    NORMALIZATION_LIMITED = "normalization_limited"
    STALE_FALLBACK_AFTER_REFRESH_FAILURE = "stale_fallback_after_refresh_failure"


class ObservationRecencyStatus(StrEnum):
    """Explicit analyst-facing recency status for the latest normalized observation."""

    CURRENT = "current"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class ObservationRecencyAssessment(BaseModel):
    """Governed observation-recency assessment derived from normalized records."""

    model_config = ConfigDict(extra="forbid")

    latest_observation: str
    latest_observation_field: str
    status: ObservationRecencyStatus
    warning: str | None = None

    @model_validator(mode="after")
    def _validate_warning_consistency(self) -> "ObservationRecencyAssessment":
        if self.status is ObservationRecencyStatus.STALE and self.warning is None:
            raise ValueError("stale observation recency assessments must include warning")
        if self.status is not ObservationRecencyStatus.STALE and self.warning is not None:
            raise ValueError(
                "only stale observation recency assessments may include warning"
            )
        return self
