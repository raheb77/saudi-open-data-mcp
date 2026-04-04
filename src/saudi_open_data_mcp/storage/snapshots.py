"""Filesystem-backed raw payload snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TextIO
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
        self._write_atomic_text(
            path,
            json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True),
        )
        return path

    def read_snapshot(self, source: str, dataset_id: str) -> RawPayload:
        """Read a raw payload snapshot from local storage."""

        path = self.snapshot_path(source, dataset_id)
        if not path.is_file():
            raise FileNotFoundError(f"Snapshot not found: {path}")
        return RawPayload.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_atomic_text(self, path: Path, text: str) -> None:
        """Write text atomically by replacing the final path only after a full temp write."""

        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(temp_name)

        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                self._write_text(handle, text)
                handle.flush()
                os.fsync(handle.fileno())
            self._replace_atomic(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _write_text(handle: TextIO, text: str) -> None:
        """Write text to a temporary snapshot file handle."""

        handle.write(text)

    @staticmethod
    def _replace_atomic(temp_path: Path, final_path: Path) -> None:
        """Atomically replace the final snapshot path with a prepared temp file."""

        os.replace(temp_path, final_path)
