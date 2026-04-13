"""Read-only catalog resource backed by the registry repository."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    NonEmptyText,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository


class CatalogDatasetSummary(BaseModel):
    """Minimal registry-backed summary for a single catalog dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: NonEmptyText
    source: NonEmptyText
    title: NonEmptyText
    update_frequency: UpdateFrequency
    health_status: DatasetHealthStatus
    coverage_status: DatasetCoverageStatus

    @classmethod
    def from_descriptor(cls, descriptor: DatasetDescriptor) -> CatalogDatasetSummary:
        """Build a summary from a full registry descriptor without exposing detail fields."""

        return cls(
            dataset_id=descriptor.dataset_id,
            source=descriptor.source,
            title=descriptor.title,
            update_frequency=descriptor.update_frequency,
            health_status=descriptor.health_status,
            coverage_status=descriptor.coverage_status,
        )


class CatalogSummary(BaseModel):
    """Read-only catalog summary suitable for later MCP exposure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_count: int = Field(ge=0)
    datasets: tuple[CatalogDatasetSummary, ...] = Field(default_factory=tuple)

    @classmethod
    def from_descriptors(cls, descriptors: Sequence[DatasetDescriptor]) -> CatalogSummary:
        """Build a deterministic catalog summary from repository descriptors."""

        datasets = tuple(
            CatalogDatasetSummary.from_descriptor(descriptor) for descriptor in descriptors
        )
        return cls(
            dataset_count=len(datasets),
            datasets=datasets,
        )


class CatalogResource:
    """Thin read-only resource layer over registry-backed dataset descriptors."""

    def __init__(self, repository: RegistryRepository) -> None:
        self._repository = repository

    def read(self) -> CatalogSummary:
        """Return immutable dataset summaries in repository order."""

        return CatalogSummary.from_descriptors(self._repository.list_datasets())
