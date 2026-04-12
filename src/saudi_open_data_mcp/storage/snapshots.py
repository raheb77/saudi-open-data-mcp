"""Filesystem-backed raw payload snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TextIO
from urllib.parse import quote

from ..connectors.base import RawPayload, SnapshotMetadata

CURRENT_SNAPSHOT_STORAGE_SCHEMA_VERSION = 1
LEGACY_SNAPSHOT_STORAGE_SCHEMA_VERSION = 0

SAMA_EXCHANGE_RATES_CURRENT_BUNDLE_FORMAT_ID = (
    "sama_exchange_rates_current_page_bundle"
)
SAMA_EXCHANGE_RATES_CURRENT_LEGACY_HTML_FORMAT_ID = (
    "sama_exchange_rates_current_legacy_html_page"
)
SAMA_EXCHANGE_RATES_CURRENT_FORMAT_VERSION = 1
SAMA_EXCHANGE_RATES_CURRENT_LOCATOR = "/en-US/FinExc/Pages/Currency.aspx"


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
        payload_for_storage = with_snapshot_metadata(payload)
        self._write_atomic_text(
            path,
            json.dumps(payload_for_storage.model_dump(mode="json"), indent=2, sort_keys=True),
        )
        return path

    def read_snapshot(self, source: str, dataset_id: str) -> RawPayload:
        """Read a raw payload snapshot from local storage."""

        path = self.snapshot_path(source, dataset_id)
        if not path.is_file():
            raise FileNotFoundError(f"Snapshot not found: {path}")
        payload = RawPayload.model_validate_json(path.read_text(encoding="utf-8"))
        return with_snapshot_metadata(payload, assume_legacy_when_missing=True)

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


def with_snapshot_metadata(
    payload: RawPayload,
    *,
    assume_legacy_when_missing: bool = False,
) -> RawPayload:
    """Attach deterministic snapshot metadata without mutating the original payload."""

    existing = payload.snapshot_metadata
    inferred_format_id, inferred_format_version = infer_snapshot_format(payload)

    if existing is None:
        storage_schema_version = (
            LEGACY_SNAPSHOT_STORAGE_SCHEMA_VERSION
            if assume_legacy_when_missing
            else CURRENT_SNAPSHOT_STORAGE_SCHEMA_VERSION
        )
        raw_format_id = inferred_format_id
        raw_format_version = inferred_format_version
    else:
        storage_schema_version = existing.storage_schema_version
        raw_format_id = existing.raw_format_id or inferred_format_id
        raw_format_version = existing.raw_format_version or inferred_format_version

    metadata = SnapshotMetadata(
        storage_schema_version=storage_schema_version,
        raw_format_id=raw_format_id,
        raw_format_version=raw_format_version,
    )
    return payload.model_copy(update={"snapshot_metadata": metadata})


def infer_snapshot_format(payload: RawPayload) -> tuple[str | None, int | None]:
    """Infer a narrow raw-format identity for snapshots with known schema drift risk."""

    if (
        payload.source == "sama"
        and payload.dataset_id == SAMA_EXCHANGE_RATES_CURRENT_LOCATOR
    ):
        body = payload.content.get("body")
        if _looks_like_exchange_rates_current_bundle(body):
            return (
                SAMA_EXCHANGE_RATES_CURRENT_BUNDLE_FORMAT_ID,
                SAMA_EXCHANGE_RATES_CURRENT_FORMAT_VERSION,
            )
        if isinstance(body, str):
            return (
                SAMA_EXCHANGE_RATES_CURRENT_LEGACY_HTML_FORMAT_ID,
                SAMA_EXCHANGE_RATES_CURRENT_FORMAT_VERSION,
            )

    return (None, None)


def _looks_like_exchange_rates_current_bundle(body: object) -> bool:
    """Return whether a body matches the current exchange-rates bundle contract."""

    if not isinstance(body, dict):
        return False

    pages = body.get("pages")
    if not isinstance(pages, list) or not pages:
        return False

    if not isinstance(body.get("results_page_url"), str):
        return False
    if not isinstance(body.get("current_date_text"), str):
        return False
    if not isinstance(body.get("total_results_count"), int):
        return False

    return all(
        isinstance(page, dict)
        and isinstance(page.get("page_number"), int)
        and isinstance(page.get("page_url"), str)
        and isinstance(page.get("body"), str)
        for page in pages
    )
