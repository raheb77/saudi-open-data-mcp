"""Typed registry-backed dataset search."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    NonEmptyText,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import sanitize_search_query


class DatasetSearchMode(StrEnum):
    """Registry search mode based on the applied query."""

    FILTERED = "filtered"
    ALL_DATASETS = "all_datasets"


class DatasetSearchStatus(StrEnum):
    """Top-level result status for registry-backed search."""

    RESULTS = "results"
    NO_RESULTS = "no_results"


class DatasetSearchMatch(BaseModel):
    """Concise registry-backed summary for a search hit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: NonEmptyText
    source: NonEmptyText
    title: NonEmptyText
    update_frequency: UpdateFrequency
    health_status: DatasetHealthStatus

    @classmethod
    def from_descriptor(cls, descriptor: DatasetDescriptor) -> Self:
        """Build a search summary from a registry descriptor."""

        return cls(
            dataset_id=descriptor.dataset_id,
            source=descriptor.source,
            title=descriptor.title,
            update_frequency=descriptor.update_frequency,
            health_status=descriptor.health_status,
        )


class DatasetSearchResult(BaseModel):
    """Deterministic typed search output over registry metadata."""

    model_config = ConfigDict(extra="forbid")

    query: str
    normalized_query: str
    status: DatasetSearchStatus
    mode: DatasetSearchMode
    match_count: int = Field(ge=0)
    matches: tuple[DatasetSearchMatch, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.match_count != len(self.matches):
            raise ValueError("match_count must equal the number of matches")

        if self.match_count > 0:
            if self.status is not DatasetSearchStatus.RESULTS:
                raise ValueError("non-empty matches require results status")
        elif self.status is not DatasetSearchStatus.NO_RESULTS:
            raise ValueError("empty matches require no_results status")

        if self.normalized_query:
            if self.mode is not DatasetSearchMode.FILTERED:
                raise ValueError("non-empty normalized_query requires filtered search mode")
        elif self.mode is not DatasetSearchMode.ALL_DATASETS:
            raise ValueError("empty normalized_query requires all_datasets search mode")

        return self

    @classmethod
    def from_descriptors(
        cls,
        *,
        query: str,
        descriptors: list[DatasetDescriptor],
    ) -> Self:
        """Build a typed search result from repository-ordered descriptors."""

        normalized_query = query.strip()
        mode = (
            DatasetSearchMode.FILTERED
            if normalized_query
            else DatasetSearchMode.ALL_DATASETS
        )
        matches = tuple(
            DatasetSearchMatch.from_descriptor(descriptor) for descriptor in descriptors
        )
        status = (
            DatasetSearchStatus.RESULTS
            if matches
            else DatasetSearchStatus.NO_RESULTS
        )
        return cls(
            query=query,
            normalized_query=normalized_query,
            status=status,
            mode=mode,
            match_count=len(matches),
            matches=matches,
        )


class DatasetSearchTool:
    """Thin deterministic search layer over the registry repository."""

    def __init__(self, repository: RegistryRepository) -> None:
        self._repository = repository

    def search_datasets(self, query: str) -> DatasetSearchResult:
        """Search registry-backed datasets using repository substring matching."""

        validated_query = sanitize_search_query(query)
        descriptors = self._repository.search_datasets(validated_query)
        return DatasetSearchResult.from_descriptors(
            query=validated_query,
            descriptors=descriptors,
        )
