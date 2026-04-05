"""Typed Wave 1 hot-set materialization over registry, connectors, and snapshots."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
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
from saudi_open_data_mcp.registry.bootstrap import (
    WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
)
from saudi_open_data_mcp.registry.models import DatasetDescriptor, NonEmptyText
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessResult,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.result_metadata import (
    ResultDataOrigin,
    ResultDegradationReason,
)

LOGGER = get_logger(__name__)


class HotSetTier(StrEnum):
    """Wave 1 hot-set selection tier."""

    TIER_A = "tier_a"
    TIER_B_OPTIONAL = "tier_b_optional"


class HotSetMaterializationStatus(StrEnum):
    """Per-dataset hot-set materialization status."""

    MATERIALIZED = "materialized"
    FAILED = "failed"


class HotSetMaterializationFailureStage(StrEnum):
    """Explicit stage for a materialization failure."""

    LOOKUP = "lookup"
    FETCH = "fetch"
    SNAPSHOT = "snapshot"


class HotSetMaterializationFailure(BaseModel):
    """Structured failure details for hot-set materialization."""

    model_config = ConfigDict(extra="forbid")

    stage: HotSetMaterializationFailureStage
    error_type: str
    message: str


class HotSetDatasetMaterializationResult(BaseModel):
    """Per-dataset Wave 1 materialization result."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    tier: HotSetTier
    status: HotSetMaterializationStatus
    source: NonEmptyText | None = None
    data_origin: ResultDataOrigin | None = None
    local_snapshot_exists: bool
    freshness_status: SnapshotFreshnessStatus | None = None
    freshness: SnapshotFreshnessResult | None = None
    normalization_status: NormalizationPipelineStatus | None = None
    failure_stage: HotSetMaterializationFailureStage | None = None
    degradation_reason: ResultDegradationReason | None = None
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    failure: HotSetMaterializationFailure | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status is HotSetMaterializationStatus.MATERIALIZED:
            if self.source is None or self.freshness is None:
                raise ValueError(
                    "materialized hot-set results must include source and freshness"
                )
            if self.data_origin is not ResultDataOrigin.LIVE_REFRESH:
                raise ValueError(
                    "materialized hot-set results must expose live_refresh data_origin"
                )
            if not self.local_snapshot_exists or not self.freshness.artifact_present:
                raise ValueError(
                    "materialized hot-set results must include positive snapshot evidence"
                )
            if self.freshness_status is not self.freshness.status:
                raise ValueError(
                    "materialized hot-set results must include matching freshness_status"
                )
            if self.normalization_status is None:
                raise ValueError(
                    "materialized hot-set results must include normalization status"
                )
            if self.failure is not None or self.failure_stage is not None:
                raise ValueError("materialized hot-set results must not include failure")
            if self.freshness.dataset_id != self.dataset_id:
                raise ValueError("freshness.dataset_id must match dataset_id")
            if self.freshness.source != self.source:
                raise ValueError("freshness.source must match source")
            if self.normalization_status is NormalizationPipelineStatus.LIMITED:
                if self.degradation_reason is not ResultDegradationReason.NORMALIZATION_LIMITED:
                    raise ValueError(
                        "limited materialized results must expose normalization_limited "
                        "degradation_reason"
                    )
            elif self.degradation_reason is not None:
                raise ValueError(
                    "record-derivable materialized results must not include "
                    "degradation_reason"
                )
            return self

        if self.failure is None:
            raise ValueError("failed hot-set results must include failure details")
        if self.failure_stage is not self.failure.stage:
            raise ValueError("failed hot-set results must expose matching failure_stage")
        if self.normalization_status is not None or self.limitations:
            raise ValueError(
                "failed hot-set results must not include normalization status or limitations"
            )
        if self.degradation_reason is not None:
            raise ValueError("failed hot-set results must not include degradation_reason")
        if self.freshness is None:
            if self.local_snapshot_exists:
                raise ValueError(
                    "failed hot-set results without freshness must not claim a snapshot"
                )
            if self.data_origin is not None or self.freshness_status is not None:
                raise ValueError(
                    "failed hot-set results without freshness must not include "
                    "data_origin or freshness_status"
                )
            return self

        if self.source is None:
            raise ValueError("failed hot-set results with freshness must include source")
        if self.freshness.dataset_id != self.dataset_id:
            raise ValueError("freshness.dataset_id must match dataset_id")
        if self.freshness.source != self.source:
            raise ValueError("freshness.source must match source")
        if self.freshness_status is not self.freshness.status:
            raise ValueError("failed hot-set results must expose matching freshness_status")
        if self.freshness.artifact_present != self.local_snapshot_exists:
            raise ValueError(
                "failed hot-set results must keep freshness evidence consistent"
            )
        if self.data_origin is not None:
            raise ValueError("failed hot-set results must not include data_origin")
        return self

    @classmethod
    def materialized(
        cls,
        *,
        descriptor: DatasetDescriptor,
        tier: HotSetTier,
        freshness: SnapshotFreshnessResult,
        normalization_result: NormalizationResult,
    ) -> Self:
        return cls(
            dataset_id=descriptor.dataset_id,
            tier=tier,
            status=HotSetMaterializationStatus.MATERIALIZED,
            source=descriptor.source,
            data_origin=ResultDataOrigin.LIVE_REFRESH,
            local_snapshot_exists=True,
            freshness_status=freshness.status,
            freshness=freshness,
            normalization_status=normalization_result.status,
            degradation_reason=(
                ResultDegradationReason.NORMALIZATION_LIMITED
                if normalization_result.status is NormalizationPipelineStatus.LIMITED
                else None
            ),
            limitations=_collect_limitations(normalization_result),
        )

    @classmethod
    def failed(
        cls,
        *,
        dataset_id: str,
        tier: HotSetTier,
        stage: HotSetMaterializationFailureStage,
        error: Exception,
        descriptor: DatasetDescriptor | None = None,
        freshness: SnapshotFreshnessResult | None = None,
    ) -> Self:
        return cls(
            dataset_id=dataset_id,
            tier=tier,
            status=HotSetMaterializationStatus.FAILED,
            source=descriptor.source if descriptor is not None else None,
            local_snapshot_exists=(
                freshness.artifact_present if freshness is not None else False
            ),
            freshness_status=freshness.status if freshness is not None else None,
            freshness=freshness,
            failure_stage=stage,
            failure=HotSetMaterializationFailure(
                stage=stage,
                error_type=type(error).__name__,
                message=_public_failure_message(error),
            ),
        )


class HotSetMaterializationResult(BaseModel):
    """Top-level typed result for a Wave 1 hot-set materialization run."""

    model_config = ConfigDict(extra="forbid")

    include_optional: bool
    requested_dataset_count: int = Field(ge=0)
    materialized_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: tuple[HotSetDatasetMaterializationResult, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_counts(self) -> Self:
        if len(self.results) != self.requested_dataset_count:
            raise ValueError("requested_dataset_count must match results length")
        if self.materialized_count + self.failed_count != self.requested_dataset_count:
            raise ValueError("materialized_count and failed_count must match requested count")
        return self


class MaterializationConnector(Protocol):
    """Minimal connector protocol for hot-set fetching."""

    async def fetch_dataset_payload(self, dataset_id: str) -> Any:
        """Fetch a raw payload for a source-specific locator."""


class MaterializationConnectorResolver(Protocol):
    """Resolve a source name to a live connector without importing connectors here."""

    def resolve(self, source: str) -> MaterializationConnector:
        """Return the configured connector for a registry descriptor source."""


class MaterializationPipeline(Protocol):
    """Minimal protocol for injecting the existing normalization pipeline."""

    def normalize(
        self,
        raw_payload: Any,
        *,
        canonical_dataset_id: str | None = None,
    ) -> NormalizationResult:
        """Return a typed normalization result for a fetched raw payload."""


class HotSetMaterializationRunner(Protocol):
    """Minimal protocol for reusing hot-set materialization outside the MCP tool."""

    async def materialize_hot_set(
        self,
        *,
        include_optional: bool = False,
        reference_time: datetime | None = None,
    ) -> HotSetMaterializationResult:
        """Run one hot-set materialization cycle."""


@dataclass(frozen=True)
class _LocatorMaterializationSuccess:
    raw_payload: Any


@dataclass(frozen=True)
class _LocatorMaterializationFailure:
    stage: HotSetMaterializationFailureStage
    error: Exception


class HotSetMaterializationTool:
    """Materialize the fixed Wave 1 safe hot-set into local raw snapshots."""

    def __init__(
        self,
        repository: RegistryRepository,
        connector_resolver: MaterializationConnectorResolver,
        snapshot_store: SnapshotStore | Path,
        *,
        normalization_pipeline: MaterializationPipeline | None = None,
    ) -> None:
        self._repository = repository
        self._connector_resolver = connector_resolver
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore)
            else SnapshotStore(snapshot_store)
        )
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()
        self._run_lock = asyncio.Lock()

    async def materialize_hot_set(
        self,
        *,
        include_optional: bool = False,
        reference_time: datetime | None = None,
    ) -> HotSetMaterializationResult:
        """Fetch and persist the fixed Wave 1 hot-set selection."""

        async with self._run_lock:
            metrics = get_metrics()
            metrics.increment("materialize.requests")
            selected_dataset_ids = _selected_dataset_ids(include_optional)
            locator_results: dict[
                tuple[str, str],
                _LocatorMaterializationSuccess | _LocatorMaterializationFailure,
            ] = {}
            results: list[HotSetDatasetMaterializationResult] = []

            for dataset_id in selected_dataset_ids:
                tier = _tier_for_dataset_id(dataset_id)
                descriptor = self._repository.get_dataset(dataset_id)
                if descriptor is None:
                    results.append(
                        HotSetDatasetMaterializationResult.failed(
                            dataset_id=dataset_id,
                            tier=tier,
                            stage=HotSetMaterializationFailureStage.LOOKUP,
                            error=LookupError(
                                f"Dataset '{dataset_id}' is not in the registry"
                            ),
                        )
                    )
                    continue

                locator_key = (descriptor.source, descriptor.source_locator)
                cached_result = locator_results.get(locator_key)
                if cached_result is None:
                    cached_result = await self._materialize_source_locator(descriptor)
                    locator_results[locator_key] = cached_result

                freshness = _bind_canonical_dataset_id(
                    descriptor=descriptor,
                    freshness=evaluate_snapshot_freshness(
                        source=descriptor.source,
                        dataset_id=descriptor.source_locator,
                        snapshot_store=self._snapshot_store,
                        reference_time=reference_time,
                        update_frequency=descriptor.update_frequency,
                    ),
                )
                if isinstance(cached_result, _LocatorMaterializationFailure):
                    results.append(
                        HotSetDatasetMaterializationResult.failed(
                            dataset_id=descriptor.dataset_id,
                            tier=tier,
                            stage=cached_result.stage,
                            error=cached_result.error,
                            descriptor=descriptor,
                            freshness=freshness,
                        )
                    )
                    continue

                results.append(
                    HotSetDatasetMaterializationResult.materialized(
                        descriptor=descriptor,
                        tier=tier,
                        freshness=freshness,
                        normalization_result=_bind_canonical_dataset_id_to_normalization(
                            descriptor=descriptor,
                            normalization_result=self._normalization_pipeline.normalize(
                                cached_result.raw_payload,
                                canonical_dataset_id=descriptor.dataset_id,
                            ),
                        ),
                    )
                )

            materialized_count = sum(
                result.status is HotSetMaterializationStatus.MATERIALIZED
                for result in results
            )
            failed_count = len(results) - materialized_count
            if materialized_count:
                metrics.increment("materialize.successes", materialized_count)
            if failed_count:
                metrics.increment("materialize.failures", failed_count)
            result = HotSetMaterializationResult(
                include_optional=include_optional,
                requested_dataset_count=len(selected_dataset_ids),
                materialized_count=materialized_count,
                failed_count=failed_count,
                results=tuple(results),
            )
            log_audit_event(
                "materialize_hot_set",
                result_status=(
                    "success"
                    if failed_count == 0
                    else "failed"
                    if materialized_count == 0
                    else "partial_success"
                ),
                level=logging.WARNING if failed_count else logging.INFO,
                include_optional=include_optional,
                requested_dataset_count=result.requested_dataset_count,
                materialized_count=result.materialized_count,
                failed_count=result.failed_count,
            )
            return result

    async def _materialize_source_locator(
        self,
        descriptor: DatasetDescriptor,
    ) -> _LocatorMaterializationSuccess | _LocatorMaterializationFailure:
        try:
            connector = self._connector_resolver.resolve(descriptor.source)
            raw_payload = await connector.fetch_dataset_payload(descriptor.source_locator)
        except Exception as exc:
            return _LocatorMaterializationFailure(
                stage=HotSetMaterializationFailureStage.FETCH,
                error=exc,
            )

        try:
            self._snapshot_store.write_snapshot(raw_payload)
        except Exception as exc:
            return _LocatorMaterializationFailure(
                stage=HotSetMaterializationFailureStage.SNAPSHOT,
                error=exc,
            )

        return _LocatorMaterializationSuccess(
            raw_payload=raw_payload
        )


class TierABackgroundRefreshService:
    """Periodic internal Tier A refresh loop over the existing materialization path."""

    def __init__(
        self,
        materialization_runner: HotSetMaterializationRunner,
        *,
        interval_seconds: int,
    ) -> None:
        self._materialization_runner = materialization_runner
        self._interval_seconds = interval_seconds

    async def run_once(self) -> HotSetMaterializationResult:
        """Run one Tier A-only refresh cycle."""

        get_metrics().increment("tier_a_refresh.runs")
        log_event(
            LOGGER,
            logging.INFO,
            "tier_a_refresh.run.started",
            interval_seconds=self._interval_seconds,
        )
        result = await self._materialization_runner.materialize_hot_set(
            include_optional=False,
        )
        log_event(
            LOGGER,
            logging.WARNING if result.failed_count else logging.INFO,
            "tier_a_refresh.run.completed",
            interval_seconds=self._interval_seconds,
            requested_dataset_count=result.requested_dataset_count,
            materialized_count=result.materialized_count,
            failed_count=result.failed_count,
        )
        return result

    async def run_forever(self) -> None:
        """Run Tier A refresh cycles until cancelled by the hosting runtime."""

        while True:
            try:
                await self.run_once()
            except Exception as exc:
                get_metrics().increment("tier_a_refresh.run_failures")
                log_event(
                    LOGGER,
                    logging.ERROR,
                    "tier_a_refresh.run.failed",
                    interval_seconds=self._interval_seconds,
                    error_type=type(exc).__name__,
                    message=_public_failure_message(exc),
                )
            await asyncio.sleep(self._interval_seconds)


def _selected_dataset_ids(include_optional: bool) -> tuple[str, ...]:
    dataset_ids = list(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    if include_optional:
        dataset_ids.extend(WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS)
    return tuple(dataset_ids)


def _tier_for_dataset_id(dataset_id: str) -> HotSetTier:
    if dataset_id in WAVE_1_HOT_SET_TIER_A_DATASET_IDS:
        return HotSetTier.TIER_A
    return HotSetTier.TIER_B_OPTIONAL


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    freshness: SnapshotFreshnessResult,
) -> SnapshotFreshnessResult:
    return freshness.model_copy(update={"dataset_id": descriptor.dataset_id})


def _bind_canonical_dataset_id_to_normalization(
    *,
    descriptor: DatasetDescriptor,
    normalization_result: NormalizationResult,
) -> NormalizationResult:
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

    return ()


def _public_failure_message(error: Exception) -> str:
    connector_message = getattr(error, "message", None)
    connector_source = getattr(error, "source_name", None)
    if isinstance(connector_message, str) and isinstance(connector_source, str):
        return connector_message

    return str(error)
