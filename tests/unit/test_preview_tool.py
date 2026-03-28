"""Unit tests for the dataset preview tool."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.tools.preview import (
    DatasetPreviewResult,
    DatasetPreviewTool,
    PreviewFailureStage,
    PreviewStatus,
)

REPORT_LOCATOR = "report.aspx?cid=55"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


@pytest.mark.asyncio
@respx.mock
async def test_json_payload_returns_record_derivable_preview_result() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    connector = SAMAConnector()
    tool = DatasetPreviewTool(connector.fetch_dataset_payload)

    result = await tool.preview_dataset(REPORT_LOCATOR)

    assert isinstance(result, DatasetPreviewResult)
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert result.normalization_result is not None
    assert result.normalization_result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.normalization_result.records == ()


@pytest.mark.asyncio
@respx.mock
async def test_html_payload_returns_limited_preview_result() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = SAMAConnector()
    tool = DatasetPreviewTool(connector.fetch_dataset_payload)

    result = await tool.preview_dataset(REPORT_LOCATOR)

    assert result.status is PreviewStatus.LIMITED
    assert result.failure is None
    assert result.normalization_result is not None
    assert result.normalization_result.status is NormalizationPipelineStatus.LIMITED
    assert result.normalization_result.records == ()


@pytest.mark.asyncio
async def test_connector_failure_becomes_explicit_preview_failure() -> None:
    async def failing_fetcher(dataset_id: str) -> RawPayload:
        raise SourceUnavailableError(
            source_name="sama",
            dataset_id=dataset_id,
            message="SAMA source request failed for preview testing",
        )

    tool = DatasetPreviewTool(failing_fetcher)

    result = await tool.preview_dataset(REPORT_LOCATOR)

    assert result.status is PreviewStatus.FAILED
    assert result.normalization_result is None
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "SourceUnavailableError"


@pytest.mark.asyncio
async def test_preview_tool_uses_normalization_pipeline() -> None:
    captured_payloads: list[Any] = []
    raw_payload = RawPayload(
        source="sama",
        dataset_id=REPORT_LOCATOR,
        content={
            "url": _report_url(),
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": []},
        },
    )

    class PipelineSpy:
        def normalize(self, payload: Any) -> NormalizationResult:
            captured_payloads.append(payload)
            return NormalizationResult(
                dataset_id=REPORT_LOCATOR,
                status=NormalizationPipelineStatus.RECORD_DERIVABLE,
            )

    async def fetcher(dataset_id: str) -> RawPayload:
        assert dataset_id == REPORT_LOCATOR
        return raw_payload

    tool = DatasetPreviewTool(fetcher, normalization_pipeline=PipelineSpy())

    result = await tool.preview_dataset(REPORT_LOCATOR)

    assert captured_payloads == [raw_payload]
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.normalization_result is not None
