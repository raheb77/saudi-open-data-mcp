"""Typed dataset preview tool over local snapshots and live connector refresh."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
    CanonicalRecord,
    NormalizationPipeline,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.observability import (
    get_logger,
    get_metrics,
    log_audit_event,
    log_event,
)
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceededError,
    RateLimitPolicy,
)
from saudi_open_data_mcp.security.sanitization import sanitize_dataset_id
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessResult,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
    has_defined_freshness_window,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.result_metadata import (
    ResultDataOrigin,
    ResultDegradationReason,
)

LOGGER = get_logger(__name__)
LOCAL_PREVIEW_MISS_NOTICE = "local preview artifact was unavailable; refreshed live instead"
STALE_FALLBACK_NOTICE = "serving stale snapshot because live refresh failed"
REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_PREVIEW_LIMITATION = (
    "dataset_registry_declares_no_current_queryable_support"
)
PREVIEW_LOOKUP_FAILURE_MESSAGE = "preview dataset lookup failed"
PREVIEW_FETCH_FAILURE_MESSAGE = "preview fetch failed"
PREVIEW_SNAPSHOT_FAILURE_MESSAGE = "preview snapshot persistence failed"
PREVIEW_RATE_LIMIT_FAILURE_MESSAGE = "preview request rate limit exceeded"


class PreviewStatus(StrEnum):
    """Preview status aligned to the current normalization capability."""

    MISSING = "missing"
    RECORD_DERIVABLE = "record_derivable"
    LIMITED = "limited"
    FAILED = "failed"


class PreviewFailureStage(StrEnum):
    """Preview failure stage."""

    LOOKUP = "lookup"
    FETCH = "fetch"
    SNAPSHOT = "snapshot"
    NORMALIZATION = "normalization"


class PreviewResolutionOutcome(StrEnum):
    """How preview resolved between local snapshots and live refresh."""

    SERVE_LOCAL = "serve_local"
    REFRESH_THEN_SERVE = "refresh_then_serve"
    SERVE_STALE_WITH_NOTICE = "serve_stale_with_notice"
    FAIL_CLOSED = "fail_closed"


PreviewDataOrigin = ResultDataOrigin


class PreviewFailure(BaseModel):
    """Explicit failure details for preview execution."""

    model_config = ConfigDict(extra="forbid")

    stage: PreviewFailureStage
    error_type: str
    message: str


class PreviewResolutionPolicy(BaseModel):
    """Deterministic preview resolution policy for local/live hybrid reads.

    Current policy semantics:

    - ``serve_local`` serves a usable local snapshot directly.
    - ``refresh_then_serve`` performs a live refresh, persists it, then serves it.
    - ``serve_stale_with_notice`` serves a stale local snapshot only after an
      allowed degraded-path decision.
    - ``fail_closed`` returns a structured failure instead of silently
      inventing data.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    refresh_missing_snapshots: bool = True
    refresh_stale_snapshots: bool = True
    serve_unknown_frequency_locally: bool = True
    allow_stale_fallback_on_refresh_failure: bool = True

    def initial_outcome(
        self,
        *,
        update_frequency: UpdateFrequency,
        freshness: SnapshotFreshnessResult,
    ) -> PreviewResolutionOutcome:
        """Resolve the initial preview path from local freshness evidence."""

        if freshness.status is SnapshotFreshnessStatus.FRESH:
            return PreviewResolutionOutcome.SERVE_LOCAL

        if freshness.status is SnapshotFreshnessStatus.UNKNOWN:
            if not has_defined_freshness_window(update_frequency):
                if self.serve_unknown_frequency_locally:
                    return PreviewResolutionOutcome.SERVE_LOCAL
                return PreviewResolutionOutcome.REFRESH_THEN_SERVE
            return PreviewResolutionOutcome.SERVE_LOCAL

        if freshness.status is SnapshotFreshnessStatus.MISSING:
            if self.refresh_missing_snapshots:
                return PreviewResolutionOutcome.REFRESH_THEN_SERVE
            return PreviewResolutionOutcome.FAIL_CLOSED

        if freshness.status is SnapshotFreshnessStatus.STALE:
            if self.refresh_stale_snapshots:
                return PreviewResolutionOutcome.REFRESH_THEN_SERVE
            return PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE

        raise ValueError(f"unsupported freshness status: {freshness.status.value}")

    def refresh_failure_outcome(
        self,
        *,
        freshness: SnapshotFreshnessResult,
    ) -> PreviewResolutionOutcome:
        """Resolve the fallback after a failed refresh attempt."""

        if (
            self.allow_stale_fallback_on_refresh_failure
            and freshness.status is SnapshotFreshnessStatus.STALE
            and freshness.artifact_present
        ):
            return PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
        return PreviewResolutionOutcome.FAIL_CLOSED

    @staticmethod
    def local_artifact_unusable_outcome(
        *,
        initial_outcome: PreviewResolutionOutcome,
    ) -> PreviewResolutionOutcome:
        """Resolve the next step when a local-serving path has no usable artifact."""

        if initial_outcome in {
            PreviewResolutionOutcome.SERVE_LOCAL,
            PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE,
        }:
            return PreviewResolutionOutcome.REFRESH_THEN_SERVE
        return initial_outcome


class DatasetPreviewResult(BaseModel):
    """Typed preview result for a canonical registry dataset identifier."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    status: PreviewStatus
    coverage_status: DatasetCoverageStatus
    resolution_outcome: PreviewResolutionOutcome | None = None
    data_origin: PreviewDataOrigin | None = None
    freshness_status: SnapshotFreshnessStatus | None = None
    failure_stage: PreviewFailureStage | None = None
    degradation_reason: ResultDegradationReason | None = None
    snapshot_modified_at: datetime | None = None
    resolution_notice: str | None = None
    records: tuple[CanonicalRecord, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    failure: PreviewFailure | None = None

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        if self.status is PreviewStatus.MISSING:
            if self.coverage_status is not DatasetCoverageStatus.UNAVAILABLE:
                raise ValueError("missing preview results must expose unavailable coverage_status")
            if (
                self.failure is not None
                or self.records
                or self.limitations
                or self.resolution_outcome is not None
                or self.data_origin is not None
                or self.freshness_status is not None
                or self.failure_stage is not None
                or self.degradation_reason is not None
                or self.snapshot_modified_at is not None
                or self.resolution_notice is not None
            ):
                raise ValueError("missing preview results must not include resolution metadata")
            return self

        if self.resolution_outcome is None:
            if self.failure is None or self.failure.stage is not PreviewFailureStage.LOOKUP:
                raise ValueError("non-missing preview results must declare resolution outcome")
            if self.failure_stage is not PreviewFailureStage.LOOKUP:
                raise ValueError("lookup failures must expose matching failure_stage")
            if (
                self.data_origin is not None
                or self.freshness_status is not None
                or self.degradation_reason is not None
                or self.snapshot_modified_at is not None
                or self.resolution_notice is not None
            ):
                raise ValueError("lookup failures must not include resolution metadata")
            return self

        if self.freshness_status is None:
            raise ValueError("resolved preview results must include freshness_status")

        expected_origin = _expected_data_origin(self.resolution_outcome)
        if self.data_origin is not expected_origin:
            raise ValueError("data_origin is inconsistent with resolution_outcome")

        if self.data_origin is not None and self.snapshot_modified_at is None:
            raise ValueError(
                "preview results with a resolved snapshot or live payload must include "
                "snapshot_modified_at"
            )

        if self.data_origin is None and self.freshness_status is SnapshotFreshnessStatus.MISSING:
            if self.snapshot_modified_at is not None:
                raise ValueError("missing freshness evidence must not include snapshot_modified_at")

        if self.resolution_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE:
            if self.resolution_notice is None:
                raise ValueError(
                    "serve_stale_with_notice results must include resolution_notice"
                )
            if self.freshness_status is not SnapshotFreshnessStatus.STALE:
                raise ValueError(
                    "serve_stale_with_notice results must expose stale freshness_status"
                )
        elif (
            self.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
            and self.resolution_notice is not None
        ):
            pass
        elif self.resolution_notice is not None:
            raise ValueError(
                "resolution_notice is only valid for serve_stale_with_notice or "
                "refresh_then_serve results"
            )

        if self.status is PreviewStatus.FAILED:
            if self.coverage_status is not DatasetCoverageStatus.UNAVAILABLE:
                raise ValueError("failed preview results must expose unavailable coverage_status")
            if self.failure is None:
                raise ValueError("failure details must be present when preview status is failed")
            if self.failure_stage is not self.failure.stage:
                raise ValueError("failed preview results must expose matching failure_stage")
            if self.records or self.limitations:
                raise ValueError("failed preview results must not include records or limitations")
            if self.degradation_reason is not None:
                raise ValueError("failed preview results must not include degradation_reason")
            return self

        if self.failure is not None:
            raise ValueError("failure details must be absent for successful preview results")
        if self.failure_stage is not None and (
            self.resolution_outcome is not PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
            or self.degradation_reason
            is not ResultDegradationReason.STALE_FALLBACK_AFTER_REFRESH_FAILURE
        ):
            raise ValueError(
                "successful preview results may only expose failure_stage for stale "
                "fallback after refresh failure"
            )
        if self.status is PreviewStatus.LIMITED:
            if self.coverage_status not in {
                DatasetCoverageStatus.LIMITED,
                DatasetCoverageStatus.CATALOG_ONLY,
            }:
                raise ValueError(
                    "limited preview results must expose limited or catalog_only coverage_status"
                )
            if self.records:
                raise ValueError("limited preview results must not include records")
            if not self.limitations:
                raise ValueError("limited preview results must include explicit limitations")
            if self.degradation_reason not in {
                ResultDegradationReason.NORMALIZATION_LIMITED,
                ResultDegradationReason.STALE_FALLBACK_AFTER_REFRESH_FAILURE,
            }:
                raise ValueError(
                    "limited preview results must expose normalization_limited or "
                    "stale_fallback_after_refresh_failure degradation_reason"
                )
            return self

        if (
            self.degradation_reason is not None
            and not (
                self.resolution_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
                and self.degradation_reason
                is ResultDegradationReason.STALE_FALLBACK_AFTER_REFRESH_FAILURE
            )
        ):
            raise ValueError(
                "record-derivable preview results must not include degradation_reason "
                "unless they represent stale fallback after refresh failure"
            )
        if self.coverage_status is not DatasetCoverageStatus.QUERYABLE:
            raise ValueError(
                "record-derivable preview results must expose queryable coverage_status"
            )
        if self.limitations:
            raise ValueError("record-derivable preview results must not include limitations")
        for record in self.records:
            if record.dataset_id != self.dataset_id:
                raise ValueError("preview record dataset_id must match preview dataset_id")
        return self


class PreviewPipeline(Protocol):
    """Minimal protocol for pipeline injection without widening tool boundaries."""

    def normalize(
        self,
        raw_payload: Any,
        *,
        canonical_dataset_id: str | None = None,
    ) -> NormalizationResult:
        """Return a typed normalization result for a fetched raw payload."""


class PreviewConnector(Protocol):
    """Minimal connector protocol for preview fetching."""

    async def fetch_dataset_payload(self, dataset_id: str) -> Any:
        """Fetch a raw payload for a source-specific locator."""


class PreviewConnectorResolver(Protocol):
    """Resolve a source name to a live connector without importing connectors here."""

    def resolve(self, source: str) -> PreviewConnector:
        """Return the configured connector for a registry descriptor source."""


class DatasetPreviewTool:
    """Preview tool that resolves canonical dataset ids to local or live source data."""

    def __init__(
        self,
        repository: RegistryRepository,
        connector_resolver: PreviewConnectorResolver,
        *,
        snapshot_store: SnapshotStore | Path,
        normalization_pipeline: PreviewPipeline | None = None,
        resolution_policy: PreviewResolutionPolicy | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self._repository = repository
        self._connector_resolver = connector_resolver
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore)
            else SnapshotStore(snapshot_store)
        )
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()
        self._resolution_policy = resolution_policy or PreviewResolutionPolicy()
        self._rate_limiter = InMemoryRateLimiter(
            rate_limit_policy or RateLimitPolicy(),
            clock=time_source or monotonic,
        )

    async def preview_dataset(
        self,
        dataset_id: str,
        *,
        reference_time: datetime | None = None,
    ) -> DatasetPreviewResult:
        """Resolve, fetch when needed, and preview a canonical dataset id."""

        metrics = get_metrics()
        metrics.increment("preview.requests")

        try:
            requested_dataset_id = sanitize_dataset_id(dataset_id)
        except ValueError as exc:
            result = self._lookup_failed_result(
                dataset_id=dataset_id,
                error=exc,
            )
            self._record_result(result)
            return result

        descriptor = self._repository.get_dataset(requested_dataset_id)
        if descriptor is None:
            result = DatasetPreviewResult(
                dataset_id=requested_dataset_id,
                status=PreviewStatus.MISSING,
                coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            )
            self._record_result(result)
            return result

        result = await self._preview_known_dataset(
            descriptor=descriptor,
            reference_time=reference_time,
        )
        self._record_result(result)
        return result

    async def _preview_known_dataset(
        self,
        *,
        descriptor: DatasetDescriptor,
        reference_time: datetime | None,
    ) -> DatasetPreviewResult:
        metrics = get_metrics()
        freshness = self._evaluate_freshness(
            descriptor=descriptor,
            reference_time=reference_time,
        )
        initial_outcome = self._resolution_policy.initial_outcome(
            update_frequency=descriptor.update_frequency,
            freshness=freshness,
        )
        next_outcome = initial_outcome
        refresh_notice: str | None = None

        if initial_outcome is PreviewResolutionOutcome.SERVE_LOCAL:
            local_result = self._read_local_preview_result(
                descriptor=descriptor,
                freshness=freshness,
                resolution_outcome=PreviewResolutionOutcome.SERVE_LOCAL,
                data_origin=PreviewDataOrigin.LOCAL_SNAPSHOT,
            )
            if local_result is not None:
                return local_result
            log_event(
                LOGGER,
                logging.INFO,
                "preview.request.local_artifact_unusable",
                dataset_id=descriptor.dataset_id,
                resolution_outcome=initial_outcome.value,
                freshness_status=freshness.status.value,
            )
            refresh_notice = LOCAL_PREVIEW_MISS_NOTICE
            next_outcome = self._resolution_policy.local_artifact_unusable_outcome(
                initial_outcome=initial_outcome,
            )

        if initial_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE:
            stale_result = self._read_local_preview_result(
                descriptor=descriptor,
                freshness=freshness,
                resolution_outcome=PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE,
                data_origin=PreviewDataOrigin.STALE_SNAPSHOT,
                resolution_notice=STALE_FALLBACK_NOTICE,
            )
            if stale_result is not None:
                return stale_result
            next_outcome = self._resolution_policy.local_artifact_unusable_outcome(
                initial_outcome=initial_outcome,
            )

        if next_outcome is PreviewResolutionOutcome.FAIL_CLOSED:
            return self._closed_failure_result(
                descriptor=descriptor,
                stage=PreviewFailureStage.FETCH,
                error=RuntimeError("preview resolution policy refused live refresh"),
                freshness=freshness,
            )

        refresh_error: Exception
        refresh_failure_stage: PreviewFailureStage
        try:
            self._rate_limiter.enforce()
            connector = self._connector_resolver.resolve(descriptor.source)
            raw_payload = await connector.fetch_dataset_payload(descriptor.source_locator)
        except RateLimitExceededError as exc:
            metrics.increment("preview.rate_limited")
            refresh_error = exc
            refresh_failure_stage = PreviewFailureStage.FETCH
        except Exception as exc:
            refresh_error = exc
            refresh_failure_stage = PreviewFailureStage.FETCH
        else:
            try:
                self._snapshot_store.write_snapshot(raw_payload)
            except Exception as exc:
                refresh_error = exc
                refresh_failure_stage = PreviewFailureStage.SNAPSHOT
            else:
                refreshed_freshness = self._evaluate_freshness(
                    descriptor=descriptor,
                    reference_time=reference_time,
                )
                return self._result_from_payload(
                    descriptor=descriptor,
                    raw_payload=raw_payload,
                    freshness=refreshed_freshness,
                    resolution_outcome=PreviewResolutionOutcome.REFRESH_THEN_SERVE,
                    data_origin=PreviewDataOrigin.LIVE_REFRESH,
                    resolution_notice=refresh_notice,
                )

        fallback_outcome = self._resolution_policy.refresh_failure_outcome(
            freshness=freshness,
        )
        if fallback_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE:
            stale_result = self._read_local_preview_result(
                descriptor=descriptor,
                freshness=freshness,
                resolution_outcome=PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE,
                data_origin=PreviewDataOrigin.STALE_SNAPSHOT,
                resolution_notice=STALE_FALLBACK_NOTICE,
                failure_stage=refresh_failure_stage,
                degradation_reason=(
                    ResultDegradationReason.STALE_FALLBACK_AFTER_REFRESH_FAILURE
                ),
            )
            if stale_result is not None:
                return stale_result

        return self._closed_failure_result(
            descriptor=descriptor,
            stage=refresh_failure_stage,
            error=refresh_error,
            freshness=freshness,
        )

    def _read_local_preview_result(
        self,
        *,
        descriptor: DatasetDescriptor,
        freshness: SnapshotFreshnessResult,
        resolution_outcome: PreviewResolutionOutcome,
        data_origin: PreviewDataOrigin,
        resolution_notice: str | None = None,
        failure_stage: PreviewFailureStage | None = None,
        degradation_reason: ResultDegradationReason | None = None,
    ) -> DatasetPreviewResult | None:
        try:
            raw_payload = self._snapshot_store.read_snapshot(
                descriptor.source,
                descriptor.source_locator,
            )
        except Exception as exc:
            log_event(
                LOGGER,
                logging.WARNING,
                "preview.request.local_artifact_read_failed",
                dataset_id=descriptor.dataset_id,
                source=descriptor.source,
                source_locator=descriptor.source_locator,
                resolution_outcome=resolution_outcome.value,
                freshness_status=freshness.status.value,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            return None

        return self._result_from_payload(
            descriptor=descriptor,
            raw_payload=raw_payload,
            freshness=freshness,
            resolution_outcome=resolution_outcome,
            data_origin=data_origin,
            resolution_notice=resolution_notice,
            failure_stage=failure_stage,
            degradation_reason=degradation_reason,
        )

    def _result_from_payload(
        self,
        *,
        descriptor: DatasetDescriptor,
        raw_payload: Any,
        freshness: SnapshotFreshnessResult,
        resolution_outcome: PreviewResolutionOutcome,
        data_origin: PreviewDataOrigin,
        resolution_notice: str | None = None,
        failure_stage: PreviewFailureStage | None = None,
        degradation_reason: ResultDegradationReason | None = None,
    ) -> DatasetPreviewResult:
        normalization_result = _bind_canonical_dataset_id(
            descriptor=descriptor,
            normalization_result=self._normalization_pipeline.normalize(
                raw_payload,
                canonical_dataset_id=descriptor.dataset_id,
            ),
        )

        if normalization_result.status is NormalizationPipelineStatus.FAILED:
            return DatasetPreviewResult(
                dataset_id=normalization_result.dataset_id,
                status=PreviewStatus.FAILED,
                coverage_status=DatasetCoverageStatus.UNAVAILABLE,
                resolution_outcome=resolution_outcome,
                data_origin=data_origin,
                freshness_status=freshness.status,
                failure_stage=PreviewFailureStage.NORMALIZATION,
                snapshot_modified_at=freshness.snapshot_modified_at,
                resolution_notice=resolution_notice,
                failure=PreviewFailure(
                    stage=PreviewFailureStage.NORMALIZATION,
                    error_type=(
                        normalization_result.failure.error_type
                        if normalization_result.failure is not None
                        else "NormalizationPipelineError"
                    ),
                    message=(
                        normalization_result.failure.message
                        if normalization_result.failure is not None
                        else "Normalization pipeline failed without structured failure details"
                    ),
                ),
            )

        if (
            normalization_result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
            and descriptor.coverage_status is not DatasetCoverageStatus.QUERYABLE
        ):
            return DatasetPreviewResult(
                dataset_id=normalization_result.dataset_id,
                status=PreviewStatus.LIMITED,
                coverage_status=_resolve_preview_coverage_status(
                    declared_coverage_status=descriptor.coverage_status,
                    preview_status=PreviewStatus.LIMITED,
                ),
                resolution_outcome=resolution_outcome,
                data_origin=data_origin,
                freshness_status=freshness.status,
                failure_stage=failure_stage,
                degradation_reason=(
                    degradation_reason
                    if degradation_reason is not None
                    else ResultDegradationReason.NORMALIZATION_LIMITED
                ),
                snapshot_modified_at=freshness.snapshot_modified_at,
                resolution_notice=resolution_notice,
                limitations=(REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_PREVIEW_LIMITATION,),
            )

        return DatasetPreviewResult(
            dataset_id=normalization_result.dataset_id,
            status=PreviewStatus(normalization_result.status.value),
            coverage_status=_resolve_preview_coverage_status(
                declared_coverage_status=descriptor.coverage_status,
                preview_status=PreviewStatus(normalization_result.status.value),
            ),
            resolution_outcome=resolution_outcome,
            data_origin=data_origin,
            freshness_status=freshness.status,
            failure_stage=failure_stage,
            degradation_reason=(
                degradation_reason
                if degradation_reason is not None
                else ResultDegradationReason.NORMALIZATION_LIMITED
                if normalization_result.status is NormalizationPipelineStatus.LIMITED
                else None
            ),
            snapshot_modified_at=freshness.snapshot_modified_at,
            resolution_notice=resolution_notice,
            records=normalization_result.records,
            limitations=_collect_limitations(normalization_result),
        )

    def _evaluate_freshness(
        self,
        *,
        descriptor: DatasetDescriptor,
        reference_time: datetime | None,
    ) -> SnapshotFreshnessResult:
        freshness = evaluate_snapshot_freshness(
            source=descriptor.source,
            dataset_id=descriptor.source_locator,
            snapshot_store=self._snapshot_store,
            reference_time=reference_time,
            update_frequency=descriptor.update_frequency,
        )
        return freshness.model_copy(update={"dataset_id": descriptor.dataset_id})

    @staticmethod
    def _lookup_failed_result(
        *,
        dataset_id: str,
        error: Exception,
    ) -> DatasetPreviewResult:
        public_message = _public_failure_message(
            stage=PreviewFailureStage.LOOKUP,
            error=error,
        )
        _log_internal_failure(
            dataset_id=dataset_id,
            stage=PreviewFailureStage.LOOKUP,
            error=error,
            public_message=public_message,
        )
        return DatasetPreviewResult(
            dataset_id=dataset_id,
            status=PreviewStatus.FAILED,
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            failure_stage=PreviewFailureStage.LOOKUP,
            failure=PreviewFailure(
                stage=PreviewFailureStage.LOOKUP,
                error_type=type(error).__name__,
                message=public_message,
            ),
        )

    @staticmethod
    def _closed_failure_result(
        *,
        descriptor: DatasetDescriptor,
        stage: PreviewFailureStage,
        error: Exception,
        freshness: SnapshotFreshnessResult,
    ) -> DatasetPreviewResult:
        public_message = _public_failure_message(
            stage=stage,
            error=error,
        )
        _log_internal_failure(
            dataset_id=descriptor.dataset_id,
            stage=stage,
            error=error,
            public_message=public_message,
        )
        return DatasetPreviewResult(
            dataset_id=descriptor.dataset_id,
            status=PreviewStatus.FAILED,
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            resolution_outcome=PreviewResolutionOutcome.FAIL_CLOSED,
            freshness_status=freshness.status,
            failure_stage=stage,
            snapshot_modified_at=freshness.snapshot_modified_at,
            failure=PreviewFailure(
                stage=stage,
                error_type=type(error).__name__,
                message=public_message,
            ),
        )

    @staticmethod
    def _record_result(result: DatasetPreviewResult) -> None:
        metrics = get_metrics()
        audit_level = (
            logging.WARNING
            if result.status is PreviewStatus.FAILED
            else logging.INFO
        )

        if result.status is PreviewStatus.MISSING:
            log_event(
                LOGGER,
                logging.INFO,
                "preview.request.missing",
                dataset_id=result.dataset_id,
                coverage_status=result.coverage_status.value,
            )
            log_audit_event(
                "preview_dataset",
                result_status=result.status.value,
                level=audit_level,
                dataset_id=result.dataset_id,
                coverage_status=result.coverage_status.value,
            )
            return

        if result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT:
            metrics.increment("preview.local_snapshot")
        elif result.data_origin is PreviewDataOrigin.LIVE_REFRESH:
            metrics.increment("preview.live_refresh")
        elif result.data_origin is PreviewDataOrigin.STALE_SNAPSHOT:
            metrics.increment("preview.stale_fallback")

        log_fields = {
            "dataset_id": result.dataset_id,
            "coverage_status": result.coverage_status.value,
            "resolution_outcome": (
                result.resolution_outcome.value
                if result.resolution_outcome is not None
                else None
            ),
            "data_origin": result.data_origin.value if result.data_origin is not None else None,
            "freshness_status": (
                result.freshness_status.value if result.freshness_status is not None else None
            ),
            "failure_stage": (
                result.failure_stage.value if result.failure_stage is not None else None
            ),
            "degradation_reason": (
                result.degradation_reason.value
                if result.degradation_reason is not None
                else None
            ),
        }

        if result.status is PreviewStatus.FAILED:
            metrics.increment("preview.failures")
            assert result.failure is not None
            log_event(
                LOGGER,
                logging.WARNING,
                "preview.request.failed",
                stage=result.failure.stage.value,
                error_type=result.failure.error_type,
                message=result.failure.message,
                **log_fields,
            )
            log_audit_event(
                "preview_dataset",
                result_status=result.status.value,
                level=audit_level,
                dataset_id=result.dataset_id,
                coverage_status=result.coverage_status.value,
                resolution_outcome=(
                    result.resolution_outcome.value
                    if result.resolution_outcome is not None
                    else None
                ),
                data_origin=(
                    result.data_origin.value
                    if result.data_origin is not None
                    else None
                ),
                freshness_status=(
                    result.freshness_status.value
                    if result.freshness_status is not None
                    else None
                ),
                snapshot_modified_at=result.snapshot_modified_at,
                failure_stage=(
                    result.failure_stage.value
                    if result.failure_stage is not None
                    else None
                ),
            )
            return

        log_event(
            LOGGER,
            logging.INFO,
            "preview.request.completed",
            status=result.status.value,
            record_count=len(result.records),
            limitation_count=len(result.limitations),
            **log_fields,
        )
        log_audit_event(
            "preview_dataset",
            result_status=result.status.value,
            level=audit_level,
            dataset_id=result.dataset_id,
            coverage_status=result.coverage_status.value,
            resolution_outcome=(
                result.resolution_outcome.value
                if result.resolution_outcome is not None
                else None
            ),
            data_origin=(
                result.data_origin.value
                if result.data_origin is not None
                else None
            ),
            freshness_status=(
                result.freshness_status.value
                if result.freshness_status is not None
                else None
            ),
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
            snapshot_modified_at=result.snapshot_modified_at,
            record_count=len(result.records),
            limitation_count=len(result.limitations),
        )


def _expected_data_origin(
    resolution_outcome: PreviewResolutionOutcome,
) -> PreviewDataOrigin | None:
    if resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL:
        return PreviewDataOrigin.LOCAL_SNAPSHOT
    if resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE:
        return PreviewDataOrigin.LIVE_REFRESH
    if resolution_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE:
        return PreviewDataOrigin.STALE_SNAPSHOT
    return None


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    normalization_result: NormalizationResult,
) -> NormalizationResult:
    """Rewrite preview records to the canonical dataset identity for MCP callers."""

    canonical_records = tuple(
        record.model_copy(update={"dataset_id": descriptor.dataset_id})
        for record in normalization_result.records
    )
    return normalization_result.model_copy(
        update={
            "dataset_id": descriptor.dataset_id,
            "records": canonical_records,
        }
    )


def _collect_limitations(normalization_result: NormalizationResult) -> tuple[str, ...]:
    """Expose only explicit operator-facing limitations for limited previews."""

    if normalization_result.status is NormalizationPipelineStatus.RECORD_DERIVABLE:
        return ()

    if normalization_result.validation_result is not None:
        limitations = normalization_result.validation_result.limitations
        if limitations:
            return limitations

    if normalization_result.mapping_result is not None:
        limitations = normalization_result.mapping_result.limitations
        if limitations:
            return limitations

    if normalization_result.status is NormalizationPipelineStatus.LIMITED:
        raise ValueError("limited normalization result must include explicit limitations")

    return ()


def _resolve_preview_coverage_status(
    *,
    declared_coverage_status: DatasetCoverageStatus,
    preview_status: PreviewStatus,
) -> DatasetCoverageStatus:
    """Resolve effective preview coverage from governed support plus runtime outcome."""

    if preview_status in {PreviewStatus.MISSING, PreviewStatus.FAILED}:
        return DatasetCoverageStatus.UNAVAILABLE
    if preview_status is PreviewStatus.RECORD_DERIVABLE:
        return (
            DatasetCoverageStatus.QUERYABLE
            if declared_coverage_status is DatasetCoverageStatus.QUERYABLE
            else declared_coverage_status
        )
    if preview_status is PreviewStatus.LIMITED:
        return (
            DatasetCoverageStatus.CATALOG_ONLY
            if declared_coverage_status is DatasetCoverageStatus.CATALOG_ONLY
            else DatasetCoverageStatus.LIMITED
        )
    raise ValueError(
        f"unsupported preview status for coverage resolution: {preview_status.value}"
    )


def _public_failure_message(
    *,
    stage: PreviewFailureStage,
    error: Exception,
) -> str:
    """Return a stable client-safe failure message for preview execution."""

    connector_message = getattr(error, "message", None)
    connector_source = getattr(error, "source_name", None)
    if isinstance(connector_message, str) and isinstance(connector_source, str):
        return connector_message

    if stage is PreviewFailureStage.LOOKUP:
        if isinstance(error, ValueError):
            return str(error)
        return PREVIEW_LOOKUP_FAILURE_MESSAGE

    if stage is PreviewFailureStage.FETCH:
        if isinstance(error, RateLimitExceededError):
            return PREVIEW_RATE_LIMIT_FAILURE_MESSAGE
        if _is_safe_runtime_failure_message(
            error,
            allowed_messages={"preview resolution policy refused live refresh"},
        ):
            return str(error)
        return PREVIEW_FETCH_FAILURE_MESSAGE

    if stage is PreviewFailureStage.SNAPSHOT:
        return PREVIEW_SNAPSHOT_FAILURE_MESSAGE

    return str(error)


def _log_internal_failure(
    *,
    dataset_id: str,
    stage: PreviewFailureStage,
    error: Exception,
    public_message: str,
) -> None:
    """Log internal exception detail when preview sanitizes the public result message."""

    if _is_connector_error(error):
        return

    raw_message = str(error)
    if raw_message == public_message:
        return

    log_event(
        LOGGER,
        logging.ERROR,
        "preview.request.failed_internal",
        dataset_id=dataset_id,
        stage=stage.value,
        error_type=type(error).__name__,
        public_message=public_message,
        internal_message=raw_message,
    )


def _is_connector_error(error: Exception) -> bool:
    """Return whether the error exposes the connector error contract."""

    connector_message = getattr(error, "message", None)
    connector_source = getattr(error, "source_name", None)
    return isinstance(connector_message, str) and isinstance(connector_source, str)


def _is_safe_runtime_failure_message(
    error: Exception,
    *,
    allowed_messages: set[str],
) -> bool:
    """Return whether a runtime error message is intentionally safe to expose."""

    return isinstance(error, RuntimeError) and str(error) in allowed_messages
