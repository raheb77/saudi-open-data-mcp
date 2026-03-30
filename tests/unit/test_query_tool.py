"""Unit tests for the dataset query tool."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationFailure,
    NormalizationFailureStage,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.query import (
    DatasetQueryStatus,
    DatasetQueryTool,
    QueryFailureStage,
)


def _descriptor(dataset_id: str = "sama-money-supply") -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        source_locator=f"report.aspx?cid={sum(dataset_id.encode('utf-8'))}",
        title="Money Supply",
        description="Official monetary aggregate dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=("Publication timing may vary by release cycle.",),
        known_issues=("Historical revisions may occur.",),
    )


def test_query_dataset_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetQueryTool(repository, SnapshotStore(tmp_path / "snapshots"))

    result = tool.query_dataset("missing-dataset")

    assert result.status is DatasetQueryStatus.MISSING
    assert result.dataset_id == "missing-dataset"
    assert result.source is None
    assert result.total_records_before_filter is None
    assert result.matched_records == ()


def test_query_dataset_returns_explicit_snapshot_missing_result(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SNAPSHOT_MISSING
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == descriptor.source
    assert result.total_records_before_filter is None
    assert result.matched_records == ()


def test_query_dataset_uses_source_locator_not_canonical_dataset_id_for_snapshot_reads(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.dataset_id,
        body={"rows": [{"period": "2026-01", "value": 1}]},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SNAPSHOT_MISSING
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == descriptor.source


def test_query_dataset_returns_local_canonical_records_for_supported_json_snapshot(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={
            "rows": [
                {"period": "2026-01", "value": 1},
                {"period": "2026-02", "value": 2},
            ]
        },
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == "sama"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {}
    assert result.limit is None
    assert len(result.matched_records) == 2
    assert result.matched_records[0].dataset_id == descriptor.dataset_id
    assert result.matched_records[0].record_index == 0
    assert result.matched_records[0].fields == {"period": "2026-01", "value": 1}
    assert result.matched_records[1].dataset_id == descriptor.dataset_id
    assert result.matched_records[1].record_index == 1
    assert result.matched_records[1].fields == {"period": "2026-02", "value": 2}


def test_query_dataset_applies_exact_match_filters(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={
            "rows": [
                {"period": "2026-01", "value": 1},
                {"period": "2026-02", "value": 2},
            ]
        },
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"period": "2026-02"},
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {"period": "2026-02"}
    assert len(result.matched_records) == 1
    assert result.matched_records[0].record_index == 1
    assert result.matched_records[0].fields == {"period": "2026-02", "value": 2}


def test_query_dataset_applies_limit_deterministically(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body=[
            {"period": "2026-01", "value": 1},
            {"period": "2026-02", "value": 2},
            {"period": "2026-03", "value": 3},
        ],
    )

    result = tool.query_dataset(descriptor.dataset_id, limit=2)

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 3
    assert result.limit == 2
    assert [record.record_index for record in result.matched_records] == [0, 1]


def test_query_dataset_returns_explicit_limited_result_for_unsupported_json_shape(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={"summary": {"count": 2}},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.LIMITED
    assert result.source == "sama"
    assert result.total_records_before_filter is None
    assert result.matched_records == ()
    assert result.limitations == (
        "json_body_requires_supported_object_list_shape_for_record_normalization",
    )


def test_query_dataset_returns_explicit_failed_result_for_failed_normalization(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()

    class FailedPipeline:
        def normalize(self, raw_payload: RawPayload) -> NormalizationResult:
            return NormalizationResult(
                dataset_id=raw_payload.dataset_id,
                status=NormalizationPipelineStatus.FAILED,
                failure=NormalizationFailure(
                    stage=NormalizationFailureStage.VALIDATION,
                    error_type="ValueError",
                    message="forced normalization failure",
                ),
            )

    tool = DatasetQueryTool(
        repository,
        snapshot_store,
        normalization_pipeline=FailedPipeline(),
    )

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={"rows": [{"period": "2026-01", "value": 1}]},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.FAILED
    assert result.source == "sama"
    assert result.matched_records == ()
    assert result.failure is not None
    assert result.failure.stage is QueryFailureStage.NORMALIZATION
    assert result.failure.error_type == "ValueError"
    assert result.failure.message == "forced normalization failure"


def test_query_tool_module_does_not_import_connectors_directly() -> None:
    project_root = Path(__file__).resolve().parents[2]
    query_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "query.py"
    tree = ast.parse(query_module.read_text(), filename=str(query_module))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "connectors" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "connectors" not in alias.name


def _write_snapshot(
    store: SnapshotStore,
    *,
    snapshot_dataset_id: str,
    body: object,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=snapshot_dataset_id,
        content={
            "url": (
                "https://www.sama.gov.sa/en-US/EconomicReports/Pages/"
                f"{snapshot_dataset_id}"
            ),
            "status_code": 200,
            "content_type": "application/json",
            "body": body,
        },
    )
    path = store.write_snapshot(payload)
    timestamp = datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
