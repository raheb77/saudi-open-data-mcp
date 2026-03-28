"""Stable local CLI entry point for the current MCP server surface."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saudi_open_data_mcp.config import load_config
from saudi_open_data_mcp.server import create_server


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="saudi-open-data-mcp")
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument(
        "--check-imports",
        action="store_true",
        help="Instantiate the server and exit successfully if wiring imports cleanly.",
    )

    check_imports_parser = subparsers.add_parser(
        "check-imports",
        help="Instantiate the server and exit.",
    )
    check_imports_parser.set_defaults(command="check-imports")

    run_http_parser = subparsers.add_parser(
        "run-http",
        help="Run the current FastMCP app over local HTTP using configured defaults.",
    )
    run_http_parser.add_argument(
        "--host",
        default=None,
        help="Override the configured HTTP host.",
    )
    run_http_parser.add_argument(
        "--port",
        default=None,
        type=int,
        help="Override the configured HTTP port.",
    )
    run_http_parser.add_argument(
        "--log-level",
        default=None,
        help="Override the configured log level.",
    )
    run_http_parser.set_defaults(command="run-http")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check_imports or args.command in {None, "check-imports"}:
        create_server()
        print("saudi-open-data-mcp server wiring is importable.")
        return 0

    if args.command == "run-http":
        config = load_config()
        app = create_server(config)
        host = args.host or config.transport.http_host
        port = args.port or config.transport.http_port
        log_level = args.log_level or config.log_level
        asyncio.run(
            app.run_http_async(
                transport="streamable-http",
                host=host,
                port=port,
                log_level=log_level,
            )
        )
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
