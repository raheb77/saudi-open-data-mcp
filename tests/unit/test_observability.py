"""Observability tests for local logging and metrics wiring."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import Connector, RawPayload, RequestPolicy
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.observability import get_metrics, reset_metrics
from saudi_open_data_mcp.registry.bootstrap import INITIAL_DATASET_DESCRIPTORS
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.server import create_server
from saudi_open_data_mcp.tools.preview import DatasetPreviewTool, PreviewStatus


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
    )


def _repository(tmp_path: Path) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        DatasetDescriptor(
            dataset_id="sama-money-supply",
            source="sama",
            source_locator="report.aspx?cid=55",
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


def _log_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(record.getMessage()) for record in caplog.records]


def _assert_event(
    events: list[dict[str, object]],
    expected_fields: dict[str, object],
) -> None:
    for event in events:
        if all(event.get(key) == value for key, value in expected_fields.items()):
            assert isinstance(event.get("time"), str)
            assert event["time"]
            return

    raise AssertionError(f"Expected log event not found: {expected_fields!r}")


def test_create_server_emits_startup_logs_and_metrics(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    create_server(_runtime_config(tmp_path))

    metrics = get_metrics()
    assert metrics.get("server.startup.attempts") == 1
    assert metrics.get("server.startup.success") == 1

    events = _log_events(caplog)
    _assert_event(
        events,
        {
            "event": "server.startup.begin",
            "level": "info",
            "logger": "saudi_open_data_mcp.server",
            "app_name": "saudi-open-data-mcp",
        },
    )
    _assert_event(
        events,
        {
            "event": "server.startup.ready",
            "level": "info",
            "logger": "saudi_open_data_mcp.server",
            "app_name": "saudi-open-data-mcp",
            "dataset_count": len(INITIAL_DATASET_DESCRIPTORS),
        },
    )


@pytest.mark.asyncio
async def test_preview_tool_emits_completion_logs_and_metrics(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    class ConnectorSpy:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            return RawPayload(
                source="sama",
                dataset_id=dataset_id,
                content={
                    "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
                    "status_code": 200,
                    "content_type": "application/json",
                    "body": {"rows": [{"period": "2026-01", "value": 1}]},
                },
            )

    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": ConnectorSpy()}),
    )

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.results.record_derivable") == 1

    events = _log_events(caplog)
    _assert_event(
        events,
        {
            "event": "preview.request.completed",
            "level": "info",
            "logger": "saudi_open_data_mcp.tools.preview",
            "dataset_id": "sama-money-supply",
            "status": "record_derivable",
            "record_count": 1,
            "limitation_count": 0,
        },
    )


@pytest.mark.asyncio
async def test_preview_tool_emits_failure_logs_and_metrics(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

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

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.FAILED
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.results.failed") == 1

    events = _log_events(caplog)
    _assert_event(
        events,
        {
            "event": "preview.request.failed",
            "level": "warning",
            "logger": "saudi_open_data_mcp.tools.preview",
            "dataset_id": "sama-money-supply",
            "stage": "fetch",
            "error_type": "SourceUnavailableError",
            "message": "SAMA source request failed for preview testing",
        },
    )


@pytest.mark.asyncio
async def test_connector_retry_and_failure_emit_logs_and_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    class DummyConnector(Connector):
        source_name = "dummy"
        approved_base_url = "https://data.example.gov.sa"

        def __init__(self) -> None:
            self.request_policy = RequestPolicy(
                timeout_seconds=0.1,
                max_retries=1,
                retry_backoff_seconds=0.0,
            )

        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            return RawPayload(source=self.source_name, dataset_id=dataset_id, content={})

    retry_connector = DummyConnector()
    retry_responses = iter(
        [
            httpx.Response(
                503,
                request=httpx.Request("GET", "https://data.example.gov.sa/dataset"),
                text="service unavailable",
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://data.example.gov.sa/dataset"),
                json={"rows": []},
            ),
        ]
    )

    retry_result = await retry_connector.execute_request_with_retries(
        lambda: _next_response(retry_responses),
        dataset_id="dataset-1",
        source_label="Dummy",
    )

    assert retry_result.status_code == 200
    metrics = get_metrics()
    assert metrics.get("connector.request_attempts.dummy") == 2
    assert metrics.get("connector.request_retries.dummy") == 1
    assert metrics.get("connector.request_failures.dummy") == 0

    retry_events = _log_events(caplog)
    _assert_event(
        retry_events,
        {
            "event": "connector.request.retry_scheduled",
            "level": "info",
            "logger": "saudi_open_data_mcp.connectors.base",
            "source": "dummy",
            "dataset_id": "dataset-1",
            "error_type": "SourceUnavailableError",
            "message": "Dummy source returned HTTP 503",
            "retries_used": 0,
            "backoff_seconds": 0.0,
        },
    )

    caplog.clear()
    reset_metrics()
    failing_connector = DummyConnector()
    failing_responses = iter(
        [
            httpx.Response(
                503,
                request=httpx.Request("GET", "https://data.example.gov.sa/dataset"),
                text="service unavailable",
            ),
            httpx.Response(
                503,
                request=httpx.Request("GET", "https://data.example.gov.sa/dataset"),
                text="service unavailable",
            ),
        ]
    )

    with pytest.raises(SourceUnavailableError):
        await failing_connector.execute_request_with_retries(
            lambda: _next_response(failing_responses),
            dataset_id="dataset-1",
            source_label="Dummy",
        )

    metrics = get_metrics()
    assert metrics.get("connector.request_attempts.dummy") == 2
    assert metrics.get("connector.request_retries.dummy") == 1
    assert metrics.get("connector.request_failures.dummy") == 1

    failure_events = _log_events(caplog)
    _assert_event(
        failure_events,
        {
            "event": "connector.request.failed",
            "level": "warning",
            "logger": "saudi_open_data_mcp.connectors.base",
            "source": "dummy",
            "dataset_id": "dataset-1",
            "error_type": "SourceUnavailableError",
            "message": "Dummy source returned HTTP 503",
            "retries_used": 1,
        },
    )


async def _next_response(responses: object) -> httpx.Response:
    return next(responses)
