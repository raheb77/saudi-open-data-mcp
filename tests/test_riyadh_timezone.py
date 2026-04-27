"""Asia/Riyadh freshness-calendar tests."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


def test_freshness_window_riyadh_timezone_handles_friday_night_snapshot(
    tmp_path: Path,
) -> None:
    riyadh = ZoneInfo("Asia/Riyadh")
    store = SnapshotStore(tmp_path)
    snapshot_time = datetime(2026, 5, 1, 23, 0, tzinfo=riyadh)
    reference_time = datetime(2026, 5, 3, 0, 30, tzinfo=riyadh)
    _write_snapshot_with_mtime(
        store,
        dataset_id="riyadh-business-calendar",
        modified_at=snapshot_time,
    )

    result = evaluate_snapshot_freshness(
        source="sama",
        dataset_id="riyadh-business-calendar",
        snapshot_store=store,
        reference_time=reference_time,
        update_frequency=UpdateFrequency.DAILY,
    )

    assert snapshot_time.weekday() == 4
    assert reference_time.weekday() == 6
    assert result.snapshot_age == timedelta(days=1, hours=1, minutes=30)
    assert result.status is SnapshotFreshnessStatus.FRESH
    assert result.reason is SnapshotFreshnessReason.WITHIN_EXPECTED_WINDOW


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
    timestamp = modified_at.astimezone(UTC).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
