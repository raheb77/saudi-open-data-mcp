"""Typed registry metadata models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SchemaVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d+\.\d+\.\d+$"),
]
RegistryNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UpdateFrequency(StrEnum):
    """Declared dataset update frequency."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"
    UNSPECIFIED = "unspecified"


class DatasetHealthStatus(StrEnum):
    """Operational dataset health state for v0.1."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class DatasetDescriptor(BaseModel):
    """Registry-owned dataset descriptor metadata."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    source: NonEmptyText
    title: NonEmptyText
    description: NonEmptyText
    schema_version: SchemaVersion
    update_frequency: UpdateFrequency
    health_status: DatasetHealthStatus
    caveats: tuple[RegistryNote, ...] = Field(default_factory=tuple)
    known_issues: tuple[RegistryNote, ...] = Field(default_factory=tuple)


class HealthMetadata(BaseModel):
    """Registry-owned health metadata."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    health_status: DatasetHealthStatus
