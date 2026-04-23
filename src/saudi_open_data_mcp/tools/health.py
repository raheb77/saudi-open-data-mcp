"""Typed dataset health lookup backed by registry metadata."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.observability import log_audit_event
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    NonEmptyText,
    RegistryNote,
    SchemaVersion,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import sanitize_dataset_id
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessResult,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


class DatasetHealthLookupResult(BaseModel):
    """Deterministic registry-backed dataset health output."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: Literal["found", "missing"]
    health_status: DatasetHealthStatus | None = None
    coverage_status: DatasetCoverageStatus | None = None
    schema_version: SchemaVersion | None = None
    caveats: tuple[RegistryNote, ...] = Field(default_factory=tuple)
    known_issues: tuple[RegistryNote, ...] = Field(default_factory=tuple)
    freshness: SnapshotFreshnessResult | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status == "found":
            if self.health_status is None:
                raise ValueError("health_status must be present when status is 'found'")
            if self.coverage_status is None:
                raise ValueError("coverage_status must be present when status is 'found'")
            if self.schema_version is None:
                raise ValueError("schema_version must be present when status is 'found'")
            return self

        if self.health_status is not None:
            raise ValueError("health_status must be absent when status is 'missing'")
        if self.coverage_status is not None:
            raise ValueError("coverage_status must be absent when status is 'missing'")
        if self.schema_version is not None:
            raise ValueError("schema_version must be absent when status is 'missing'")
        if self.caveats:
            raise ValueError("caveats must be empty when status is 'missing'")
        if self.known_issues:
            raise ValueError("known_issues must be empty when status is 'missing'")
        return self

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Exclude absent freshness evidence while preserving other explicit nulls."""

        exclude = kwargs.pop("exclude", None)
        if self.freshness is None:
            exclude = _merge_exclude(exclude, "freshness")
        return super().model_dump(*args, exclude=exclude, **kwargs)

    @classmethod
    def found(
        cls,
        *,
        dataset_id: str,
        health_status: DatasetHealthStatus,
        coverage_status: DatasetCoverageStatus,
        schema_version: str,
        caveats: tuple[str, ...],
        known_issues: tuple[str, ...],
        freshness: SnapshotFreshnessResult | None = None,
    ) -> Self:
        """Build a found health result from registry-backed metadata."""

        return cls(
            dataset_id=dataset_id,
            status="found",
            health_status=health_status,
            coverage_status=coverage_status,
            schema_version=schema_version,
            caveats=caveats,
            known_issues=known_issues,
            freshness=freshness,
        )

    @classmethod
    def missing(cls, dataset_id: str) -> Self:
        """Build an explicit missing result for an unknown dataset."""

        return cls(dataset_id=dataset_id, status="missing")


class DatasetHealthTool:
    """Registry-backed health lookup without live connector probing."""

    def __init__(
        self,
        repository: RegistryRepository,
        snapshot_store: SnapshotStore | Path | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore) or snapshot_store is None
            else SnapshotStore(snapshot_store)
        )

    def get_dataset_health(
        self,
        dataset_id: str,
        *,
        reference_time: datetime | None = None,
    ) -> DatasetHealthLookupResult:
        """Return exact-match dataset health from the registry."""

        normalized_dataset_id = sanitize_dataset_id(dataset_id)
        descriptor = self._repository.get_dataset(normalized_dataset_id)
        if descriptor is None:
            result = DatasetHealthLookupResult.missing(normalized_dataset_id)
            _audit_health_result(result, source=None)
            return result

        health_metadata = self._repository.get_health(normalized_dataset_id)
        health_status = (
            health_metadata.health_status
            if health_metadata is not None
            else descriptor.health_status
        )
        freshness = (
            _bind_canonical_dataset_id(
                descriptor=descriptor,
                freshness=evaluate_snapshot_freshness(
                    source=descriptor.source,
                    dataset_id=descriptor.source_locator,
                    snapshot_store=self._snapshot_store,
                    reference_time=reference_time,
                    update_frequency=descriptor.update_frequency,
                ),
            )
            if self._snapshot_store is not None
            else None
        )

        result = DatasetHealthLookupResult.found(
            dataset_id=descriptor.dataset_id,
            health_status=health_status,
            coverage_status=descriptor.coverage_status,
            schema_version=descriptor.schema_version,
            caveats=descriptor.caveats,
            known_issues=descriptor.known_issues,
            freshness=freshness,
        )
        _audit_health_result(result, source=descriptor.source)
        return result


def _merge_exclude(exclude: object, field_name: str) -> object:
    """Merge a field exclusion into an existing model_dump exclude value."""

    if exclude is None:
        return {field_name}
    if isinstance(exclude, set):
        return {*exclude, field_name}
    if isinstance(exclude, dict):
        merged = dict(exclude)
        merged[field_name] = True
        return merged
    return exclude


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    freshness: SnapshotFreshnessResult,
) -> SnapshotFreshnessResult:
    """Rewrite source-locator-based freshness output to the canonical dataset identity."""

    return freshness.model_copy(update={"dataset_id": descriptor.dataset_id})


def _audit_health_result(
    result: DatasetHealthLookupResult,
    *,
    source: str | None,
) -> None:
    """Emit one audit event for registry-backed dataset health lookup."""

    log_audit_event(
        "dataset_health",
        result_status=result.status,
        dataset_id=result.dataset_id,
        source=source,
        health_status=(
            result.health_status.value
            if result.health_status is not None
            else None
        ),
        coverage_status=(
            result.coverage_status.value
            if result.coverage_status is not None
            else None
        ),
        freshness_status=(
            result.freshness.status.value
            if result.freshness is not None
            else None
        ),
    )
