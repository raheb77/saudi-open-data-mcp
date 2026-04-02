"""Unit tests for the dataset health tool."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    HealthMetadata,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.health import (
    DatasetHealthLookupResult,
    DatasetHealthTool,
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


def test_get_dataset_health_returns_typed_health_for_known_dataset(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor()
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    tool = DatasetHealthTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    result = tool.get_dataset_health(descriptor.dataset_id)

    assert isinstance(result, DatasetHealthLookupResult)
    assert result.status == "found"
    assert result.dataset_id == descriptor.dataset_id
    assert result.health_status is DatasetHealthStatus.UNKNOWN
    assert result.schema_version == descriptor.schema_version
    assert result.caveats == descriptor.caveats
    assert result.known_issues == descriptor.known_issues
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.artifact_present is False
    assert result.freshness.status is SnapshotFreshnessStatus.MISSING
    assert result.freshness.reason is SnapshotFreshnessReason.NO_SNAPSHOT


def test_get_dataset_health_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetHealthTool(repository)

    result = tool.get_dataset_health("missing-dataset")

    assert isinstance(result, DatasetHealthLookupResult)
    assert result.status == "missing"
    assert result.dataset_id == "missing-dataset"
    assert result.health_status is None
    assert result.schema_version is None
    assert result.caveats == ()
    assert result.known_issues == ()
    assert result.freshness is None


def test_get_dataset_health_matches_registry_backed_health_metadata(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(dataset_id="sama-interest-rates")
    tool = DatasetHealthTool(repository)

    repository.upsert_dataset(descriptor)
    repository.upsert_health(
        HealthMetadata(
            dataset_id=descriptor.dataset_id,
            health_status=DatasetHealthStatus.DEGRADED,
        )
    )
    stored_health = repository.get_health(descriptor.dataset_id)
    result = tool.get_dataset_health(descriptor.dataset_id)

    assert stored_health is not None
    assert result.status == "found"
    assert result.health_status == stored_health.health_status


def test_get_dataset_health_includes_deterministic_recent_snapshot_freshness(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor(dataset_id="sama-balance-of-payments")
    tool = DatasetHealthTool(repository, snapshot_store)
    reference_time = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    repository.upsert_dataset(descriptor)
    _write_snapshot_with_mtime(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        modified_at=snapshot_time,
    )
    result = tool.get_dataset_health(
        descriptor.dataset_id,
        reference_time=reference_time,
    )

    assert result.status == "found"
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.artifact_present is True
    assert result.freshness.status is SnapshotFreshnessStatus.FRESH
    assert result.freshness.reason is SnapshotFreshnessReason.WITHIN_EXPECTED_WINDOW
    assert result.freshness.snapshot_modified_at == snapshot_time


def test_get_dataset_health_ignores_snapshot_stored_only_under_canonical_dataset_id(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor(dataset_id="sama-interest-rates")
    tool = DatasetHealthTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot_with_mtime(
        snapshot_store,
        snapshot_dataset_id=descriptor.dataset_id,
        modified_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    result = tool.get_dataset_health(descriptor.dataset_id)

    assert result.status == "found"
    assert result.freshness is not None
    assert result.freshness.dataset_id == descriptor.dataset_id
    assert result.freshness.artifact_present is False
    assert result.freshness.status is SnapshotFreshnessStatus.MISSING
    assert result.freshness.reason is SnapshotFreshnessReason.NO_SNAPSHOT


def test_health_tool_module_does_not_import_connectors() -> None:
    project_root = Path(__file__).resolve().parents[2]
    health_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "health.py"
    tree = ast.parse(health_module.read_text(), filename=str(health_module))

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
