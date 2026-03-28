"""Unit tests for deterministic snapshot freshness evaluation."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


def test_missing_snapshot_returns_explicit_missing_freshness_result(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    reference_time = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="missing-dataset",
        snapshot_store=store,
        reference_time=reference_time,
        update_frequency=UpdateFrequency.MONTHLY,
    )

    assert result.status is SnapshotFreshnessStatus.MISSING
    assert result.reason is SnapshotFreshnessReason.NO_SNAPSHOT
    assert result.snapshot_modified_at is None
    assert result.snapshot_age is None
    assert result.reference_time == reference_time


def test_existing_snapshot_is_classified_fresh_with_fixed_reference_time(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 1, 14, 6, 0, tzinfo=UTC)
    reference_time = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    snapshot_path = _write_snapshot_with_mtime(
        store,
        dataset_id="money-supply",
        modified_at=snapshot_time,
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="money-supply",
        snapshot_store=tmp_path,
        reference_time=reference_time,
        update_frequency=UpdateFrequency.DAILY,
    )

    assert result.snapshot_path == snapshot_path
    assert result.status is SnapshotFreshnessStatus.FRESH
    assert result.reason is SnapshotFreshnessReason.WITHIN_EXPECTED_WINDOW
    assert result.snapshot_modified_at == snapshot_time
    assert result.snapshot_age == timedelta(hours=18)


def test_existing_snapshot_is_classified_stale_when_age_exceeds_frequency_window(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    reference_time = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
        store,
        dataset_id="interest-rates",
        modified_at=snapshot_time,
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="interest-rates",
        snapshot_store=store,
        reference_time=reference_time,
        update_frequency=UpdateFrequency.WEEKLY,
    )

    assert result.status is SnapshotFreshnessStatus.STALE
    assert result.reason is SnapshotFreshnessReason.EXCEEDED_EXPECTED_WINDOW
    assert result.snapshot_age == timedelta(days=9)


def test_existing_snapshot_without_frequency_remains_explicitly_unknown(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    reference_time = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
        store,
        dataset_id="balance-of-payments",
        modified_at=snapshot_time,
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="balance-of-payments",
        snapshot_store=store,
        reference_time=reference_time,
        update_frequency=None,
    )

    assert result.status is SnapshotFreshnessStatus.UNKNOWN
    assert result.reason is SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE
    assert result.snapshot_age == timedelta(days=31)


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    dataset_id: str,
    modified_at: datetime,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=dataset_id,
        content={"body": {"rows": []}},
    )
    path = store.write_snapshot(payload)
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
