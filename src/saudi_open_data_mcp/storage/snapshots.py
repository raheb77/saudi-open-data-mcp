"""Filesystem-backed raw payload snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from ..connectors.base import RawPayload


class SnapshotStore:
    """Store and read raw payload snapshots from the local filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _path_component(value: str) -> str:
        """Encode a source or dataset identifier into a safe path component."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("snapshot path components must not be empty")
        if normalized in {".", ".."}:
            raise ValueError("snapshot path components must not be '.' or '..'")
        return quote(normalized, safe="-_").replace(".", "%2E")

    def snapshot_path(self, source: str, dataset_id: str) -> Path:
        """Return the deterministic snapshot path for a dataset."""

        source_component = self._path_component(source)
        dataset_component = self._path_component(dataset_id)
        return self.root / source_component / f"{dataset_component}.json"

    def snapshot_exists(self, source: str, dataset_id: str) -> bool:
        """Return whether a snapshot exists for the given source and dataset."""

        return self.snapshot_path(source, dataset_id).is_file()

    def write_snapshot(self, payload: RawPayload) -> Path:
        """Write a raw payload snapshot to local storage."""

        path = self.snapshot_path(payload.source, payload.dataset_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def read_snapshot(self, source: str, dataset_id: str) -> RawPayload:
        """Read a raw payload snapshot from local storage."""

        path = self.snapshot_path(source, dataset_id)
        if not path.is_file():
            raise FileNotFoundError(f"Snapshot not found: {path}")
        return RawPayload.model_validate_json(path.read_text(encoding="utf-8"))
