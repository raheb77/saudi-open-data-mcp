#!/usr/bin/env python3
"""Bootstrap the registry scaffold."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    from saudi_open_data_mcp.registry.bootstrap import bootstrap_registry
    from saudi_open_data_mcp.registry.repository import RegistryRepository

    repository = RegistryRepository(Path(".local/registry.sqlite"))
    bootstrap_registry(repository)
    print("Registry scaffold checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
