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

DatasetPayloadFetcher = Callable[[str], Awaitable[Any]]


class PreviewStatus(StrEnum):
    """Preview status aligned to the current normalization capability."""

    RECORD_DERIVABLE = "record_derivable"
    LIMITED = "limited"
    FAILED = "failed"


class PreviewFailureStage(StrEnum):
    """Preview failure stage."""

    FETCH = "fetch"
    NORMALIZATION = "normalization"


class PreviewFailure(BaseModel):
    """Explicit failure details for preview execution."""

    model_config = ConfigDict(extra="forbid")

    stage: PreviewFailureStage
    error_type: str
    message: str


class DatasetPreviewResult(BaseModel):
    """Typed preview result for a dataset or source-specific locator."""

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
    """Preview tool that composes injected raw payload fetching with normalization.

    In v0.1, the public ``dataset_id`` argument is passed through to the injected
    fetcher as the current source-supported locator. For SAMA, that means a
    report locator such as ``report.aspx?cid=55`` rather than a canonical
    registry-owned dataset identity.
    """

    def __init__(
        self,
        payload_fetcher: DatasetPayloadFetcher,
        *,
        normalization_pipeline: PreviewPipeline | None = None,
    ) -> None:
        self._payload_fetcher = payload_fetcher
        self._normalization_pipeline = normalization_pipeline or NormalizationPipeline()

    async def preview_dataset(self, dataset_id: str) -> DatasetPreviewResult:
        """Fetch a raw payload and return an honest normalization-based preview."""

        requested_dataset_id = dataset_id.strip()
        if not requested_dataset_id:
            return self._failed_fetch_result(
                dataset_id=dataset_id,
                error=ValueError("dataset_id must not be empty"),
            )

        try:
            raw_payload = await self._payload_fetcher(requested_dataset_id)
        except Exception as exc:
            return self._failed_fetch_result(
                dataset_id=requested_dataset_id,
                error=exc,
            )

        normalization_result = self._normalization_pipeline.normalize(raw_payload)

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
    def _failed_fetch_result(dataset_id: str, error: Exception) -> DatasetPreviewResult:
        return DatasetPreviewResult(
            dataset_id=dataset_id,
            status=PreviewStatus.FAILED,
            failure=PreviewFailure(
                stage=PreviewFailureStage.FETCH,
                error_type=type(error).__name__,
                message=str(error),
            ),
        )


def register(app: FastMCP) -> None:
    """Defer FastMCP registration until server wiring expands to preview support."""

    _ = app
