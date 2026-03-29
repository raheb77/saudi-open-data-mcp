"""Typed dataset preview tool over the connector and normalization path."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, Protocol, Self

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import DatasetDescriptor
from saudi_open_data_mcp.registry.repository import RegistryRepository

DatasetPayloadFetcher = Callable[[str], Awaitable[Any]]


class PreviewStatus(StrEnum):
    """Preview status aligned to the current normalization capability."""

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
    normalization_result: NormalizationResult | None = None
    failure: PreviewFailure | None = None

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        if self.status is PreviewStatus.FAILED:
            if self.failure is None:
                raise ValueError("failure details must be present when preview status is failed")
            if (
                self.normalization_result is not None
                and self.normalization_result.status is not NormalizationPipelineStatus.FAILED
            ):
                raise ValueError(
                    "failed preview results may only carry failed normalization results"
                )
            return self

        if self.failure is not None:
            raise ValueError("failure details must be absent for successful preview results")
        if self.normalization_result is None:
            raise ValueError(
                "normalization_result must be present for record-derivable or limited previews"
            )
        if self.normalization_result.dataset_id != self.dataset_id:
            raise ValueError("dataset_id must match normalization_result.dataset_id")
        if self.status.value != self.normalization_result.status.value:
            raise ValueError("preview status must match normalization pipeline status")
        return self


class PreviewPipeline(Protocol):
    """Minimal protocol for pipeline injection without widening tool boundaries."""

    def normalize(self, raw_payload: Any) -> NormalizationResult:
        """Return a typed normalization result for a fetched raw payload."""


class DatasetPreviewTool:
    """Preview tool that resolves canonical dataset ids to source locators."""

    def __init__(
        self,
        repository: RegistryRepository,
        payload_fetcher: DatasetPayloadFetcher,
        *,
        normalization_pipeline: PreviewPipeline | None = None,
    ) -> None:
        self._repository = repository
        self._payload_fetcher = payload_fetcher
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
            return self._failed_result(
                dataset_id=requested_dataset_id,
                stage=PreviewFailureStage.LOOKUP,
                error=LookupError(
                    f"dataset_id '{requested_dataset_id}' is not present in the registry"
                ),
            )

        try:
            raw_payload = await self._payload_fetcher(descriptor.source_locator)
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
                normalization_result=normalization_result,
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
            normalization_result=normalization_result,
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
                message=str(error),
            ),
        )


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    normalization_result: NormalizationResult,
) -> NormalizationResult:
    """Rewrite source-locator-based preview output to the canonical dataset identity."""

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


def register(app: FastMCP) -> None:
    """Defer FastMCP registration until server wiring expands to preview support."""

    _ = app
