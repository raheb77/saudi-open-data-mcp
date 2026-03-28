"""CLI entry point for the scaffold."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .server import create_server


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="saudi-open-data-mcp")
    parser.add_argument(
        "--check-imports",
        action="store_true",
        help="Instantiate the scaffold server and exit.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    parser.parse_args(argv)
    create_server()
    print("saudi-open-data-mcp scaffold is importable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
