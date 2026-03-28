"""Typed dataset metadata lookup for later MCP registration."""

from __future__ import annotations

from typing import Literal, Self

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.registry.models import DatasetDescriptor, NonEmptyText
from saudi_open_data_mcp.registry.repository import RegistryRepository


class DatasetMetadataLookupResult(BaseModel):
    """Deterministic typed output for dataset metadata lookup."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: Literal["found", "missing"]
    metadata: DatasetDescriptor | None = None

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
            metadata=metadata,
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

        descriptor = self._repository.get_dataset(dataset_id)
        if descriptor is None:
            return DatasetMetadataLookupResult.missing(dataset_id)

        return DatasetMetadataLookupResult.found(descriptor)


def register(app: FastMCP) -> None:
    """Defer FastMCP registration until server wiring is in scope."""

    _ = app
