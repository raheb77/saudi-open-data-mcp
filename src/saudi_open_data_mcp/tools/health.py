"""Typed dataset health lookup backed by registry metadata."""

from __future__ import annotations

from typing import Literal, Self

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.registry.models import (
    DatasetHealthStatus,
    NonEmptyText,
    RegistryNote,
    SchemaVersion,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository


class DatasetHealthLookupResult(BaseModel):
    """Deterministic registry-backed dataset health output."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: Literal["found", "missing"]
    health_status: DatasetHealthStatus | None = None
    schema_version: SchemaVersion | None = None
    caveats: tuple[RegistryNote, ...] = Field(default_factory=tuple)
    known_issues: tuple[RegistryNote, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status == "found":
            if self.health_status is None:
                raise ValueError("health_status must be present when status is 'found'")
            if self.schema_version is None:
                raise ValueError("schema_version must be present when status is 'found'")
            return self

        if self.health_status is not None:
            raise ValueError("health_status must be absent when status is 'missing'")
        if self.schema_version is not None:
            raise ValueError("schema_version must be absent when status is 'missing'")
        if self.caveats:
            raise ValueError("caveats must be empty when status is 'missing'")
        if self.known_issues:
            raise ValueError("known_issues must be empty when status is 'missing'")
        return self

    @classmethod
    def found(
        cls,
        *,
        dataset_id: str,
        health_status: DatasetHealthStatus,
        schema_version: str,
        caveats: tuple[str, ...],
        known_issues: tuple[str, ...],
    ) -> Self:
        """Build a found health result from registry-backed metadata."""

        return cls(
            dataset_id=dataset_id,
            status="found",
            health_status=health_status,
            schema_version=schema_version,
            caveats=caveats,
            known_issues=known_issues,
        )

    @classmethod
    def missing(cls, dataset_id: str) -> Self:
        """Build an explicit missing result for an unknown dataset."""

        return cls(dataset_id=dataset_id, status="missing")


class DatasetHealthTool:
    """Registry-backed health lookup without live connector probing."""

    def __init__(self, repository: RegistryRepository) -> None:
        self._repository = repository

    def get_dataset_health(self, dataset_id: str) -> DatasetHealthLookupResult:
        """Return exact-match dataset health from the registry."""

        descriptor = self._repository.get_dataset(dataset_id)
        if descriptor is None:
            return DatasetHealthLookupResult.missing(dataset_id)

        health_metadata = self._repository.get_health(dataset_id)
        health_status = (
            health_metadata.health_status
            if health_metadata is not None
            else descriptor.health_status
        )

        return DatasetHealthLookupResult.found(
            dataset_id=descriptor.dataset_id,
            health_status=health_status,
            schema_version=descriptor.schema_version,
            caveats=descriptor.caveats,
            known_issues=descriptor.known_issues,
        )


def register(app: FastMCP) -> None:
    """Defer FastMCP registration until server wiring expands to health support."""

    _ = app
