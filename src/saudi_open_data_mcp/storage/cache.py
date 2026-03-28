"""Cache scaffolding."""

from __future__ import annotations

from pathlib import Path


class CacheStore:
    """Placeholder file cache helper."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def key_path(self, namespace: str, key: str) -> Path:
        """Return the deterministic cache path for a key."""

        return self.root / namespace / f"{key}.json"
