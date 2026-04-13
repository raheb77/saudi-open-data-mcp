"""Observability tests for local logging and metrics wiring."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from saudi_open_data_mcp import server as server_module
from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import Connector, RawPayload, RequestPolicy
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.observability import (
    build_observability_summary,
    get_metrics,
    reset_metrics,
)
from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.rate_limit import RateLimitPolicy
from saudi_open_data_mcp.server import create_server
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.materialize import HotSetMaterializationTool
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
            coverage_status=DatasetCoverageStatus.QUERYABLE,
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
    assert metrics.get("server.startup.ready") == 1
    assert metrics.get("server.startup.failures") == 0

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


def test_build_observability_summary_groups_existing_counters() -> None:
    metrics = get_metrics()
    metrics.increment("server.startup.attempts")
    metrics.increment("preview.requests", 2)
    metrics.increment("preview.live_refresh")
    metrics.increment("http.auth.requests", 3)
    metrics.increment("http.auth.accepted", 2)
    metrics.increment("http.authz.rejected")
    metrics.increment("http.authz.rejected.insufficient_capability")
    metrics.increment("http.authz.coverage_missing")
    metrics.increment("connector.retries")
    metrics.increment("connector.request_attempts.sama", 3)
    metrics.increment("materialize.requests")
    metrics.increment("materialize.successes", 5)
    metrics.increment("tier_a_refresh.runs", 2)
    metrics.increment("tier_a_refresh.run_failures")

    summary = build_observability_summary(metrics)
    groups = {group.name: group for group in summary.groups}

    assert summary.process_local is True
    assert summary.raw_counters == {
        "connector.request_attempts.sama": 3,
        "connector.retries": 1,
        "http.auth.accepted": 2,
        "http.auth.requests": 3,
        "http.authz.rejected": 1,
        "http.authz.rejected.insufficient_capability": 1,
        "http.authz.coverage_missing": 1,
        "materialize.requests": 1,
        "materialize.successes": 5,
        "preview.live_refresh": 1,
        "preview.requests": 2,
        "server.startup.attempts": 1,
        "tier_a_refresh.run_failures": 1,
        "tier_a_refresh.runs": 2,
    }
    assert groups["startup"].counters[0].model_dump() == {
        "name": "server.startup.attempts",
        "value": 1,
    }
    assert groups["preview"].counters[0].model_dump() == {
        "name": "preview.requests",
        "value": 2,
    }
    assert groups["preview"].counters[2].model_dump() == {
        "name": "preview.live_refresh",
        "value": 1,
    }
    assert groups["auth"].counters[0].model_dump() == {
        "name": "http.auth.requests",
        "value": 3,
    }
    assert groups["auth"].counters[5].model_dump() == {
        "name": "http.authz.rejected",
        "value": 1,
    }
    assert groups["auth"].counters[6].model_dump() == {
        "name": "http.authz.rejected.insufficient_capability",
        "value": 1,
    }
    assert groups["auth"].counters[7].model_dump() == {
        "name": "http.authz.coverage_missing",
        "value": 1,
    }
    assert tuple(
        counter.model_dump() for counter in groups["connectors"].detail_counters
    ) == ({"name": "connector.request_attempts.sama", "value": 3},)
    assert groups["tier_a_refresh"].counters[0].model_dump() == {
        "name": "tier_a_refresh.runs",
        "value": 2,
    }
    assert groups["tier_a_refresh"].counters[1].model_dump() == {
        "name": "tier_a_refresh.run_failures",
        "value": 1,
    }
    assert "process-local" in summary.notes[0]
    assert "tier_a_refresh.*" in summary.notes[2]


def test_create_server_emits_startup_failure_logs_and_metrics(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.INFO)

    def _boom(_repository: RegistryRepository) -> list[object]:
        raise RuntimeError("bootstrap failed for testing")

    monkeypatch.setattr(server_module, "bootstrap_registry", _boom)

    with pytest.raises(RuntimeError, match="bootstrap failed for testing"):
        create_server(_runtime_config(tmp_path))

    metrics = get_metrics()
    assert metrics.get("server.startup.attempts") == 1
    assert metrics.get("server.startup.ready") == 0
    assert metrics.get("server.startup.failures") == 1

    events = _log_events(caplog)
    _assert_event(
        events,
        {
            "event": "server.startup.failed",
            "level": "error",
            "logger": "saudi_open_data_mcp.server",
            "app_name": "saudi-open-data-mcp",
            "error_type": "RuntimeError",
            "message": "bootstrap failed for testing",
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
        snapshot_store=SnapshotStore(tmp_path / "snapshots"),
    )

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.live_refresh") == 1
    assert metrics.get("preview.local_snapshot") == 0
    assert metrics.get("preview.stale_fallback") == 0
    assert metrics.get("preview.failures") == 0

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
        snapshot_store=SnapshotStore(tmp_path / "snapshots"),
    )

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.FAILED
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.failures") == 1
    assert metrics.get("preview.local_snapshot") == 0
    assert metrics.get("preview.live_refresh") == 0
    assert metrics.get("preview.stale_fallback") == 0

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
async def test_preview_tool_emits_snapshot_write_failure_logs_and_metrics(
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

    class WriteFailingSnapshotStore(SnapshotStore):
        def write_snapshot(self, payload: RawPayload) -> Path:
            raise OSError("snapshot write failed for preview testing")

    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": ConnectorSpy()}),
        snapshot_store=WriteFailingSnapshotStore(tmp_path / "snapshots"),
    )

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.FAILED
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.failures") == 1
    assert metrics.get("preview.local_snapshot") == 0
    assert metrics.get("preview.live_refresh") == 0
    assert metrics.get("preview.stale_fallback") == 0

    events = _log_events(caplog)
    _assert_event(
        events,
        {
            "event": "preview.request.failed",
            "level": "warning",
            "logger": "saudi_open_data_mcp.tools.preview",
            "dataset_id": "sama-money-supply",
            "stage": "snapshot",
            "error_type": "OSError",
            "message": "snapshot write failed for preview testing",
        },
    )


@pytest.mark.asyncio
async def test_preview_tool_emits_local_snapshot_metrics(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id="report.aspx?cid=55",
            content={
                "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
                "status_code": 200,
                "content_type": "application/json",
                "body": {"rows": [{"period": "2026-01", "value": 1}]},
            },
        )
    )

    class UnusedConnector:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            raise AssertionError("connector should not be called for local snapshot preview")

    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": UnusedConnector()}),
        snapshot_store=snapshot_store,
    )

    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.local_snapshot") == 1
    assert metrics.get("preview.live_refresh") == 0
    assert metrics.get("preview.stale_fallback") == 0
    assert metrics.get("preview.failures") == 0


@pytest.mark.asyncio
async def test_preview_tool_emits_stale_fallback_metrics(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    snapshot_path = snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id="report.aspx?cid=55",
            content={
                "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
                "status_code": 200,
                "content_type": "application/json",
                "body": {"rows": [{"period": "2025-12", "value": 1}]},
            },
        )
    )
    stale_timestamp = datetime(2025, 12, 1, 0, 0, tzinfo=UTC).timestamp()
    os.utime(snapshot_path, (stale_timestamp, stale_timestamp))

    class FailingConnector:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            raise SourceUnavailableError(
                source_name="sama",
                dataset_id=dataset_id,
                message="refresh failed for stale fallback testing",
            )

    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": FailingConnector()}),
        snapshot_store=snapshot_store,
    )

    result = await tool.preview_dataset(
        "sama-money-supply",
        reference_time=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 1
    assert metrics.get("preview.stale_fallback") == 1
    assert metrics.get("preview.live_refresh") == 0
    assert metrics.get("preview.local_snapshot") == 0
    assert metrics.get("preview.failures") == 0


@pytest.mark.asyncio
async def test_preview_tool_emits_rate_limited_metrics(tmp_path: Path) -> None:
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
        snapshot_store=SnapshotStore(tmp_path / "snapshots"),
        rate_limit_policy=RateLimitPolicy(requests=1, window_seconds=60),
        time_source=lambda: 100.0,
    )

    await tool.preview_dataset("sama-money-supply")
    SnapshotStore(tmp_path / "snapshots").snapshot_path("sama", "report.aspx?cid=55").unlink()
    result = await tool.preview_dataset("sama-money-supply")

    assert result.status is PreviewStatus.FAILED
    metrics = get_metrics()
    assert metrics.get("preview.requests") == 2
    assert metrics.get("preview.live_refresh") == 1
    assert metrics.get("preview.rate_limited") == 1
    assert metrics.get("preview.failures") == 1


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
    assert metrics.get("connector.retries") == 1
    assert metrics.get("connector.failures") == 0

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
    assert metrics.get("connector.retries") == 1
    assert metrics.get("connector.failures") == 1

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


@pytest.mark.asyncio
async def test_materialize_tool_emits_operational_metrics(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrap_registry(repository)

    class SuccessfulConnector:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            return RawPayload(
                source="sama",
                dataset_id=dataset_id,
                content={
                    "url": "https://www.sama.gov.sa/example",
                    "status_code": 200,
                    "content_type": "application/json",
                    "body": {"rows": []},
                },
            )

    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": SuccessfulConnector()}),
        SnapshotStore(tmp_path / "snapshots"),
    )

    await tool.materialize_hot_set()

    metrics = get_metrics()
    assert metrics.get("materialize.requests") == 1
    assert metrics.get("materialize.successes") == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert metrics.get("materialize.failures") == 0


@pytest.mark.asyncio
async def test_materialize_tool_emits_failure_metrics(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrap_registry(repository)

    class FailingConnector:
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            raise SourceUnavailableError(
                source_name="sama",
                dataset_id=dataset_id,
                message="materialize fetch failed for testing",
            )

    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": FailingConnector()}),
        SnapshotStore(tmp_path / "snapshots"),
    )

    await tool.materialize_hot_set()

    metrics = get_metrics()
    assert metrics.get("materialize.requests") == 1
    assert metrics.get("materialize.successes") == 0
    assert metrics.get("materialize.failures") == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)


async def _next_response(responses: object) -> httpx.Response:
    return next(responses)
