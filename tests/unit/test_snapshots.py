"""Unit tests for raw payload snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


def test_snapshot_path_is_deterministic(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)

    first = store.snapshot_path("sama", "balance-of-payments")
    second = store.snapshot_path("sama", "balance-of-payments")

    assert first == second
    assert first == tmp_path / "sama" / "balance-of-payments.json"


def test_write_then_read_snapshot_round_trip(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    payload = RawPayload(
        source="sama",
        dataset_id="money-supply",
        content={"series": [{"value": 1, "period": "2026-01"}]},
    )

    path = store.write_snapshot(payload)
    loaded = store.read_snapshot("sama", "money-supply")

    assert path == tmp_path / "sama" / "money-supply.json"
    assert loaded == payload


def test_snapshot_exists_reflects_storage_state(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    payload = RawPayload(source="sama", dataset_id="interest-rates", content={})

    assert not store.snapshot_exists("sama", "interest-rates")

    store.write_snapshot(payload)

    assert store.snapshot_exists("sama", "interest-rates")


def test_read_snapshot_raises_for_missing_snapshot(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)

    with pytest.raises(FileNotFoundError):
        store.read_snapshot("sama", "missing-dataset")


def test_snapshot_path_safely_encodes_identifiers(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)

    path = store.snapshot_path("../SAMA", "bal/../pay ments")
    relative = path.relative_to(tmp_path)

    assert relative.parts == ("%2E%2E%2FSAMA", "bal%2F%2E%2E%2Fpay%20ments.json")
    assert ".." not in relative.parts


def test_snapshot_path_rejects_empty_identifiers(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)

    with pytest.raises(ValueError):
        store.snapshot_path(" ", "dataset")

    with pytest.raises(ValueError):
        store.snapshot_path("sama", "")
