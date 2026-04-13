"""Typed dataset metadata lookup for later MCP registration."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.observability import log_audit_event
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    NonEmptyText,
    RegistryNote,
    SchemaVersion,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import sanitize_dataset_id


class PublicDatasetMetadata(BaseModel):
    """Operator-facing dataset metadata without internal source locator details."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    source: NonEmptyText
    title: NonEmptyText
    description: NonEmptyText
    schema_version: SchemaVersion
    update_frequency: UpdateFrequency
    health_status: DatasetHealthStatus
    coverage_status: DatasetCoverageStatus
    caveats: tuple[RegistryNote, ...]
    known_issues: tuple[RegistryNote, ...]

    @classmethod
    def from_descriptor(cls, descriptor: DatasetDescriptor) -> Self:
        """Build public metadata from a registry-owned descriptor."""

        return cls(
            dataset_id=descriptor.dataset_id,
            source=descriptor.source,
            title=descriptor.title,
            description=descriptor.description,
            schema_version=descriptor.schema_version,
            update_frequency=descriptor.update_frequency,
            health_status=descriptor.health_status,
            coverage_status=descriptor.coverage_status,
            caveats=descriptor.caveats,
            known_issues=descriptor.known_issues,
        )


class DatasetMetadataLookupResult(BaseModel):
    """Deterministic typed output for dataset metadata lookup."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: Literal["found", "missing"]
    metadata: PublicDatasetMetadata | None = None

    @model_validator(mode="after")
    def _validate_status_and_metadata(self) -> Self:
        if self.status == "found" and self.metadata is None:
            raise ValueError("metadata must be present when status is 'found'")

        if self.status == "missing" and self.metadata is not None:
            raise ValueError("metadata must be absent when status is 'missing'")

        if self.metadata is not None and self.metadata.dataset_id != self.dataset_id:
            raise ValueError("dataset_id must match metadata.dataset_id")

        return self

    @classmethod
    def found(cls, metadata: DatasetDescriptor) -> Self:
        """Build a found result from a registry descriptor."""

        return cls(
            dataset_id=metadata.dataset_id,
            status="found",
            metadata=PublicDatasetMetadata.from_descriptor(metadata),
        )

    @classmethod
    def missing(cls, dataset_id: str) -> Self:
        """Build an explicit missing result for an unknown dataset."""

        return cls(dataset_id=dataset_id, status="missing")


class DatasetMetadataTool:
    """Typed metadata lookup layer over the registry repository."""

    def __init__(self, repository: RegistryRepository) -> None:
        self._repository = repository

    def get_dataset_metadata(self, dataset_id: str) -> DatasetMetadataLookupResult:
        """Return exact-match dataset metadata from the registry."""

        normalized_dataset_id = sanitize_dataset_id(dataset_id)
        descriptor = self._repository.get_dataset(normalized_dataset_id)
        if descriptor is None:
            result = DatasetMetadataLookupResult.missing(normalized_dataset_id)
            _audit_metadata_result(result)
            return result

        result = DatasetMetadataLookupResult.found(descriptor)
        _audit_metadata_result(result)
        return result


def _audit_metadata_result(result: DatasetMetadataLookupResult) -> None:
    """Emit one audit event for exact metadata lookup."""

    log_audit_event(
        "dataset_metadata",
        result_status=result.status,
        dataset_id=result.dataset_id,
        source=result.metadata.source if result.metadata is not None else None,
    )
