"""Health models."""

from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    """Health state."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class HealthReport(BaseModel):
    """Health report placeholder."""

    dataset_id: str
    status: HealthStatus
    detail: str = "scaffold"
