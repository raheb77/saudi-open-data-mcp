"""Module entry point for `python -m saudi_open_data_mcp`."""

from __future__ import annotations

from collections.abc import Sequence

from .cli import main as cli_main


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate module execution to the stable CLI entry point."""

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
