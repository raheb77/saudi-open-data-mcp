"""Unit tests for the dataset preview tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.tools.preview import (
    DatasetPreviewResult,
    DatasetPreviewTool,
    PreviewFailureStage,
    PreviewStatus,
)

DATASET_ID = "sama-money-supply"
REPORT_LOCATOR = "report.aspx?cid=55"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


def _repository(tmp_path: Path) -> RegistryRepository:
    return _repository_with_source(tmp_path, source="sama")


def _repository_with_source(tmp_path: Path, *, source: str) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        DatasetDescriptor(
            dataset_id=DATASET_ID,
            source=source,
            source_locator=REPORT_LOCATOR,
            title="Money Supply",
            description="Official monetary aggregate dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.UNKNOWN,
            caveats=("Publication timing may vary by release cycle.",),
            known_issues=("Historical revisions may occur.",),
        )
    )
    return repository


@pytest.mark.asyncio
@respx.mock
async def test_json_payload_returns_record_derivable_preview_result(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    connector = SAMAConnector()
    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": connector}),
    )

    result = await tool.preview_dataset(DATASET_ID)

    assert isinstance(result, DatasetPreviewResult)
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert result.dataset_id == DATASET_ID
    assert result.limitations == ()
    assert "normalization_result" not in result.model_dump(mode="json")
    assert len(result.records) == 1
    assert result.records[0].dataset_id == DATASET_ID
    assert result.records[0].source == "sama"
    assert result.records[0].record_index == 0
    assert result.records[0].fields == {
        "period": "2026-01",
        "value": 1,
    }


@pytest.mark.asyncio
@respx.mock
async def test_html_payload_returns_limited_preview_result(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = SAMAConnector()
    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": connector}),
    )

    result = await tool.preview_dataset(DATASET_ID)

    assert result.status is PreviewStatus.LIMITED
    assert result.failure is None
    assert result.dataset_id == DATASET_ID
    assert result.records == ()
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
    )
    assert "normalization_result" not in result.model_dump(mode="json")


@pytest.mark.asyncio
async def test_connector_failure_becomes_explicit_preview_failure(tmp_path: Path) -> None:
    class FailingConnector:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            raise SourceUnavailableError(
                source_name="sama",
                dataset_id=dataset_id,
                message="SAMA source request failed for preview testing",
            )

    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": FailingConnector()}),
    )

    result = await tool.preview_dataset(DATASET_ID)

    assert result.status is PreviewStatus.FAILED
    assert result.dataset_id == DATASET_ID
    assert result.records == ()
    assert result.limitations == ()
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "SourceUnavailableError"


@pytest.mark.asyncio
async def test_preview_tool_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    tool = DatasetPreviewTool(
        RegistryRepository(tmp_path / "registry.sqlite"),
        SourceConnectorResolver({}),
    )

    result = await tool.preview_dataset("missing-dataset")

    assert result.status is PreviewStatus.MISSING
    assert result.dataset_id == "missing-dataset"
    assert result.records == ()
    assert result.limitations == ()
    assert result.failure is None


@pytest.mark.asyncio
async def test_preview_tool_uses_registry_lookup_and_normalization_pipeline(
    tmp_path: Path,
) -> None:
    captured_payloads: list[Any] = []
    resolved_sources: list[str] = []
    requested_locators: list[str] = []
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

    class ConnectorSpy:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            requested_locators.append(dataset_id)
            assert dataset_id == REPORT_LOCATOR
            return raw_payload

    class ResolverSpy:
        def resolve(self, source: str) -> ConnectorSpy:
            resolved_sources.append(source)
            assert source == "sama"
            return ConnectorSpy()

    tool = DatasetPreviewTool(
        _repository(tmp_path),
        ResolverSpy(),
        normalization_pipeline=PipelineSpy(),
    )

    result = await tool.preview_dataset(DATASET_ID)

    assert resolved_sources == ["sama"]
    assert requested_locators == [REPORT_LOCATOR]
    assert captured_payloads == [raw_payload]
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.dataset_id == DATASET_ID
    assert result.records == ()
    assert result.limitations == ()


@pytest.mark.asyncio
async def test_preview_tool_fails_explicitly_for_unsupported_source(tmp_path: Path) -> None:
    tool = DatasetPreviewTool(
        _repository_with_source(tmp_path, source="unsupported-source"),
        SourceConnectorResolver({"sama": SAMAConnector()}),
    )

    result = await tool.preview_dataset(DATASET_ID)

    assert result.status is PreviewStatus.FAILED
    assert result.dataset_id == DATASET_ID
    assert result.records == ()
    assert result.limitations == ()
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "ConnectorNotImplementedError"
    assert "unsupported-source" in result.failure.message
