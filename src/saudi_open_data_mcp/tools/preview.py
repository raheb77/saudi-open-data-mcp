"""Typed dataset preview tool over the connector and normalization path."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
    CanonicalRecord,
    NormalizationPipeline,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import DatasetDescriptor
from saudi_open_data_mcp.registry.repository import RegistryRepository


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
    NORMALIZATION = "normalization"


class PreviewFailure(BaseModel):
    """Explicit failure details for preview execution."""

    model_config = ConfigDict(extra="forbid")

    stage: PreviewFailureStage
    error_type: str
    message: str


class DatasetPreviewResult(BaseModel):
    """Typed preview result for a canonical registry dataset identifier."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    status: PreviewStatus
    records: tuple[CanonicalRecord, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    failure: PreviewFailure | None = None

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        if self.status is PreviewStatus.MISSING:
            if self.failure is not None or self.records or self.limitations:
                raise ValueError(
                    "missing preview results must not include records, limitations, or failure"
                )
            return self

        if self.status is PreviewStatus.FAILED:
            if self.failure is None:
                raise ValueError("failure details must be present when preview status is failed")
            if self.records or self.limitations:
                raise ValueError("failed preview results must not include records or limitations")
            return self

        if self.failure is not None:
            raise ValueError("failure details must be absent for successful preview results")
        if self.status is PreviewStatus.LIMITED:
            if self.records:
                raise ValueError("limited preview results must not include records")
            if not self.limitations:
                raise ValueError("limited preview results must include explicit limitations")
            return self

        if self.limitations:
            raise ValueError("record-derivable preview results must not include limitations")
        for record in self.records:
            if record.dataset_id != self.dataset_id:
                raise ValueError("preview record dataset_id must match preview dataset_id")
        return self


class PreviewPipeline(Protocol):
    """Minimal protocol for pipeline injection without widening tool boundaries."""

    def normalize(self, raw_payload: Any) -> NormalizationResult:
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
    """Preview tool that resolves canonical dataset ids to source locators."""

    def __init__(
        self,
        repository: RegistryRepository,
        connector_resolver: PreviewConnectorResolver,
        *,
        normalization_pipeline: PreviewPipeline | None = None,
    ) -> None:
        self._repository = repository
        self._connector_resolver = connector_resolver
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()

    async def preview_dataset(self, dataset_id: str) -> DatasetPreviewResult:
        """Fetch a raw payload for a canonical dataset id and return a preview."""

        requested_dataset_id = dataset_id.strip()
        if not requested_dataset_id:
            return self._failed_result(
                dataset_id=dataset_id,
                stage=PreviewFailureStage.LOOKUP,
                error=ValueError("dataset_id must not be empty"),
            )

        descriptor = self._repository.get_dataset(requested_dataset_id)
        if descriptor is None:
            return DatasetPreviewResult(
                dataset_id=requested_dataset_id,
                status=PreviewStatus.MISSING,
            )

        try:
            connector = self._connector_resolver.resolve(descriptor.source)
            raw_payload = await connector.fetch_dataset_payload(descriptor.source_locator)
        except Exception as exc:
            return self._failed_result(
                dataset_id=requested_dataset_id,
                stage=PreviewFailureStage.FETCH,
                error=exc,
            )

        normalization_result = _bind_canonical_dataset_id(
            descriptor=descriptor,
            normalization_result=self._normalization_pipeline.normalize(raw_payload),
        )

        if normalization_result.status is NormalizationPipelineStatus.FAILED:
            return DatasetPreviewResult(
                dataset_id=normalization_result.dataset_id,
                status=PreviewStatus.FAILED,
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

        return DatasetPreviewResult(
            dataset_id=normalization_result.dataset_id,
            status=PreviewStatus(normalization_result.status.value),
            records=normalization_result.records,
            limitations=_collect_limitations(normalization_result),
        )

    @staticmethod
    def _failed_result(
        *,
        dataset_id: str,
        stage: PreviewFailureStage,
        error: Exception,
    ) -> DatasetPreviewResult:
        return DatasetPreviewResult(
            dataset_id=dataset_id,
            status=PreviewStatus.FAILED,
            failure=PreviewFailure(
                stage=stage,
                error_type=type(error).__name__,
                message=_public_failure_message(error),
            ),
        )


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


def _public_failure_message(error: Exception) -> str:
    """Return an operator-facing failure message without leaking connector context."""

    connector_message = getattr(error, "message", None)
    connector_source = getattr(error, "source_name", None)
    if isinstance(connector_message, str) and isinstance(connector_source, str):
        return connector_message

    return str(error)
