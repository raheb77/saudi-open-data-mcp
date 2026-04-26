"""Curated live upstream canary checks for approved source surfaces."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from saudi_open_data_mcp.config import RuntimeConfig, prepare_runtime_storage
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import ConnectorError
from saudi_open_data_mcp.connectors.resolver import build_default_connector_resolver
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)
from saudi_open_data_mcp.observability import get_logger, log_event
from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    HealthMetadata,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository

LOGGER = get_logger(__name__)
DATA_GOV_SA_NO_QUERYABLE_DATASET_REASON = (
    "no queryable data.gov.sa dataset registered"
)


class UpstreamCanaryStatus(StrEnum):
    """Top-level canary pass/fail status."""

    PASSED = "passed"
    FAILED = "failed"


class UpstreamCanaryFailureStage(StrEnum):
    """Stage at which a canary failed."""

    LOOKUP = "lookup"
    FETCH = "fetch"
    NORMALIZATION = "normalization"


@dataclass(frozen=True)
class _UpstreamCanaryDefinition:
    dataset_id: str
    expected_normalization_status: NormalizationPipelineStatus
    minimum_record_count: int


_UPSTREAM_CANARY_DEFINITIONS: tuple[_UpstreamCanaryDefinition, ...] = (
    _UpstreamCanaryDefinition(
        dataset_id="sama-exchange-rates-current",
        expected_normalization_status=NormalizationPipelineStatus.RECORD_DERIVABLE,
        minimum_record_count=1,
    ),
    _UpstreamCanaryDefinition(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        expected_normalization_status=NormalizationPipelineStatus.RECORD_DERIVABLE,
        minimum_record_count=1,
    ),
    _UpstreamCanaryDefinition(
        dataset_id="mof-budget-balance-quarterly",
        expected_normalization_status=NormalizationPipelineStatus.RECORD_DERIVABLE,
        minimum_record_count=1,
    ),
)
_INITIAL_DESCRIPTOR_BY_ID = {
    descriptor.dataset_id: descriptor for descriptor in INITIAL_DATASET_DESCRIPTORS
}


class UpstreamCanaryCheckResult(BaseModel):
    """Result for one curated upstream canary dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    source: str | None = None
    source_locator: str | None = None
    status: UpstreamCanaryStatus
    expected_normalization_status: str
    minimum_record_count: int
    normalization_status: str | None = None
    record_count: int | None = None
    response_status_code: int | None = None
    response_content_type: str | None = None
    response_url: str | None = None
    failure_stage: UpstreamCanaryFailureStage | None = None
    error_type: str | None = None
    message: str | None = None
    degradation_reason: str | None = None


class UpstreamCanarySkippedSource(BaseModel):
    """Source family skipped by the curated canary with an explicit reason."""

    model_config = ConfigDict(extra="forbid")

    source: str
    reason: str


class UpstreamCanaryHealthStatusChange(BaseModel):
    """Dataset health_status transition persisted from one canary check."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    previous_health_status: DatasetHealthStatus | None
    new_health_status: DatasetHealthStatus
    degradation_reason: str | None = None


class UpstreamCanarySummary(BaseModel):
    """Auditable summary for the curated upstream canary run."""

    model_config = ConfigDict(extra="forbid")

    status: UpstreamCanaryStatus
    checked_at: datetime
    checked_dataset_count: int
    passed_dataset_count: int
    failed_dataset_count: int
    dataset_ids_checked: tuple[str, ...]
    detects: tuple[str, ...] = Field(default_factory=tuple)
    does_not_detect: tuple[str, ...] = Field(default_factory=tuple)
    skipped_sources: tuple[UpstreamCanarySkippedSource, ...] = Field(default_factory=tuple)
    health_status_changes: tuple[UpstreamCanaryHealthStatusChange, ...] = Field(
        default_factory=tuple
    )
    checks: tuple[UpstreamCanaryCheckResult, ...] = Field(default_factory=tuple)


async def run_upstream_canary(
    runtime_config: RuntimeConfig,
    *,
    dataset_ids: tuple[str, ...] | None = None,
) -> UpstreamCanarySummary:
    """Run live fetch-plus-normalization checks for the curated upstream subset."""

    selected_definitions = _select_canary_definitions(dataset_ids)
    skipped_sources = _skipped_sources_for_default_run() if dataset_ids is None else ()
    connector_resolver = build_default_connector_resolver(
        source_config=runtime_config.source,
    )
    normalization_pipeline = NormalizationPipeline()
    prepare_runtime_storage(runtime_config)
    repository = RegistryRepository(runtime_config.registry_path)
    bootstrap_registry(repository)
    checks: list[UpstreamCanaryCheckResult] = []
    health_status_changes: list[UpstreamCanaryHealthStatusChange] = []

    for definition in selected_definitions:
        check = await _run_one_canary_check(
            definition=definition,
            connector_resolver=connector_resolver,
            normalization_pipeline=normalization_pipeline,
        )
        health_status_change = _persist_canary_health_outcome(repository, check)
        if health_status_change is not None:
            health_status_changes.append(health_status_change)
        checks.append(check)

    failed_dataset_count = sum(
        1 for check in checks if check.status is UpstreamCanaryStatus.FAILED
    )
    return UpstreamCanarySummary(
        status=(
            UpstreamCanaryStatus.FAILED
            if failed_dataset_count
            else UpstreamCanaryStatus.PASSED
        ),
        checked_at=datetime.now(tz=UTC),
        checked_dataset_count=len(checks),
        passed_dataset_count=len(checks) - failed_dataset_count,
        failed_dataset_count=failed_dataset_count,
        dataset_ids_checked=tuple(definition.dataset_id for definition in selected_definitions),
        detects=(
            "approved upstream route drift for the curated canary dataset_ids",
            "live HTTP/connectivity failures returned by the configured approved source hosts",
            "invalid upstream response shapes rejected by the connectors",
            (
                "normalization regressions that prevent the curated canary "
                "datasets from producing record-derivable results"
            ),
        ),
        does_not_detect=(
            "full catalog coverage outside the curated canary dataset_ids",
            "freshness SLA violations for every dataset",
            "all possible parser regressions that do not affect the curated canary datasets",
        ),
        skipped_sources=skipped_sources,
        health_status_changes=tuple(health_status_changes),
        checks=tuple(checks),
    )


def _select_canary_definitions(
    dataset_ids: tuple[str, ...] | None,
) -> tuple[_UpstreamCanaryDefinition, ...]:
    if dataset_ids is None:
        return _UPSTREAM_CANARY_DEFINITIONS

    definitions_by_id = {
        definition.dataset_id: definition for definition in _UPSTREAM_CANARY_DEFINITIONS
    }
    selected: list[_UpstreamCanaryDefinition] = []
    for dataset_id in dataset_ids:
        definition = definitions_by_id.get(dataset_id)
        if definition is None:
            available = ", ".join(sorted(definitions_by_id))
            raise ValueError(
                "upstream canary only supports the curated dataset_ids: "
                f"{available}"
            )
        selected.append(definition)
    return tuple(selected)


def _skipped_sources_for_default_run() -> tuple[UpstreamCanarySkippedSource, ...]:
    if any(
        descriptor.source == "data-gov-sa"
        and descriptor.coverage_status is DatasetCoverageStatus.QUERYABLE
        for descriptor in INITIAL_DATASET_DESCRIPTORS
    ):
        return ()

    log_event(
        LOGGER,
        logging.INFO,
        "canary: no queryable data.gov.sa dataset registered, skipping",
        source="data-gov-sa",
    )
    return (
        UpstreamCanarySkippedSource(
            source="data-gov-sa",
            reason=DATA_GOV_SA_NO_QUERYABLE_DATASET_REASON,
        ),
    )


async def _run_one_canary_check(
    *,
    definition: _UpstreamCanaryDefinition,
    connector_resolver,
    normalization_pipeline: NormalizationPipeline,
) -> UpstreamCanaryCheckResult:
    descriptor = _INITIAL_DESCRIPTOR_BY_ID.get(definition.dataset_id)
    if descriptor is None:
        return UpstreamCanaryCheckResult(
            dataset_id=definition.dataset_id,
            status=UpstreamCanaryStatus.FAILED,
            expected_normalization_status=definition.expected_normalization_status.value,
            minimum_record_count=definition.minimum_record_count,
            failure_stage=UpstreamCanaryFailureStage.LOOKUP,
            error_type="UnknownDatasetDescriptor",
            message="dataset_id is not present in the current seeded descriptor set",
        )

    try:
        connector = connector_resolver.resolve(descriptor.source)
    except Exception as exc:
        return _failed_canary_result(
            descriptor=descriptor,
            definition=definition,
            failure_stage=UpstreamCanaryFailureStage.LOOKUP,
            error_type=type(exc).__name__,
            message=str(exc),
        )

    try:
        raw_payload = await connector.fetch_dataset_payload(descriptor.source_locator)
    except ConnectorError as exc:
        return _failed_canary_result(
            descriptor=descriptor,
            definition=definition,
            failure_stage=UpstreamCanaryFailureStage.FETCH,
            error_type=type(exc).__name__,
            message=str(exc),
        )
    except Exception as exc:
        return _failed_canary_result(
            descriptor=descriptor,
            definition=definition,
            failure_stage=UpstreamCanaryFailureStage.FETCH,
            error_type=type(exc).__name__,
            message=str(exc),
        )

    normalization_result = normalization_pipeline.normalize(
        raw_payload,
        canonical_dataset_id=descriptor.dataset_id,
    )
    response_metadata = _response_metadata(raw_payload)
    if normalization_result.status is not definition.expected_normalization_status:
        return _failed_canary_result(
            descriptor=descriptor,
            definition=definition,
            failure_stage=UpstreamCanaryFailureStage.NORMALIZATION,
            error_type="UnexpectedNormalizationStatus",
            message=(
                "expected normalization_status "
                f"{definition.expected_normalization_status.value} but got "
                f"{normalization_result.status.value}"
            ),
            raw_payload=raw_payload,
            normalization_status=normalization_result.status.value,
            record_count=len(normalization_result.records),
        )

    record_count = len(normalization_result.records)
    if record_count < definition.minimum_record_count:
        return _failed_canary_result(
            descriptor=descriptor,
            definition=definition,
            failure_stage=UpstreamCanaryFailureStage.NORMALIZATION,
            error_type="InsufficientRecordCount",
            message=(
                f"expected at least {definition.minimum_record_count} normalized records "
                f"but got {record_count}"
            ),
            raw_payload=raw_payload,
            normalization_status=normalization_result.status.value,
            record_count=record_count,
        )

    return UpstreamCanaryCheckResult(
        dataset_id=descriptor.dataset_id,
        source=descriptor.source,
        source_locator=descriptor.source_locator,
        status=UpstreamCanaryStatus.PASSED,
        expected_normalization_status=definition.expected_normalization_status.value,
        minimum_record_count=definition.minimum_record_count,
        normalization_status=normalization_result.status.value,
        record_count=record_count,
        response_status_code=response_metadata["status_code"],
        response_content_type=response_metadata["content_type"],
        response_url=response_metadata["url"],
    )


def _failed_canary_result(
    *,
    descriptor: DatasetDescriptor,
    definition: _UpstreamCanaryDefinition,
    failure_stage: UpstreamCanaryFailureStage,
    error_type: str,
    message: str,
    raw_payload: RawPayload | None = None,
    normalization_status: str | None = None,
    record_count: int | None = None,
) -> UpstreamCanaryCheckResult:
    response_metadata = _response_metadata(raw_payload) if raw_payload is not None else None
    degradation_reason = _canary_degradation_reason(
        failure_stage=failure_stage,
        error_type=error_type,
        message=message,
    )
    return UpstreamCanaryCheckResult(
        dataset_id=descriptor.dataset_id,
        source=descriptor.source,
        source_locator=descriptor.source_locator,
        status=UpstreamCanaryStatus.FAILED,
        expected_normalization_status=definition.expected_normalization_status.value,
        minimum_record_count=definition.minimum_record_count,
        normalization_status=normalization_status,
        record_count=record_count,
        response_status_code=(
            response_metadata["status_code"] if response_metadata is not None else None
        ),
        response_content_type=(
            response_metadata["content_type"] if response_metadata is not None else None
        ),
        response_url=response_metadata["url"] if response_metadata is not None else None,
        failure_stage=failure_stage,
        error_type=error_type,
        message=message,
        degradation_reason=degradation_reason,
    )


def _persist_canary_health_outcome(
    repository: RegistryRepository,
    check: UpstreamCanaryCheckResult,
) -> UpstreamCanaryHealthStatusChange | None:
    previous_health = repository.get_health(check.dataset_id)
    previous_health_status = (
        previous_health.health_status if previous_health is not None else None
    )
    health_status = (
        DatasetHealthStatus.HEALTHY
        if check.status is UpstreamCanaryStatus.PASSED
        else DatasetHealthStatus.DEGRADED
    )
    repository.upsert_health(
        HealthMetadata(
            dataset_id=check.dataset_id,
            health_status=health_status,
        )
    )
    if previous_health_status is health_status:
        return None
    return UpstreamCanaryHealthStatusChange(
        dataset_id=check.dataset_id,
        previous_health_status=previous_health_status,
        new_health_status=health_status,
        degradation_reason=(
            check.degradation_reason
            if health_status is DatasetHealthStatus.DEGRADED
            else None
        ),
    )


def _canary_degradation_reason(
    *,
    failure_stage: UpstreamCanaryFailureStage,
    error_type: str,
    message: str,
) -> str:
    return f"{failure_stage.value}: {error_type}: {message}"


def upstream_canary_exit_code(summary: UpstreamCanarySummary) -> int:
    """Return the CLI exit code for a completed canary summary."""

    return 0 if summary.status is UpstreamCanaryStatus.PASSED else 2


def _response_metadata(raw_payload: RawPayload) -> dict[str, Any]:
    return {
        "url": str(raw_payload.content.get("url")),
        "status_code": int(raw_payload.content.get("status_code", 0)),
        "content_type": str(raw_payload.content.get("content_type", "")),
    }
