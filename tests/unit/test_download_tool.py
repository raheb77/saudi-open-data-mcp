"""Unit tests for the dataset download tool."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.freshness import SnapshotFreshnessStatus
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.download import (
    DatasetDownloadReason,
    DatasetDownloadResult,
    DatasetDownloadStatus,
    DatasetDownloadTool,
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


def test_get_dataset_download_returns_explicit_unknown_dataset_result(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetDownloadTool(repository, SnapshotStore(tmp_path / "snapshots"))

    result = tool.get_dataset_download("missing-dataset")

    assert isinstance(result, DatasetDownloadResult)
    assert result.status is DatasetDownloadStatus.UNKNOWN_DATASET
    assert result.reason is DatasetDownloadReason.DATASET_NOT_IN_REGISTRY
    assert result.local_snapshot_exists is False
    assert result.source is None
    assert result.snapshot_path is None
    assert result.freshness is None


def test_get_dataset_download_returns_explicit_missing_local_artifact(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetDownloadTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    result = tool.get_dataset_download(descriptor.dataset_id)

    assert result.status is DatasetDownloadStatus.ARTIFACT_MISSING
    assert result.reason is DatasetDownloadReason.NO_LOCAL_SNAPSHOT
    assert result.dataset_id == descriptor.dataset_id
    assert result.local_snapshot_exists is False
    assert result.source == "sama"
    assert result.snapshot_path == snapshot_store.snapshot_path(
        "sama",
        descriptor.source_locator,
    )
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.status is SnapshotFreshnessStatus.MISSING


def test_get_dataset_download_uses_source_locator_not_canonical_dataset_id_for_lookup(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor(dataset_id="sama-interest-rates")
    tool = DatasetDownloadTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot_with_mtime(
        snapshot_store,
        snapshot_dataset_id=descriptor.dataset_id,
        modified_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    result = tool.get_dataset_download(descriptor.dataset_id)

    assert result.status is DatasetDownloadStatus.ARTIFACT_MISSING
    assert result.reason is DatasetDownloadReason.NO_LOCAL_SNAPSHOT
    assert result.dataset_id == descriptor.dataset_id
    assert result.snapshot_path == snapshot_store.snapshot_path(
        "sama",
        descriptor.source_locator,
    )


def test_get_dataset_download_returns_available_local_artifact_result(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor(dataset_id="sama-interest-rates")
    tool = DatasetDownloadTool(repository, snapshot_store)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    reference_time = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

    repository.upsert_dataset(descriptor)
    snapshot_path = _write_snapshot_with_mtime(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        modified_at=snapshot_time,
    )
    result = tool.get_dataset_download(
        descriptor.dataset_id,
        reference_time=reference_time,
    )

    assert result.status is DatasetDownloadStatus.AVAILABLE
    assert result.reason is DatasetDownloadReason.LOCAL_SNAPSHOT_AVAILABLE
    assert result.dataset_id == descriptor.dataset_id
    assert result.local_snapshot_exists is True
    assert result.source == "sama"
    assert result.snapshot_path == snapshot_path
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.status is SnapshotFreshnessStatus.FRESH
    assert result.freshness.snapshot_modified_at == snapshot_time


def test_get_dataset_download_keeps_available_result_when_freshness_is_stale(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor(dataset_id="sama-balance-of-payments")
    tool = DatasetDownloadTool(repository, snapshot_store)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    reference_time = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)

    repository.upsert_dataset(descriptor)
    snapshot_path = _write_snapshot_with_mtime(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        modified_at=snapshot_time,
    )
    result = tool.get_dataset_download(
        descriptor.dataset_id,
        reference_time=reference_time,
    )

    assert result.status is DatasetDownloadStatus.AVAILABLE
    assert result.reason is DatasetDownloadReason.LOCAL_SNAPSHOT_AVAILABLE
    assert result.dataset_id == descriptor.dataset_id
    assert result.local_snapshot_exists is True
    assert result.source == "sama"
    assert result.snapshot_path == snapshot_path
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.status is SnapshotFreshnessStatus.STALE
    assert result.freshness.snapshot_modified_at == snapshot_time


def test_download_tool_module_does_not_import_connectors_directly() -> None:
    project_root = Path(__file__).resolve().parents[2]
    download_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "download.py"
    tree = ast.parse(download_module.read_text(), filename=str(download_module))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "connectors" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "connectors" not in alias.name


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    snapshot_dataset_id: str,
    modified_at: datetime,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=snapshot_dataset_id,
        content={"body": {"rows": []}},
    )
    path = store.write_snapshot(payload)
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
