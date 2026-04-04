"""Unit tests for raw payload snapshots."""

from __future__ import annotations

import json
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
    assert sorted(item.name for item in path.parent.iterdir()) == ["money-supply.json"]


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


def test_write_snapshot_failure_does_not_leave_partial_final_file(tmp_path: Path) -> None:
    class WriteFailingSnapshotStore(SnapshotStore):
        @staticmethod
        def _write_text(handle, text: str) -> None:
            handle.write('{"partial": true')
            raise OSError("write failed before commit")

    store = WriteFailingSnapshotStore(tmp_path)
    payload = RawPayload(source="sama", dataset_id="money-supply", content={"value": 1})
    final_path = store.snapshot_path("sama", "money-supply")

    with pytest.raises(OSError, match="write failed before commit"):
        store.write_snapshot(payload)

    assert not final_path.exists()
    assert list(final_path.parent.glob("*.tmp")) == []


def test_existing_snapshot_remains_intact_when_replace_fails_before_commit(
    tmp_path: Path,
) -> None:
    base_store = SnapshotStore(tmp_path)
    original_payload = RawPayload(
        source="sama",
        dataset_id="money-supply",
        content={"value": 1},
    )
    updated_payload = RawPayload(
        source="sama",
        dataset_id="money-supply",
        content={"value": 2},
    )
    final_path = base_store.write_snapshot(original_payload)

    class ReplaceFailingSnapshotStore(SnapshotStore):
        @staticmethod
        def _replace_atomic(temp_path: Path, final_path: Path) -> None:
            raise OSError("replace failed before commit")

    failing_store = ReplaceFailingSnapshotStore(tmp_path)

    with pytest.raises(OSError, match="replace failed before commit"):
        failing_store.write_snapshot(updated_payload)

    assert final_path.read_text(encoding="utf-8") == json.dumps(
        original_payload.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    assert base_store.read_snapshot("sama", "money-supply") == original_payload
    assert list(final_path.parent.glob("*.tmp")) == []


def test_existing_snapshot_remains_intact_when_write_fails_before_commit(
    tmp_path: Path,
) -> None:
    base_store = SnapshotStore(tmp_path)
    original_payload = RawPayload(
        source="sama",
        dataset_id="money-supply",
        content={"value": 1},
    )
    final_path = base_store.write_snapshot(original_payload)

    class WriteFailingSnapshotStore(SnapshotStore):
        @staticmethod
        def _write_text(handle, text: str) -> None:
            handle.write('{"partial": true')
            raise OSError("write failed before commit")

    failing_store = WriteFailingSnapshotStore(tmp_path)

    with pytest.raises(OSError, match="write failed before commit"):
        failing_store.write_snapshot(
            RawPayload(
                source="sama",
                dataset_id="money-supply",
                content={"value": 2},
            )
        )

    assert final_path.read_text(encoding="utf-8") == json.dumps(
        original_payload.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    assert base_store.read_snapshot("sama", "money-supply") == original_payload
    assert list(final_path.parent.glob("*.tmp")) == []
