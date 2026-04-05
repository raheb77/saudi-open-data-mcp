"""Stable local CLI entry point for the current MCP server surface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saudi_open_data_mcp.config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    load_config,
)
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.security.http_readiness import build_http_readiness_middleware
from saudi_open_data_mcp.server import create_server

JSON_FORMAT = "json"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        prog="python src/saudi_open_data_mcp/cli.py",
        description=(
            "Thin non-interactive CLI over the current MCP core. Data commands emit "
            "JSON to stdout by default."
        ),
    )
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

    list_parser = subparsers.add_parser(
        "list",
        help="List bootstrapped datasets using the current registry-backed search path.",
    )
    list_parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Optional substring search query. Empty means list all datasets.",
    )
    _add_output_arguments(list_parser)
    list_parser.set_defaults(command="list")

    query_parser = subparsers.add_parser(
        "query",
        help="Run the current local-only query_dataset path for one dataset_id.",
    )
    _add_dataset_query_arguments(query_parser)
    _add_output_arguments(query_parser)
    query_parser.set_defaults(command="query")

    preview_parser = subparsers.add_parser(
        "preview",
        help="Run the current preview_dataset path for one dataset_id.",
    )
    preview_parser.add_argument("dataset_id", help="Exact canonical dataset_id.")
    _add_output_arguments(preview_parser)
    preview_parser.set_defaults(command="preview")

    export_parser = subparsers.add_parser(
        "export",
        help=(
            "Export the exact structured output of the current local-only query_dataset "
            "path for one dataset_id."
        ),
    )
    _add_dataset_query_arguments(export_parser)
    _add_output_arguments(export_parser)
    export_parser.set_defaults(command="export")

    health_parser = subparsers.add_parser(
        "health",
        help="Run the current dataset_health lookup for one dataset_id.",
    )
    health_parser.add_argument("dataset_id", help="Exact canonical dataset_id.")
    _add_output_arguments(health_parser)
    health_parser.set_defaults(command="health")

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Run the current materialize_hot_set path.",
    )
    refresh_parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Include the current optional Tier B hot-set dataset ids.",
    )
    _add_output_arguments(refresh_parser)
    refresh_parser.set_defaults(command="refresh")

    config_parser = subparsers.add_parser(
        "config",
        help="Print the current runtime configuration with auth token presence redacted.",
    )
    _add_output_arguments(config_parser)
    config_parser.set_defaults(command="config")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {
        "config",
        "list",
        "query",
        "export",
        "preview",
        "health",
        "refresh",
    }:
        _validate_output_arguments_or_exit(
            parser,
            output_format=args.format,
            output_path=args.output,
            quiet=args.quiet,
        )

    if args.check_startup or args.command in {None, "check-startup"}:
        config = _load_config_or_exit(parser)
        _create_server_or_exit(parser, config)
        print("saudi-open-data-mcp startup wiring and registry bootstrap are valid.")
        return 0

    if args.command == "run-http":
        config = _load_config_or_exit(parser)
        try:
            middleware = build_http_readiness_middleware(
                config.app_name
            ) + build_http_auth_middleware(
                config.transport.http_auth_token,
                config.transport.http_auth_capabilities,
                config.transport.http_auth_role,
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

    if args.command == "config":
        config = _load_config_or_exit(parser)
        _write_payload_or_exit(
            parser,
            payload=_config_payload(config),
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    if args.command == "list":
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="search_datasets",
                arguments={"query": args.query},
            )
        )
        _write_payload_or_exit(
            parser,
            payload=payload,
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    if args.command in {"query", "export"}:
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        filters = _parse_filter_arguments_or_exit(parser, args.filter)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="query_dataset",
                arguments={
                    "dataset_id": args.dataset_id,
                    "filters": filters or None,
                    "limit": args.limit,
                },
            )
        )
        _write_payload_or_exit(
            parser,
            payload=payload,
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    if args.command == "preview":
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="preview_dataset",
                arguments={"dataset_id": args.dataset_id},
            )
        )
        _write_payload_or_exit(
            parser,
            payload=payload,
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    if args.command == "health":
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="dataset_health",
                arguments={"dataset_id": args.dataset_id},
            )
        )
        _write_payload_or_exit(
            parser,
            payload=payload,
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    if args.command == "refresh":
        config = _load_config_or_exit(parser)
        app = _create_server_or_exit(parser, config)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="materialize_hot_set",
                arguments={"include_optional": args.include_optional},
            )
        )
        _write_payload_or_exit(
            parser,
            payload=payload,
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0

    parser.error("unsupported command")
    return 2


def _add_dataset_query_arguments(subparser: argparse.ArgumentParser) -> None:
    """Add the shared dataset query argument set used by query/export commands."""

    subparser.add_argument("dataset_id", help="Exact canonical dataset_id.")
    subparser.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Exact-match query filter. Values are parsed as JSON scalars when possible; "
            "otherwise they remain strings."
        ),
    )
    subparser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of matching records to return.",
    )


def _add_output_arguments(subparser: argparse.ArgumentParser) -> None:
    """Add the current machine-friendly output arguments for local CLI commands."""

    subparser.add_argument(
        "--format",
        default=JSON_FORMAT,
        metavar="FORMAT",
        help="Output format. Only json is currently supported.",
    )
    subparser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the rendered command output to this file instead of stdout.",
    )
    subparser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the confirmation line after a successful --output write.",
    )


def _validate_output_arguments_or_exit(
    parser: argparse.ArgumentParser,
    *,
    output_format: str,
    output_path: Path | None,
    quiet: bool,
) -> None:
    """Validate the shared output arguments for local JSON-emitting commands."""

    if output_format != JSON_FORMAT:
        parser.error(
            f"unsupported --format '{output_format}'; only {JSON_FORMAT} is currently supported"
        )

    if quiet and output_path is None:
        parser.error("--quiet requires --output")


def _parse_filter_arguments_or_exit(
    parser: argparse.ArgumentParser,
    filter_arguments: Sequence[str],
) -> dict[str, str | int | float | bool | None]:
    """Parse repeated KEY=VALUE filters or exit with a concise parser error."""

    try:
        return _parse_filter_arguments(filter_arguments)
    except ValueError as exc:
        parser.error(str(exc))


def _parse_filter_arguments(
    filter_arguments: Sequence[str],
) -> dict[str, str | int | float | bool | None]:
    """Parse repeated exact-match filter arguments into query-compatible scalars."""

    parsed_filters: dict[str, str | int | float | bool | None] = {}
    for filter_argument in filter_arguments:
        if "=" not in filter_argument:
            raise ValueError("filters must use KEY=VALUE syntax")

        key, raw_value = filter_argument.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("filter keys must not be empty")
        parsed_filters[normalized_key] = _parse_filter_value(raw_value)

    return parsed_filters


def _parse_filter_value(raw_value: str) -> str | int | float | bool | None:
    """Parse a CLI filter value as a scalar JSON literal when possible."""

    if raw_value == "":
        return ""

    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value

    if isinstance(parsed_value, (str, int, float, bool)) or parsed_value is None:
        return parsed_value

    raise ValueError("query filter values must be scalar JSON literals or plain strings")


async def _invoke_tool_payload(
    app: Any,
    *,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Invoke one already-registered MCP tool and return its structured payload."""

    tools = await app.get_tools()
    tool_result = await tools[tool_name].run(arguments)
    return tool_result.structured_content


def _config_payload(config: RuntimeConfig) -> dict[str, Any]:
    """Return a redacted JSON-friendly config payload for local operator use."""

    payload = config.model_dump(
        mode="json",
        exclude={"transport": {"http_auth_token"}},
    )
    transport_payload = dict(payload["transport"])
    transport_payload["http_auth_capabilities"] = sorted(
        capability.value for capability in config.transport.http_auth_capabilities
    )
    transport_payload["http_auth_token_configured"] = (
        config.transport.http_auth_token is not None
    )
    payload["transport"] = transport_payload
    return payload


def _write_payload_or_exit(
    parser: argparse.ArgumentParser,
    *,
    payload: dict[str, Any],
    output_path: Path | None,
    quiet: bool,
    output_format: str,
) -> None:
    """Render one JSON payload and write it to stdout or a file."""

    try:
        rendered = _render_payload(payload, output_format=output_format)
    except ValueError as exc:
        parser.error(str(exc))

    if output_path is None:
        print(rendered)
        return

    try:
        output_path.write_text(rendered + "\n", encoding="utf-8")
    except OSError as exc:
        parser.error(f"unable to write output file '{output_path}': {exc}")

    if not quiet:
        print(f"Wrote {output_path}")


def _render_payload(
    payload: dict[str, Any],
    *,
    output_format: str,
) -> str:
    """Render one command payload using the currently supported output format."""

    if output_format != JSON_FORMAT:
        raise ValueError(
            f"unsupported --format '{output_format}'; only {JSON_FORMAT} is currently supported"
        )
    return json.dumps(payload, indent=2, sort_keys=True)


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
