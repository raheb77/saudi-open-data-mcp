"""Typed local-only querying over canonical normalized records."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
    CanonicalRecord,
    NormalizationFailure,
    NormalizationPipeline,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import DatasetDescriptor, NonEmptyText
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

QueryFilterValue = str | int | float | bool | None


class DatasetQueryStatus(StrEnum):
    """Explicit local query status for v0.1."""

    UNKNOWN_DATASET = "unknown_dataset"
    SNAPSHOT_MISSING = "snapshot_missing"
    LIMITED = "limited"
    FAILED = "failed"
    SUCCESS = "success"


class QueryFailureStage(StrEnum):
    """Failure stage for local query execution."""

    SNAPSHOT_READ = "snapshot_read"
    NORMALIZATION = "normalization"


class QueryFailure(BaseModel):
    """Typed failure details for query execution."""

    model_config = ConfigDict(extra="forbid")

    stage: QueryFailureStage
    error_type: str
    message: str


class DatasetQueryResult(BaseModel):
    """Typed result for exact dataset queries over local normalized records."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: DatasetQueryStatus
    source: NonEmptyText | None = None
    applied_filters: dict[str, QueryFilterValue] = Field(default_factory=dict)
    limit: int | None = Field(default=None, ge=1)
    total_records_before_filter: int | None = Field(default=None, ge=0)
    matched_records: tuple[CanonicalRecord, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    failure: QueryFailure | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status is DatasetQueryStatus.UNKNOWN_DATASET:
            if self.source is not None:
                raise ValueError("unknown_dataset results must not include source")
            if self.total_records_before_filter is not None:
                raise ValueError(
                    "unknown_dataset results must not include total_records_before_filter"
                )
            if self.matched_records or self.limitations or self.failure is not None:
                raise ValueError(
                    "unknown_dataset results must not include records, limitations, or failure"
                )
            return self

        if self.source is None:
            raise ValueError("known dataset query results must include source")

        if self.status is DatasetQueryStatus.SNAPSHOT_MISSING:
            if self.total_records_before_filter is not None:
                raise ValueError(
                    "snapshot_missing results must not include total_records_before_filter"
                )
            if self.matched_records or self.limitations or self.failure is not None:
                raise ValueError(
                    "snapshot_missing results must not include records, limitations, or failure"
                )
            return self

        if self.status is DatasetQueryStatus.LIMITED:
            if not self.limitations:
                raise ValueError("limited results must include explicit limitations")
            if self.total_records_before_filter is not None or self.matched_records:
                raise ValueError(
                    "limited results must not include queryable record counts or matches"
                )
            if self.failure is not None:
                raise ValueError("limited results must not include failure details")
            return self

        if self.status is DatasetQueryStatus.FAILED:
            if self.failure is None:
                raise ValueError("failed results must include failure details")
            if self.total_records_before_filter is not None or self.matched_records:
                raise ValueError(
                    "failed results must not include queryable record counts or matches"
                )
            if self.limitations:
                raise ValueError("failed results must not include limitations")
            return self

        if self.failure is not None or self.limitations:
            raise ValueError("successful query results must not include failure or limitations")
        if self.total_records_before_filter is None:
            raise ValueError("successful query results must include total_records_before_filter")
        if self.total_records_before_filter < len(self.matched_records):
            raise ValueError(
                "total_records_before_filter must be greater than or equal to matched_records"
            )

        for record in self.matched_records:
            if record.dataset_id != self.dataset_id:
                raise ValueError("matched record dataset_id must match query dataset_id")
            if record.source != self.source:
                raise ValueError("matched record source must match query source")

        return self

    @classmethod
    def unknown_dataset(
        cls,
        *,
        dataset_id: str,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build an explicit unknown-dataset query result."""

        return cls(
            dataset_id=dataset_id,
            status=DatasetQueryStatus.UNKNOWN_DATASET,
            applied_filters=applied_filters,
            limit=limit,
        )

    @classmethod
    def snapshot_missing(
        cls,
        *,
        descriptor: DatasetDescriptor,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build an explicit result for a known dataset without a local snapshot."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.SNAPSHOT_MISSING,
            source=descriptor.source,
            applied_filters=applied_filters,
            limit=limit,
        )

    @classmethod
    def limited(
        cls,
        *,
        descriptor: DatasetDescriptor,
        normalization_result: NormalizationResult,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build a limited result when local normalization cannot expose records."""

        limitations = _collect_limitations(normalization_result)
        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.LIMITED,
            source=descriptor.source,
            applied_filters=applied_filters,
            limit=limit,
            limitations=limitations,
        )

    @classmethod
    def failed(
        cls,
        *,
        descriptor: DatasetDescriptor,
        stage: QueryFailureStage,
        error_type: str,
        message: str,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build an explicit failure result for snapshot read or normalization failure."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.FAILED,
            source=descriptor.source,
            applied_filters=applied_filters,
            limit=limit,
            failure=QueryFailure(
                stage=stage,
                error_type=error_type,
                message=message,
            ),
        )

    @classmethod
    def success(
        cls,
        *,
        descriptor: DatasetDescriptor,
        records: tuple[CanonicalRecord, ...],
        total_records_before_filter: int,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build a successful local query result."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.SUCCESS,
            source=descriptor.source,
            applied_filters=applied_filters,
            limit=limit,
            total_records_before_filter=total_records_before_filter,
            matched_records=records,
        )


class QueryPipeline(Protocol):
    """Minimal protocol for injecting the existing normalization pipeline."""

    def normalize(self, raw_payload: Any) -> NormalizationResult:
        """Return a typed normalization result for a raw payload."""


class DatasetQueryTool:
    """Local-only exact query layer over registry metadata, snapshots, and normalization."""

    def __init__(
        self,
        repository: RegistryRepository,
        snapshot_store: SnapshotStore | Path,
        *,
        normalization_pipeline: QueryPipeline | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore)
            else SnapshotStore(snapshot_store)
        )
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()

    def query_dataset(
        self,
        dataset_id: str,
        *,
        filters: Mapping[str, QueryFilterValue] | None = None,
        limit: int | None = None,
    ) -> DatasetQueryResult:
        """Query local canonical records for an exact registry dataset identifier."""

        normalized_dataset_id = _validate_dataset_id(dataset_id)
        normalized_filters = _normalize_filters(filters)
        normalized_limit = _normalize_limit(limit)

        descriptor = self._repository.get_dataset(normalized_dataset_id)
        if descriptor is None:
            return DatasetQueryResult.unknown_dataset(
                dataset_id=normalized_dataset_id,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )

        try:
            raw_payload = self._snapshot_store.read_snapshot(
                descriptor.source,
                descriptor.dataset_id,
            )
        except FileNotFoundError:
            return DatasetQueryResult.snapshot_missing(
                descriptor=descriptor,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
        except Exception as exc:
            return DatasetQueryResult.failed(
                descriptor=descriptor,
                stage=QueryFailureStage.SNAPSHOT_READ,
                error_type=type(exc).__name__,
                message=str(exc),
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )

        normalization_result = self._normalization_pipeline.normalize(raw_payload)
        if normalization_result.status is NormalizationPipelineStatus.FAILED:
            return DatasetQueryResult.failed(
                descriptor=descriptor,
                stage=QueryFailureStage.NORMALIZATION,
                error_type=_normalization_error_type(normalization_result.failure),
                message=_normalization_error_message(normalization_result.failure),
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )

        if normalization_result.status is NormalizationPipelineStatus.LIMITED:
            return DatasetQueryResult.limited(
                descriptor=descriptor,
                normalization_result=normalization_result,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )

        filtered_records = _apply_filters(
            normalization_result.records,
            normalized_filters,
        )
        limited_records = (
            filtered_records[:normalized_limit]
            if normalized_limit is not None
            else filtered_records
        )
        return DatasetQueryResult.success(
            descriptor=descriptor,
            records=limited_records,
            total_records_before_filter=len(normalization_result.records),
            applied_filters=normalized_filters,
            limit=normalized_limit,
        )


def _validate_dataset_id(dataset_id: str) -> str:
    """Validate and normalize an exact registry dataset identifier."""

    value = dataset_id.strip()
    if not value:
        raise ValueError("dataset_id must not be empty")
    return value


def _normalize_limit(limit: int | None) -> int | None:
    """Validate the optional result limit."""

    if limit is None:
        return None
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    return limit


def _normalize_filters(
    filters: Mapping[str, QueryFilterValue] | None,
) -> dict[str, QueryFilterValue]:
    """Validate and normalize exact-match query filters."""

    if filters is None:
        return {}

    normalized: dict[str, QueryFilterValue] = {}
    for key, value in filters.items():
        if not isinstance(key, str):
            raise ValueError("query filter keys must be strings")
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("query filter keys must not be empty")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError(
                "query filter values must be strings, numbers, booleans, or null"
            )
        normalized[normalized_key] = value
    return normalized


def _apply_filters(
    records: tuple[CanonicalRecord, ...],
    filters: dict[str, QueryFilterValue],
) -> tuple[CanonicalRecord, ...]:
    """Apply exact-match filters while preserving original record ordering."""

    if not filters:
        return records

    return tuple(
        record
        for record in records
        if _record_matches_filters(record, filters)
    )


def _record_matches_filters(
    record: CanonicalRecord,
    filters: dict[str, QueryFilterValue],
) -> bool:
    """Return whether a canonical record matches all exact field filters."""

    for field_name, expected_value in filters.items():
        if field_name not in record.fields:
            return False
        if record.fields[field_name] != expected_value:
            return False
    return True


def _collect_limitations(normalization_result: NormalizationResult) -> tuple[str, ...]:
    """Collect explicit limitations from a limited normalization result."""

    if normalization_result.validation_result is not None:
        limitations = normalization_result.validation_result.limitations
        if limitations:
            return limitations

    if normalization_result.mapping_result is not None:
        limitations = normalization_result.mapping_result.limitations
        if limitations:
            return limitations

    raise ValueError("limited normalization result must include explicit limitations")


def _normalization_error_type(failure: NormalizationFailure | None) -> str:
    """Return a stable normalization error type for failed query results."""

    if failure is None:
        return "NormalizationPipelineError"
    return failure.error_type


def _normalization_error_message(failure: NormalizationFailure | None) -> str:
    """Return a stable normalization error message for failed query results."""

    if failure is None:
        return "Normalization pipeline failed without structured failure details"
    return failure.message


def register(app: FastMCP) -> None:
    """Defer FastMCP registration until server wiring expands to query support."""

    _ = app
