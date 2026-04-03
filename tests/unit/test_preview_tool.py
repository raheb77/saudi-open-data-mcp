"""Unit tests for the hybrid dataset preview tool."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.rate_limit import RateLimitPolicy
from saudi_open_data_mcp.storage.freshness import SnapshotFreshnessStatus
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.preview import (
    LOCAL_PREVIEW_MISS_NOTICE,
    STALE_FALLBACK_NOTICE,
    DatasetPreviewResult,
    DatasetPreviewTool,
    PreviewDataOrigin,
    PreviewFailureStage,
    PreviewResolutionOutcome,
    PreviewStatus,
)

DATASET_ID = "sama-money-supply"
REPORT_LOCATOR = "report.aspx?cid=55"
REFERENCE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class _ConnectorSpy:
    def __init__(self, responses: list[RawPayload | Exception]) -> None:
        self._responses = iter(responses)
        self.calls: list[str] = []

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        self.calls.append(dataset_id)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _repository(
    tmp_path: Path,
    *,
    source: str = "sama",
    dataset_id: str = DATASET_ID,
    source_locator: str = REPORT_LOCATOR,
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY,
) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        DatasetDescriptor(
            dataset_id=dataset_id,
            source=source,
            source_locator=source_locator,
            title="Money Supply",
            description="Official monetary aggregate dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=update_frequency,
            health_status=DatasetHealthStatus.UNKNOWN,
            caveats=("Publication timing may vary by release cycle.",),
            known_issues=("Historical revisions may occur.",),
        )
    )
    return repository


def _snapshot_store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


def _tool(
    tmp_path: Path,
    connector: _ConnectorSpy,
    *,
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY,
    rate_limit_policy: RateLimitPolicy | None = None,
    time_source=None,
) -> DatasetPreviewTool:
    return DatasetPreviewTool(
        _repository(tmp_path, update_frequency=update_frequency),
        SourceConnectorResolver({"sama": connector}),
        snapshot_store=_snapshot_store(tmp_path),
        rate_limit_policy=rate_limit_policy,
        time_source=time_source,
    )


def _payload(
    *,
    locator: str = REPORT_LOCATOR,
    body: object | None = None,
    content_type: str = "application/json",
) -> RawPayload:
    if locator.startswith("/"):
        url = f"https://www.sama.gov.sa{locator}"
    else:
        url = f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{locator}"

    return RawPayload(
        source="sama",
        dataset_id=locator,
        content={
            "url": url,
            "status_code": 200,
            "content_type": content_type,
            "body": body if body is not None else {"rows": [{"period": "2026-01", "value": 1}]},
        },
    )


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    locator: str = REPORT_LOCATOR,
    modified_at: datetime,
    body: object | None = None,
    content_type: str = "application/json",
) -> Path:
    path = store.write_snapshot(
        _payload(locator=locator, body=body, content_type=content_type)
    )
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


@pytest.mark.asyncio
async def test_fresh_snapshot_is_served_locally(tmp_path: Path) -> None:
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        modified_at=datetime(2026, 1, 14, 12, 0, tzinfo=UTC),
    )
    connector = _ConnectorSpy([])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert isinstance(result, DatasetPreviewResult)
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.snapshot_modified_at == datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    assert result.resolution_notice is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == DATASET_ID
    assert connector.calls == []


@pytest.mark.asyncio
async def test_fresh_snapshot_local_miss_logs_and_refreshes_live(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    snapshot_path = _snapshot_store(tmp_path).snapshot_path("sama", REPORT_LOCATOR)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("not valid raw payload json", encoding="utf-8")
    timestamp = datetime(2026, 1, 14, 12, 0, tzinfo=UTC).timestamp()
    os.utime(snapshot_path, (timestamp, timestamp))

    connector = _ConnectorSpy([_payload()])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.resolution_notice == LOCAL_PREVIEW_MISS_NOTICE
    assert connector.calls == [REPORT_LOCATOR]
    assert any(
        json.loads(record.getMessage()).get("event")
        == "preview.request.local_artifact_unusable"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_stale_snapshot_refreshes_successfully_then_serves_live(tmp_path: Path) -> None:
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        modified_at=datetime(2025, 12, 1, 0, 0, tzinfo=UTC),
        body={"rows": [{"period": "2025-12", "value": 1}]},
    )
    connector = _ConnectorSpy(
        [_payload(body={"rows": [{"period": "2026-01", "value": 2}]})]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.snapshot_modified_at is not None
    assert result.records[0].fields == {"period": "2026-01", "value": 2}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_stale_snapshot_failed_refresh_falls_back_to_stale_snapshot(
    tmp_path: Path,
) -> None:
    store = _snapshot_store(tmp_path)
    stale_time = datetime(2025, 12, 1, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
        store,
        modified_at=stale_time,
        body={"rows": [{"period": "2025-12", "value": 1}]},
    )
    connector = _ConnectorSpy(
        [
            SourceUnavailableError(
                source_name="sama",
                dataset_id=REPORT_LOCATOR,
                message="SAMA source request failed for preview testing",
            )
        ]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
    assert result.data_origin is PreviewDataOrigin.STALE_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.STALE
    assert result.snapshot_modified_at == stale_time
    assert result.resolution_notice == STALE_FALLBACK_NOTICE
    assert result.records[0].fields == {"period": "2025-12", "value": 1}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_missing_snapshot_refresh_uses_unknown_freshness_for_unspecified_frequency(
    tmp_path: Path,
) -> None:
    connector = _ConnectorSpy(
        [_payload(body={"rows": [{"status": "single", "count": 10}]})]
    )
    tool = _tool(
        tmp_path,
        connector,
        update_frequency=UpdateFrequency.UNSPECIFIED,
    )

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.UNKNOWN
    assert result.snapshot_modified_at is not None
    assert result.records[0].fields == {"status": "single", "count": 10}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_missing_snapshot_failed_refresh_fails_closed(tmp_path: Path) -> None:
    connector = _ConnectorSpy(
        [
            SourceUnavailableError(
                source_name="sama",
                dataset_id=REPORT_LOCATOR,
                message="SAMA source request failed for preview testing",
            )
        ]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.FAILED
    assert result.resolution_outcome is PreviewResolutionOutcome.FAIL_CLOSED
    assert result.data_origin is None
    assert result.freshness_status is SnapshotFreshnessStatus.MISSING
    assert result.snapshot_modified_at is None
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "SourceUnavailableError"
    assert result.failure.message == "SAMA source request failed for preview testing"
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_rate_limit_applies_only_to_refresh_path_not_local_reads(
    tmp_path: Path,
) -> None:
    connector = _ConnectorSpy([_payload()])
    tool = _tool(
        tmp_path,
        connector,
        rate_limit_policy=RateLimitPolicy(requests=1, window_seconds=60),
        time_source=lambda: 100.0,
    )

    first_result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)
    second_result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert first_result.status is PreviewStatus.RECORD_DERIVABLE
    assert first_result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert first_result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert second_result.status is PreviewStatus.RECORD_DERIVABLE
    assert second_result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert second_result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_preview_tool_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    tool = DatasetPreviewTool(
        RegistryRepository(tmp_path / "registry.sqlite"),
        SourceConnectorResolver({}),
        snapshot_store=_snapshot_store(tmp_path),
    )

    result = await tool.preview_dataset("missing-dataset")

    assert result.status is PreviewStatus.MISSING
    assert result.dataset_id == "missing-dataset"
    assert result.resolution_outcome is None
    assert result.data_origin is None
    assert result.freshness_status is None
    assert result.snapshot_modified_at is None
    assert result.records == ()
    assert result.limitations == ()
    assert result.failure is None


@pytest.mark.asyncio
async def test_non_connector_failures_keep_standard_string_representation(
    tmp_path: Path,
) -> None:
    class FormattedError(Exception):
        def __str__(self) -> str:
            return "formatted generic failure"

    connector = _ConnectorSpy([FormattedError()])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.FAILED
    assert result.resolution_outcome is PreviewResolutionOutcome.FAIL_CLOSED
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "FormattedError"
    assert result.failure.message == "formatted generic failure"
