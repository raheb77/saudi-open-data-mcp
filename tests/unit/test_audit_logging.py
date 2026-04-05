"""Focused audit logging tests for important MCP core operations."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.observability import audit_context, build_token_fingerprint
from saudi_open_data_mcp.registry.bootstrap import (
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.download import DatasetDownloadTool
from saudi_open_data_mcp.tools.health import DatasetHealthTool
from saudi_open_data_mcp.tools.materialize import HotSetMaterializationTool
from saudi_open_data_mcp.tools.metadata import DatasetMetadataTool
from saudi_open_data_mcp.tools.preview import DatasetPreviewTool, PreviewStatus
from saudi_open_data_mcp.tools.query import DatasetQueryStatus, DatasetQueryTool

DATASET_ID = "sama-money-supply"
SOURCE_LOCATOR = "report.aspx?cid=55"


class _ConnectorSpy:
    def __init__(self, response: RawPayload | Exception) -> None:
        self._response = response

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        del dataset_id
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _TierAConnector:
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        if dataset_id == SOURCE_LOCATOR:
            return _raw_payload(
                dataset_id=dataset_id,
                body={"rows": [{"period": "2026-01", "value": 1}]},
                content_type="application/json",
            )

        return _raw_payload(
            dataset_id=dataset_id,
            body="<html><body>official page</body></html>",
            content_type="text/html",
        )


def _audit_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [
        payload
        for record in caplog.records
        if (payload := json.loads(record.getMessage())).get("event", "").startswith("audit.")
    ]


def _repository(tmp_path: Path) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        DatasetDescriptor(
            dataset_id=DATASET_ID,
            source="sama",
            source_locator=SOURCE_LOCATOR,
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


def _snapshot_store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


def _raw_payload(
    *,
    dataset_id: str,
    body: object,
    content_type: str,
) -> RawPayload:
    if dataset_id.startswith("/"):
        url = f"https://www.sama.gov.sa{dataset_id}"
    else:
        url = f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{dataset_id}"

    return RawPayload(
        source="sama",
        dataset_id=dataset_id,
        content={
            "url": url,
            "status_code": 200,
            "content_type": content_type,
            "body": body,
        },
    )


def test_query_dataset_emits_audit_log_with_request_context(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    repository = _repository(tmp_path)
    snapshot_store = _snapshot_store(tmp_path)
    snapshot_store.write_snapshot(
        _raw_payload(
            dataset_id=SOURCE_LOCATOR,
            body={"rows": [{"period": "2026-01", "value": 1}]},
            content_type="application/json",
        )
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    with audit_context(
        transport="http",
        actor_type="http_bearer_token",
        actor_token_fingerprint=build_token_fingerprint("internal-test-token"),
        request_id="req-123",
        rpc_request_id="rpc-1",
        path="/mcp",
    ):
        result = tool.query_dataset(DATASET_ID, filters={"period": "2026-01"})

    assert result.status is DatasetQueryStatus.SUCCESS
    events = _audit_events(caplog)
    assert any(
        event["event"] == "audit.query_dataset"
        and event["dataset_id"] == DATASET_ID
        and event["result_status"] == "success"
        and event["request_id"] == "req-123"
        and event["rpc_request_id"] == "rpc-1"
        and event["transport"] == "http"
        and event["matched_record_count"] == 1
        and event["actor_token_fingerprint"] == build_token_fingerprint("internal-test-token")
        for event in events
    )


@pytest.mark.asyncio
async def test_preview_dataset_emits_audit_log_for_fetch_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    repository = _repository(tmp_path)
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver(
            {
                "sama": _ConnectorSpy(
                    SourceUnavailableError(
                        source_name="sama",
                        dataset_id=SOURCE_LOCATOR,
                        message="preview fetch failed for audit testing",
                    )
                )
            }
        ),
        snapshot_store=_snapshot_store(tmp_path),
    )

    with audit_context(
        transport="http",
        actor_type="http_bearer_token",
        actor_token_fingerprint=build_token_fingerprint("internal-test-token"),
        request_id="req-preview",
        rpc_request_id="rpc-preview",
        path="/mcp",
    ):
        result = await tool.preview_dataset(
            DATASET_ID,
            reference_time=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )

    assert result.status is PreviewStatus.FAILED
    events = _audit_events(caplog)
    assert any(
        event["event"] == "audit.preview_dataset"
        and event["dataset_id"] == DATASET_ID
        and event["result_status"] == "failed"
        and event["request_id"] == "req-preview"
        and event["failure_stage"] == "fetch"
        and event["resolution_outcome"] == "fail_closed"
        for event in events
    )


def test_metadata_health_and_download_emit_audit_logs(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    repository = _repository(tmp_path)
    snapshot_store = _snapshot_store(tmp_path)
    snapshot_store.write_snapshot(
        _raw_payload(
            dataset_id=SOURCE_LOCATOR,
            body={"rows": [{"period": "2026-01", "value": 1}]},
            content_type="application/json",
        )
    )

    metadata_tool = DatasetMetadataTool(repository)
    health_tool = DatasetHealthTool(repository, snapshot_store)
    download_tool = DatasetDownloadTool(repository, snapshot_store)

    with audit_context(
        transport="http",
        actor_type="http_bearer_token",
        actor_token_fingerprint=build_token_fingerprint("internal-test-token"),
        request_id="req-meta",
        path="/mcp",
    ):
        metadata_tool.get_dataset_metadata(DATASET_ID)
        health_tool.get_dataset_health(DATASET_ID)
        download_tool.get_dataset_download(DATASET_ID)

    events = _audit_events(caplog)
    assert any(
        event["event"] == "audit.dataset_metadata"
        and event["dataset_id"] == DATASET_ID
        and event["result_status"] == "found"
        for event in events
    )
    assert any(
        event["event"] == "audit.dataset_health"
        and event["dataset_id"] == DATASET_ID
        and event["result_status"] == "found"
        and event["freshness_status"] == "fresh"
        for event in events
    )
    assert any(
        event["event"] == "audit.download_dataset"
        and event["dataset_id"] == DATASET_ID
        and event["result_status"] == "available"
        and event["local_snapshot_exists"] is True
        for event in events
    )


@pytest.mark.asyncio
async def test_materialize_hot_set_emits_audit_log_summary(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrap_registry(repository)
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": _TierAConnector()}),
        snapshot_store=_snapshot_store(tmp_path),
    )

    with audit_context(
        transport="http",
        actor_type="http_bearer_token",
        actor_token_fingerprint=build_token_fingerprint("internal-test-token"),
        request_id="req-materialize",
        rpc_request_id="rpc-materialize",
        path="/mcp",
    ):
        result = await tool.materialize_hot_set()

    assert result.materialized_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    events = _audit_events(caplog)
    assert any(
        event["event"] == "audit.materialize_hot_set"
        and event["result_status"] == "success"
        and event["request_id"] == "req-materialize"
        and event["requested_dataset_count"] == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
        and event["materialized_count"] == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
        and event["failed_count"] == 0
        for event in events
    )
