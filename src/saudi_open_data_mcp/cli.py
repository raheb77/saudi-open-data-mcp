"""Stable local CLI entry point for the current MCP server surface."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saudi_open_data_mcp.config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    load_config,
)
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.server import create_server


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="python src/saudi_open_data_mcp/cli.py")
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument(
        "--check-startup",
        action="store_true",
        help=(
            "Construct the server, bootstrap the registry if needed, "
            "and exit successfully if startup wiring validates."
        ),
    )

    check_startup_parser = subparsers.add_parser(
        "check-startup",
        help="Construct the server, bootstrap the registry if needed, and exit.",
    )
    check_startup_parser.set_defaults(command="check-startup")

    run_stdio_parser = subparsers.add_parser(
        "run-stdio",
        help="Run the current FastMCP app over stdio.",
    )
    run_stdio_parser.add_argument(
        "--log-level",
        default=None,
        help="Override the configured log level.",
    )
    run_stdio_parser.set_defaults(command="run-stdio")

    run_http_parser = subparsers.add_parser(
        "run-http",
        help=(
            "Run the current FastMCP app over streamable HTTP using configured "
            "defaults and HTTP bearer auth."
        ),
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

    if args.check_startup or args.command in {None, "check-startup"}:
        config = _load_config_or_exit(parser)
        _create_server_or_exit(parser, config)
        print("saudi-open-data-mcp startup wiring and registry bootstrap are valid.")
        return 0

    if args.command == "run-http":
        config = _load_config_or_exit(parser)
        try:
            middleware = build_http_auth_middleware(
                config.transport.http_auth_token,
                config.transport.http_auth_capabilities,
            )
        except ValueError as exc:
            parser.error(str(exc))
        app = _create_server_or_exit(parser, config)
        host = args.host or config.transport.http_host
        port = args.port or config.transport.http_port
        log_level = args.log_level or config.log_level
        asyncio.run(
            app.run_http_async(
                transport="streamable-http",
                host=host,
                port=port,
                log_level=log_level,
                middleware=middleware,
            )
        )
        return 0

    if args.command == "run-stdio":
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        log_level = args.log_level or config.log_level
        asyncio.run(
            app.run_stdio_async(
                log_level=log_level,
            )
        )
        return 0

    parser.error("unsupported command")
    return 2


def _load_config_or_exit(parser: argparse.ArgumentParser):
    """Load config or exit with a concise operator-facing parser error."""

    try:
        return load_config()
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))


def _create_server_or_exit(
    parser: argparse.ArgumentParser,
    config: RuntimeConfig | None = None,
):
    """Create the server or exit with a concise operator-facing parser error."""

    try:
        return create_server(config)
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
