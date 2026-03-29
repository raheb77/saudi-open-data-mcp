"""Project-local editable install bootstrap for the synced `.venv`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


def _editable_repo_root(site_packages: Path) -> Path | None:
    """Return the editable project root recorded in dist-info metadata."""

    for dist_info in sorted(site_packages.glob("saudi_open_data_mcp-*.dist-info")):
        direct_url_path = dist_info / "direct_url.json"
        if not direct_url_path.is_file():
            continue

        try:
            direct_url = json.loads(direct_url_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if not direct_url.get("dir_info", {}).get("editable"):
            continue

        url = direct_url.get("url")
        if not isinstance(url, str):
            continue

        parsed = urlparse(url)
        if parsed.scheme != "file":
            continue

        path = url2pathname(parsed.path)
        if parsed.netloc:
            path = f"//{parsed.netloc}{path}"

        repo_root = Path(path)
        if repo_root.is_dir():
            return repo_root

    return None


def _ensure_repo_src_on_path() -> None:
    """Add the editable project `src/` directory to sys.path when needed."""

    site_packages = Path(__file__).resolve().parent
    repo_root = _editable_repo_root(site_packages)
    if repo_root is None:
        return

    src_path = repo_root / "src"
    if not src_path.is_dir():
        return

    src_path_str = str(src_path)
    if src_path_str not in sys.path:
        sys.path.append(src_path_str)


_ensure_repo_src_on_path()
