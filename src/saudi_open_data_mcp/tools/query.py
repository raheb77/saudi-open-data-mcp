"""Typed local-only querying over canonical normalized records."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
    CanonicalRecord,
    NormalizationFailure,
    NormalizationPipeline,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.observability import get_logger, log_audit_event, log_event
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    NonEmptyText,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import (
    sanitize_dataset_id,
    sanitize_query_filter_key,
    sanitize_query_filter_string_value,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.observation_recency import assess_observation_recency
from saudi_open_data_mcp.tools.result_metadata import (
    ObservationRecencyAssessment,
    ResultDataOrigin,
    ResultDegradationReason,
)

QueryFilterValue = str | int | float | bool | None
MAX_QUERY_RESULT_LIMIT = 1000
REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_QUERY_LIMITATION = (
    "dataset_registry_declares_no_current_queryable_support"
)
QUERY_SNAPSHOT_READ_FAILURE_MESSAGE = "local snapshot read failed"
LOGGER = get_logger(__name__)


class DatasetQueryStatus(StrEnum):
    """Explicit local query status for v0.1."""

    MISSING = "missing"
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
    coverage_status: DatasetCoverageStatus
    source: NonEmptyText | None = None
    data_origin: ResultDataOrigin | None = None
    applied_filters: dict[str, QueryFilterValue] = Field(default_factory=dict)
    limit: int | None = Field(default=None, ge=1)
    total_records_before_filter: int | None = Field(default=None, ge=0)
    failure_stage: QueryFailureStage | None = None
    degradation_reason: ResultDegradationReason | None = None
    observation_recency: ObservationRecencyAssessment | None = None
    matched_records: tuple[CanonicalRecord, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    failure: QueryFailure | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status is DatasetQueryStatus.MISSING:
            if self.coverage_status is not DatasetCoverageStatus.UNAVAILABLE:
                raise ValueError("missing results must expose unavailable coverage_status")
            if self.source is not None or self.data_origin is not None:
                raise ValueError("missing results must not include source or data_origin")
            if self.total_records_before_filter is not None:
                raise ValueError("missing results must not include total_records_before_filter")
            if (
                self.matched_records
                or self.limitations
                or self.failure is not None
                or self.failure_stage is not None
                or self.degradation_reason is not None
                or self.observation_recency is not None
            ):
                raise ValueError(
                    "missing results must not include records, limitations, failure, "
                    "failure_stage, degradation_reason, or observation_recency"
                )
            return self

        if self.source is None:
            raise ValueError("known dataset query results must include source")

        if self.status is DatasetQueryStatus.SNAPSHOT_MISSING:
            if self.coverage_status is not DatasetCoverageStatus.UNAVAILABLE:
                raise ValueError(
                    "snapshot_missing results must expose unavailable coverage_status"
                )
            if self.data_origin is not None:
                raise ValueError("snapshot_missing results must not include data_origin")
            if self.total_records_before_filter is not None:
                raise ValueError(
                    "snapshot_missing results must not include total_records_before_filter"
                )
            if (
                self.matched_records
                or self.limitations
                or self.failure is not None
                or self.failure_stage is not None
                or self.degradation_reason is not None
                or self.observation_recency is not None
            ):
                raise ValueError(
                    "snapshot_missing results must not include records, limitations, "
                    "failure, failure_stage, degradation_reason, or observation_recency"
                )
            return self

        if self.data_origin is not ResultDataOrigin.LOCAL_SNAPSHOT:
            raise ValueError("query results backed by local artifacts must expose data_origin")

        if self.status is DatasetQueryStatus.LIMITED:
            if self.coverage_status not in {
                DatasetCoverageStatus.LIMITED,
                DatasetCoverageStatus.CATALOG_ONLY,
            }:
                raise ValueError(
                    "limited results must expose limited or catalog_only coverage_status"
                )
            if not self.limitations:
                raise ValueError("limited results must include explicit limitations")
            if self.total_records_before_filter is not None or self.matched_records:
                raise ValueError(
                    "limited results must not include queryable record counts or matches"
                )
            if self.failure is not None or self.failure_stage is not None:
                raise ValueError("limited results must not include failure details")
            if self.degradation_reason is not ResultDegradationReason.NORMALIZATION_LIMITED:
                raise ValueError(
                    "limited results must expose normalization_limited degradation_reason"
                )
            return self

        if self.status is DatasetQueryStatus.FAILED:
            if self.coverage_status is not DatasetCoverageStatus.UNAVAILABLE:
                raise ValueError("failed results must expose unavailable coverage_status")
            if self.failure is None:
                raise ValueError("failed results must include failure details")
            if self.failure_stage is not self.failure.stage:
                raise ValueError("failed results must expose matching failure_stage")
            if self.total_records_before_filter is not None or self.matched_records:
                raise ValueError(
                    "failed results must not include queryable record counts or matches"
                )
            if self.limitations or self.degradation_reason is not None:
                raise ValueError(
                    "failed results must not include limitations or degradation_reason"
                )
            if self.observation_recency is not None:
                raise ValueError("failed results must not include observation_recency")
            return self

        if self.coverage_status is not DatasetCoverageStatus.QUERYABLE:
            raise ValueError("successful query results must expose queryable coverage_status")
        if self.failure is not None or self.failure_stage is not None or self.limitations:
            raise ValueError(
                "successful query results must not include failure, failure_stage, or limitations"
            )
        if self.degradation_reason is not None:
            raise ValueError("successful query results must not include degradation_reason")
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
    def missing(
        cls,
        *,
        dataset_id: str,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
    ) -> Self:
        """Build an explicit missing query result for an unknown dataset."""

        return cls(
            dataset_id=dataset_id,
            status=DatasetQueryStatus.MISSING,
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
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
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            source=descriptor.source,
            applied_filters=applied_filters,
            limit=limit,
        )

    @classmethod
    def limited(
        cls,
        *,
        descriptor: DatasetDescriptor,
        applied_filters: dict[str, QueryFilterValue],
        limit: int | None,
        normalization_result: NormalizationResult | None = None,
        limitations: tuple[str, ...] | None = None,
        observation_recency: ObservationRecencyAssessment | None = None,
    ) -> Self:
        """Build a limited result when local normalization cannot expose records."""

        resolved_limitations = (
            limitations
            if limitations is not None
            else _collect_limitations(normalization_result)
            if normalization_result is not None
            else ()
        )
        if not resolved_limitations:
            raise ValueError("limited query results must include explicit limitations")
        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.LIMITED,
            coverage_status=_resolve_limited_query_coverage_status(
                descriptor.coverage_status
            ),
            source=descriptor.source,
            data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
            applied_filters=applied_filters,
            limit=limit,
            degradation_reason=ResultDegradationReason.NORMALIZATION_LIMITED,
            observation_recency=observation_recency,
            limitations=resolved_limitations,
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
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            source=descriptor.source,
            data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
            applied_filters=applied_filters,
            limit=limit,
            failure_stage=stage,
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
        observation_recency: ObservationRecencyAssessment | None = None,
    ) -> Self:
        """Build a successful local query result."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetQueryStatus.SUCCESS,
            coverage_status=DatasetCoverageStatus.QUERYABLE,
            source=descriptor.source,
            data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
            applied_filters=applied_filters,
            limit=limit,
            total_records_before_filter=total_records_before_filter,
            observation_recency=observation_recency,
            matched_records=records,
        )


class QueryPipeline(Protocol):
    """Minimal protocol for injecting the existing normalization pipeline."""

    def normalize(
        self,
        raw_payload: Any,
        *,
        canonical_dataset_id: str | None = None,
    ) -> NormalizationResult:
        """Return a typed normalization result for a raw payload."""


class DatasetQueryTool:
    """Local-only exact query layer over registry metadata, snapshots, and normalization."""

    def __init__(
        self,
        repository: RegistryRepository,
        snapshot_store: SnapshotStore | Path,
        *,
        normalization_pipeline: QueryPipeline | None = None,
        observation_reference_date_provider: Callable[[], date] | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore)
            else SnapshotStore(snapshot_store)
        )
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()
        self._observation_reference_date_provider = (
            observation_reference_date_provider
            or (lambda: datetime.now(UTC).date())
        )

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
            result = DatasetQueryResult.missing(
                dataset_id=normalized_dataset_id,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
            _audit_query_result(result)
            return result

        try:
            raw_payload = self._snapshot_store.read_snapshot(
                descriptor.source,
                descriptor.source_locator,
            )
        except FileNotFoundError:
            result = DatasetQueryResult.snapshot_missing(
                descriptor=descriptor,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
            _audit_query_result(result)
            return result
        except Exception as exc:
            public_message = _public_failure_message(
                stage=QueryFailureStage.SNAPSHOT_READ,
                error=exc,
            )
            _log_internal_failure(
                dataset_id=descriptor.dataset_id,
                stage=QueryFailureStage.SNAPSHOT_READ,
                error=exc,
                public_message=public_message,
            )
            result = DatasetQueryResult.failed(
                descriptor=descriptor,
                stage=QueryFailureStage.SNAPSHOT_READ,
                error_type=type(exc).__name__,
                message=public_message,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
            _audit_query_result(result)
            return result

        normalization_result = self._normalization_pipeline.normalize(
            raw_payload,
            canonical_dataset_id=descriptor.dataset_id,
        )
        if normalization_result.status is NormalizationPipelineStatus.FAILED:
            result = DatasetQueryResult.failed(
                descriptor=descriptor,
                stage=QueryFailureStage.NORMALIZATION,
                error_type=_normalization_error_type(normalization_result.failure),
                message=_normalization_error_message(normalization_result.failure),
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
            _audit_query_result(result)
            return result

        if normalization_result.status is NormalizationPipelineStatus.LIMITED:
            result = DatasetQueryResult.limited(
                descriptor=descriptor,
                normalization_result=normalization_result,
                applied_filters=normalized_filters,
                limit=normalized_limit,
            )
            _audit_query_result(result)
            return result

        observation_recency = assess_observation_recency(
            records=normalization_result.records,
            update_frequency=descriptor.update_frequency,
            reference_date=self._observation_reference_date_provider(),
        )

        if descriptor.coverage_status is not DatasetCoverageStatus.QUERYABLE:
            result = DatasetQueryResult.limited(
                descriptor=descriptor,
                applied_filters=normalized_filters,
                limit=normalized_limit,
                limitations=(
                    REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_QUERY_LIMITATION,
                ),
                observation_recency=observation_recency,
            )
            _audit_query_result(result)
            return result

        filtered_records = _apply_filters(
            _bind_canonical_dataset_id(
                descriptor=descriptor,
                records=normalization_result.records,
            ),
            normalized_filters,
        )
        limited_records = (
            filtered_records[:normalized_limit]
            if normalized_limit is not None
            else filtered_records
        )
        result = DatasetQueryResult.success(
            descriptor=descriptor,
            records=limited_records,
            total_records_before_filter=len(normalization_result.records),
            applied_filters=normalized_filters,
            limit=normalized_limit,
            observation_recency=observation_recency,
        )
        _audit_query_result(result)
        return result


def _validate_dataset_id(dataset_id: str) -> str:
    """Validate and normalize an exact registry dataset identifier."""

    return sanitize_dataset_id(dataset_id)


def _normalize_limit(limit: int | None) -> int | None:
    """Validate the optional result limit."""

    if limit is None:
        return None
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    if limit > MAX_QUERY_RESULT_LIMIT:
        raise ValueError(
            f"limit must be less than or equal to {MAX_QUERY_RESULT_LIMIT}"
        )
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
        normalized_key = sanitize_query_filter_key(key)
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError(
                "query filter values must be strings, numbers, booleans, or null"
            )
        if isinstance(value, str):
            value = sanitize_query_filter_string_value(value)
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


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    records: tuple[CanonicalRecord, ...],
) -> tuple[CanonicalRecord, ...]:
    """Rewrite source-locator-derived records to the canonical registry dataset identity."""

    return tuple(
        record.model_copy(update={"dataset_id": descriptor.dataset_id})
        for record in records
    )


def _audit_query_result(result: DatasetQueryResult) -> None:
    """Emit one audit event for a completed local query operation."""

    log_audit_event(
        "query_dataset",
        result_status=result.status.value,
        dataset_id=result.dataset_id,
        source=result.source,
        coverage_status=result.coverage_status.value,
        data_origin=result.data_origin.value if result.data_origin is not None else None,
        filter_keys=tuple(sorted(result.applied_filters)),
        limit=result.limit,
        total_records_before_filter=result.total_records_before_filter,
        matched_record_count=len(result.matched_records),
        limitation_count=len(result.limitations),
        failure_stage=(
            result.failure_stage.value
            if result.failure_stage is not None
            else None
        ),
        degradation_reason=(
            result.degradation_reason.value
            if result.degradation_reason is not None
            else None
        ),
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


def _resolve_limited_query_coverage_status(
    declared_coverage_status: DatasetCoverageStatus,
) -> DatasetCoverageStatus:
    """Resolve effective limited-state coverage for query results."""

    if declared_coverage_status is DatasetCoverageStatus.CATALOG_ONLY:
        return DatasetCoverageStatus.CATALOG_ONLY
    return DatasetCoverageStatus.LIMITED


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


def _public_failure_message(
    *,
    stage: QueryFailureStage,
    error: Exception,
) -> str:
    """Return a stable client-safe failure message for query execution."""

    if stage is QueryFailureStage.SNAPSHOT_READ:
        return QUERY_SNAPSHOT_READ_FAILURE_MESSAGE
    return str(error)


def _log_internal_failure(
    *,
    dataset_id: str,
    stage: QueryFailureStage,
    error: Exception,
    public_message: str,
) -> None:
    """Log internal exception detail when the public message is intentionally sanitized."""

    raw_message = str(error)
    if raw_message == public_message:
        return

    log_event(
        LOGGER,
        logging.ERROR,
        "query.request.failed_internal",
        dataset_id=dataset_id,
        stage=stage.value,
        error_type=type(error).__name__,
        public_message=public_message,
        internal_message=raw_message,
    )
