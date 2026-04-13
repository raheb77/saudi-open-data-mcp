"""Typed registry metadata models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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


class DatasetCoverageStatus(StrEnum):
    """Governed dataset support/readiness state."""

    QUERYABLE = "queryable"
    LIMITED = "limited"
    CATALOG_ONLY = "catalog_only"
    UNAVAILABLE = "unavailable"


class DatasetDescriptor(BaseModel):
    """Registry-owned dataset descriptor metadata.

    `dataset_id` is the canonical registry identifier.
    `source_locator` is the source-specific locator needed at the source boundary.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    source: NonEmptyText
    source_locator: NonEmptyText
    title: NonEmptyText
    description: NonEmptyText
    schema_version: SchemaVersion
    update_frequency: UpdateFrequency
    health_status: DatasetHealthStatus
    coverage_status: DatasetCoverageStatus = DatasetCoverageStatus.CATALOG_ONLY
    caveats: tuple[RegistryNote, ...] = Field(default_factory=tuple)
    known_issues: tuple[RegistryNote, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_declared_coverage_status(self) -> "DatasetDescriptor":
        if self.coverage_status is DatasetCoverageStatus.UNAVAILABLE:
            raise ValueError(
                "dataset descriptors must declare queryable, limited, or "
                "catalog_only coverage_status"
            )
        return self


class HealthMetadata(BaseModel):
    """Registry-owned health metadata."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    health_status: DatasetHealthStatus
