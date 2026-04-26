"""Unit tests for deterministic snapshot freshness evaluation."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
    has_defined_freshness_window,
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
    assert result.artifact_present is False
    assert result.snapshot_modified_at is None
    assert result.snapshot_age is None
    assert result.reference_time == reference_time


def test_existing_snapshot_is_classified_fresh_with_fixed_reference_time(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 1, 14, 6, 0, tzinfo=UTC)
    reference_time = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
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

    assert result.artifact_present is True
    assert result.status is SnapshotFreshnessStatus.FRESH
    assert result.reason is SnapshotFreshnessReason.WITHIN_EXPECTED_WINDOW
    assert result.snapshot_modified_at == snapshot_time
    assert result.snapshot_age == timedelta(hours=18)
    assert result.snapshot_id == store.snapshot_id("sama", "money-supply")


def test_existing_snapshot_freshness_exposes_snapshot_id_without_path(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path)
    _write_snapshot_with_mtime(
        store,
        dataset_id="money-supply",
        modified_at=datetime(2026, 1, 14, 6, 0, tzinfo=UTC),
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="money-supply",
        snapshot_store=store,
        reference_time=datetime(2026, 1, 15, 0, 0, tzinfo=UTC),
        update_frequency=UpdateFrequency.DAILY,
    )
    payload = result.model_dump(mode="json")

    assert payload["snapshot_id"] == store.snapshot_id("sama", "money-supply")
    assert "snapshot_path" not in payload
    assert str(tmp_path) not in json.dumps(payload)


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

    assert result.artifact_present is True
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

    assert result.artifact_present is True
    assert result.status is SnapshotFreshnessStatus.UNKNOWN
    assert result.reason is SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE
    assert result.snapshot_age == timedelta(days=31)


@pytest.mark.parametrize(
    "update_frequency",
    [
        UpdateFrequency.UNSPECIFIED,
        UpdateFrequency.AD_HOC,
    ],
)
def test_existing_snapshot_with_undefined_frequency_window_remains_unknown(
    tmp_path: Path,
    update_frequency: UpdateFrequency,
) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    reference_time = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
        store,
        dataset_id="repo-rate",
        modified_at=snapshot_time,
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="repo-rate",
        snapshot_store=store,
        reference_time=reference_time,
        update_frequency=update_frequency,
    )

    assert has_defined_freshness_window(update_frequency) is False
    assert result.artifact_present is True
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
