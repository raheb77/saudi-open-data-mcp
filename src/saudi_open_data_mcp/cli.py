"""Stable local CLI entry point for the current MCP server surface."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saudi_open_data_mcp.config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    load_config,
)
from saudi_open_data_mcp.observability.upstream_canary import (
    UpstreamCanaryStatus,
    run_upstream_canary,
)
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.security.http_readiness import build_http_readiness_middleware
from saudi_open_data_mcp.server import create_server
from saudi_open_data_mcp.tools.export_artifacts import (
    ExportArtifactFormat,
    render_query_result_excel_artifact,
    render_query_result_pdf_artifact,
)
from saudi_open_data_mcp.tools.health import DatasetHealthLookupResult
from saudi_open_data_mcp.tools.query import DatasetQueryResult

JSON_FORMAT = "json"
EXCEL_FORMAT = ExportArtifactFormat.EXCEL.value
PDF_FORMAT = ExportArtifactFormat.PDF.value
DOTENV_FILENAME = ".env"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        prog="saudi-open-data-mcp",
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
            "Export the current governed query_dataset result for one dataset_id as "
            "json, excel, or pdf."
        ),
    )
    _add_dataset_query_arguments(export_parser)
    _add_output_arguments(
        export_parser,
        allowed_formats=(JSON_FORMAT, EXCEL_FORMAT, PDF_FORMAT),
    )
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

    upstream_canary_parser = subparsers.add_parser(
        "upstream-canary",
        help=(
            "Run the curated live upstream canary over approved source routes and "
            "normalization contracts."
        ),
    )
    upstream_canary_parser.add_argument(
        "--dataset-id",
        action="append",
        dest="dataset_ids",
        default=None,
        help="Optional curated canary dataset_id. Repeat to limit the run.",
    )
    _add_output_arguments(upstream_canary_parser)
    upstream_canary_parser.set_defaults(command="upstream-canary")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {
        "config",
        "list",
        "query",
        "preview",
        "health",
        "refresh",
        "upstream-canary",
    }:
        _validate_output_arguments_or_exit(
            parser,
            output_format=args.format,
            output_path=args.output,
            quiet=args.quiet,
            allowed_formats=(JSON_FORMAT,),
        )

    if args.command == "export":
        _validate_output_arguments_or_exit(
            parser,
            output_format=args.format,
            output_path=args.output,
            quiet=args.quiet,
            allowed_formats=(JSON_FORMAT, EXCEL_FORMAT, PDF_FORMAT),
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
                # Keep the MCP session stateful, but emit finite JSON responses for
                # POST requests so browser/dashboard clients receive a usable
                # initialize/tools/resources result without waiting on an SSE body
                # to terminate.
                json_response=True,
                stateless_http=False,
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
        dataset_id = _resolve_dataset_id_argument_or_exit(
            parser,
            positional_dataset_id=args.dataset_id,
            option_dataset_id=args.dataset_id_option,
        )
        filters = _parse_filter_arguments_or_exit(parser, args.filter)
        payload = asyncio.run(
            _invoke_tool_payload(
                app,
                tool_name="query_dataset",
                arguments={
                    "dataset_id": dataset_id,
                    "filters": filters or None,
                    "limit": args.limit,
                },
            )
        )

        if args.command == "export" and args.format in {EXCEL_FORMAT, PDF_FORMAT}:
            health_payload = asyncio.run(
                _invoke_tool_payload(
                    app,
                    tool_name="dataset_health",
                    arguments={"dataset_id": dataset_id},
                )
            )
            _write_query_export_artifact_or_exit(
                parser,
                query_payload=payload,
                health_payload=health_payload,
                output_path=args.output,
                quiet=args.quiet,
                output_format=args.format,
            )
            return 0

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

    if args.command == "upstream-canary":
        config = _load_config_or_exit(parser)
        summary = asyncio.run(
            run_upstream_canary(
                config,
                dataset_ids=(
                    tuple(args.dataset_ids)
                    if args.dataset_ids is not None
                    else None
                ),
            )
        )
        _write_payload_or_exit(
            parser,
            payload=summary.model_dump(mode="json"),
            output_path=args.output,
            quiet=args.quiet,
            output_format=args.format,
        )
        return 0 if summary.status is UpstreamCanaryStatus.PASSED else 1

    parser.error("unsupported command")
    return 2


def _add_dataset_query_arguments(subparser: argparse.ArgumentParser) -> None:
    """Add the shared dataset query argument set used by query/export commands."""

    subparser.add_argument("dataset_id", nargs="?", help="Exact canonical dataset_id.")
    subparser.add_argument(
        "--dataset-id",
        dest="dataset_id_option",
        default=None,
        help="Exact canonical dataset_id.",
    )
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


def _add_output_arguments(
    subparser: argparse.ArgumentParser,
    *,
    allowed_formats: Sequence[str] = (JSON_FORMAT,),
) -> None:
    """Add the current machine-friendly output arguments for local CLI commands."""

    subparser.add_argument(
        "--format",
        default=JSON_FORMAT,
        metavar="FORMAT",
        help=_output_format_help(allowed_formats),
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
    allowed_formats: Sequence[str],
) -> None:
    """Validate the shared output arguments for local JSON-emitting commands."""

    if output_format not in allowed_formats:
        parser.error(_unsupported_format_message(output_format, allowed_formats))

    if quiet and output_path is None:
        parser.error("--quiet requires --output")

    if output_format in {EXCEL_FORMAT, PDF_FORMAT} and output_path is None:
        parser.error(f"--output is required when --format is {output_format}")


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


def _resolve_dataset_id_argument_or_exit(
    parser: argparse.ArgumentParser,
    *,
    positional_dataset_id: str | None,
    option_dataset_id: str | None,
) -> str:
    """Resolve the shared dataset-id arguments for query/export commands."""

    if positional_dataset_id and option_dataset_id:
        parser.error("provide either dataset_id or --dataset-id, not both")

    dataset_id = option_dataset_id or positional_dataset_id
    if dataset_id is None:
        parser.error("dataset_id is required")

    return dataset_id


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


def _write_query_export_artifact_or_exit(
    parser: argparse.ArgumentParser,
    *,
    query_payload: dict[str, Any],
    health_payload: dict[str, Any],
    output_path: Path | None,
    quiet: bool,
    output_format: str,
) -> None:
    """Render one governed query export artifact and write it to disk."""

    if output_path is None:
        parser.error(f"--output is required when --format is {output_format}")

    try:
        query_result = DatasetQueryResult.model_validate(query_payload)
        health_result = DatasetHealthLookupResult.model_validate(health_payload)
        freshness_status = (
            health_result.freshness.status.value
            if health_result.freshness is not None
            else None
        )
        exported_at = datetime.now(UTC)
        if output_format == EXCEL_FORMAT:
            rendered = render_query_result_excel_artifact(
                query_result,
                freshness_status=freshness_status,
                exported_at=exported_at,
            )
        elif output_format == PDF_FORMAT:
            rendered = render_query_result_pdf_artifact(
                query_result,
                freshness_status=freshness_status,
                exported_at=exported_at,
            )
        else:
            parser.error(
                _unsupported_format_message(
                    output_format,
                    (JSON_FORMAT, EXCEL_FORMAT, PDF_FORMAT),
                )
            )
            return
    except ValueError as exc:
        parser.error(str(exc))

    try:
        output_path.write_bytes(rendered)
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
        raise ValueError(_unsupported_format_message(output_format, (JSON_FORMAT,)))
    return json.dumps(payload, indent=2, sort_keys=True)


def _output_format_help(allowed_formats: Sequence[str]) -> str:
    """Build the parser help text for one command's output formats."""

    if tuple(allowed_formats) == (JSON_FORMAT,):
        return "Output format. Only json is currently supported."
    return "Output format. Supported: " + ", ".join(allowed_formats) + "."


def _unsupported_format_message(
    output_format: str,
    allowed_formats: Sequence[str],
) -> str:
    """Build one consistent unsupported-format parser message."""

    if tuple(allowed_formats) == (JSON_FORMAT,):
        return (
            f"unsupported --format '{output_format}'; only {JSON_FORMAT} is currently supported"
        )
    return (
        f"unsupported --format '{output_format}'; supported formats: "
        + ", ".join(allowed_formats)
    )


def _load_config_or_exit(parser: argparse.ArgumentParser):
    """Load config or exit with a concise operator-facing parser error."""

    try:
        with _dotenv_environment():
            return load_config()
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))


@contextmanager
def _dotenv_environment():
    """Temporarily layer a local .env file onto the current process environment."""

    dotenv_values = _read_dotenv_file(Path.cwd() / DOTENV_FILENAME)
    applied_values = {
        key: value for key, value in dotenv_values.items() if key not in os.environ
    }
    os.environ.update(applied_values)
    try:
        yield
    finally:
        for key in applied_values:
            os.environ.pop(key, None)


def _read_dotenv_file(path: Path) -> dict[str, str]:
    """Read one simple KEY=VALUE .env file without overriding real environment values."""

    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        key, separator, value = raw_line.partition("=")
        if separator != "=":
            raise RuntimeConfigurationError(
                f"invalid {path.name} entry at line {line_number}; expected KEY=VALUE"
            )

        normalized_key = key.strip()
        if not normalized_key:
            raise RuntimeConfigurationError(
                f"invalid {path.name} entry at line {line_number}; missing variable name"
            )

        values[normalized_key] = _parse_dotenv_value(
            value,
            path=path,
            line_number=line_number,
        )

    return values


def _parse_dotenv_value(
    raw_value: str,
    *,
    path: Path,
    line_number: int,
) -> str:
    """Parse one dotenv value, supporting plain or quoted strings."""

    normalized = raw_value.strip()
    if not normalized:
        return ""

    if normalized[0] not in {'"', "'"}:
        return normalized

    quote = normalized[0]
    if len(normalized) < 2 or normalized[-1] != quote:
        raise RuntimeConfigurationError(
            f"invalid {path.name} entry at line {line_number}; unmatched quoted value"
        )
    return normalized[1:-1]


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
