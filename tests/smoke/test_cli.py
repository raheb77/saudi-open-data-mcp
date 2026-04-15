"""Smoke tests for the scaffold CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import SecretStr

from saudi_open_data_mcp import cli as cli_module
from saudi_open_data_mcp.config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    TransportConfig,
)
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.bootstrap import bootstrap_registry
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.http_auth import (
    HTTPAuthCapability,
    HTTPAuthRole,
    HTTPBearerAuthMiddleware,
)
from saudi_open_data_mcp.security.http_readiness import (
    HTTP_READINESS_PATH,
    HTTPReadinessMiddleware,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

DATA_GOV_SA_DATASET_ID = "data-gov-sa-census-marital-status"
DATA_GOV_SA_SOURCE_LOCATOR = (
    "/ar/datasets/view/104380ce-60b6-46bc-ba0a-6d5e10ac46cb/"
    "preview/parsed/Census%20Marital%20Status%20CSV.json"
)


def test_cli_check_startup_mode_returns_success() -> None:
    assert cli_module.main(["--check-startup"]) == 0


def test_cli_check_startup_subcommand_returns_success() -> None:
    assert cli_module.main(["check-startup"]) == 0


def test_cli_run_http_dispatches_to_server(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_http_async(self, **kwargs) -> None:
            calls.append(kwargs)

    config = RuntimeConfig(
        transport=TransportConfig(
            http_auth_token=SecretStr("internal-test-token"),
        )
    )

    monkeypatch.setattr(cli_module, "load_config", lambda: config)
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(
        ["run-http", "--host", "127.0.0.1", "--port", "8081", "--log-level", "DEBUG"]
    )

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["transport"] == "streamable-http"
    assert calls[0]["json_response"] is True
    assert calls[0]["stateless_http"] is False
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8081
    assert calls[0]["log_level"] == "DEBUG"
    middleware = calls[0]["middleware"]
    assert isinstance(middleware, list)
    assert len(middleware) == 2
    assert middleware[0].cls is HTTPReadinessMiddleware
    assert middleware[0].kwargs["app_name"] == "saudi-open-data-mcp"
    assert middleware[1].cls is HTTPBearerAuthMiddleware
    assert "internal-test-token" not in repr(middleware[1])
    assert middleware[1].kwargs["bearer_token"].get_secret_value() == "internal-test-token"
    assert middleware[1].kwargs["role"] is HTTPAuthRole.OPERATOR
    assert middleware[1].kwargs["capabilities"] == frozenset(HTTPAuthCapability)


def test_cli_run_http_uses_loopback_default_host(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_http_async(self, **kwargs) -> None:
            calls.append(kwargs)

    config = RuntimeConfig(
        transport=TransportConfig(
            http_auth_token=SecretStr("internal-test-token"),
        )
    )

    monkeypatch.setattr(cli_module, "load_config", lambda: config)
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(["run-http"])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["transport"] == "streamable-http"
    assert calls[0]["json_response"] is True
    assert calls[0]["stateless_http"] is False
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8000
    assert calls[0]["log_level"] == "INFO"
    middleware = calls[0]["middleware"]
    assert isinstance(middleware, list)
    assert len(middleware) == 2
    assert middleware[0].cls is HTTPReadinessMiddleware
    assert middleware[0].kwargs["app_name"] == "saudi-open-data-mcp"
    assert middleware[1].cls is HTTPBearerAuthMiddleware
    assert "internal-test-token" not in repr(middleware[1])
    assert middleware[1].kwargs["bearer_token"].get_secret_value() == "internal-test-token"
    assert middleware[1].kwargs["role"] is HTTPAuthRole.OPERATOR
    assert middleware[1].kwargs["capabilities"] == frozenset(HTTPAuthCapability)
    assert HTTP_READINESS_PATH == "/readyz"


def test_cli_run_http_requires_http_auth_token(monkeypatch) -> None:
    config = RuntimeConfig()

    monkeypatch.setattr(cli_module, "load_config", lambda: config)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["run-http"])

    assert excinfo.value.code == 2


def test_cli_run_http_loads_http_auth_token_from_local_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_http_async(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HTTP_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("HTTP_AUTH_ROLE", raising=False)
    monkeypatch.delenv("HTTP_AUTH_CAPABILITIES", raising=False)
    (tmp_path / ".env").write_text(
        "HTTP_AUTH_TOKEN=dotenv-test-token\n"
        "HTTP_AUTH_ROLE=viewer\n"
        "HTTP_AUTH_CAPABILITIES=read\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(["run-http"])

    assert exit_code == 0
    assert len(calls) == 1
    middleware = calls[0]["middleware"]
    assert middleware[1].kwargs["bearer_token"].get_secret_value() == "dotenv-test-token"
    assert middleware[1].kwargs["role"] is HTTPAuthRole.VIEWER
    assert middleware[1].kwargs["capabilities"] == frozenset({HTTPAuthCapability.READ})
    assert "HTTP_AUTH_TOKEN" not in os.environ


def test_cli_environment_overrides_local_dotenv_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_http_async(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HTTP_AUTH_TOKEN", "env-token")
    monkeypatch.setenv("HTTP_AUTH_ROLE", "viewer")
    monkeypatch.setenv("HTTP_AUTH_CAPABILITIES", "read")
    (tmp_path / ".env").write_text(
        "HTTP_AUTH_TOKEN=dotenv-test-token\n"
        "HTTP_AUTH_ROLE=operator\n"
        "HTTP_AUTH_CAPABILITIES=read,refresh,materialize\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(["run-http"])

    assert exit_code == 0
    assert len(calls) == 1
    middleware = calls[0]["middleware"]
    assert middleware[1].kwargs["bearer_token"].get_secret_value() == "env-token"
    assert middleware[1].kwargs["role"] is HTTPAuthRole.VIEWER
    assert middleware[1].kwargs["capabilities"] == frozenset({HTTPAuthCapability.READ})


def test_cli_run_stdio_dispatches_to_server(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_stdio_async(self, **kwargs) -> None:
            calls.append(kwargs)

    config = RuntimeConfig(log_level="INFO")

    monkeypatch.setattr(cli_module, "load_config", lambda: config)
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(["run-stdio", "--log-level", "DEBUG"])

    assert exit_code == 0
    assert calls == [
        {
            "log_level": "DEBUG",
        }
    ]


def test_cli_list_invokes_search_tool_and_emits_json(
    monkeypatch,
    capsys,
) -> None:
    app = _DummyToolApp(
        {
            "search_datasets": _DummyToolRunner(
                {
                    "status": "results",
                    "match_count": 1,
                    "matches": [
                        {
                            "dataset_id": "sama-pos-weekly",
                            "coverage_status": "queryable",
                        }
                    ],
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(["list", "pos", "--format", "json"])

    assert exit_code == 0
    assert app.calls["search_datasets"] == [{"query": "pos"}]
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "match_count": 1,
        "matches": [
            {
                "dataset_id": "sama-pos-weekly",
                "coverage_status": "queryable",
            }
        ],
        "status": "results",
    }


def test_cli_query_parses_scalar_filters_and_limit(
    monkeypatch,
    capsys,
) -> None:
    app = _DummyToolApp(
        {
            "query_dataset": _DummyToolRunner(
                {
                    "status": "success",
                    "dataset_id": "stats-gov-sa-cpi-headline-monthly",
                    "coverage_status": "queryable",
                    "matched_records": [],
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(
        [
            "query",
            "--dataset-id",
            "stats-gov-sa-cpi-headline-monthly",
            "--filter",
            "observation_month=2026-01",
            "--filter",
            "limit_hit=true",
            "--filter",
            "count=10",
            "--filter",
            "missing=null",
            "--limit",
            "5",
        ]
    )

    assert exit_code == 0
    assert app.calls["query_dataset"] == [
        {
            "dataset_id": "stats-gov-sa-cpi-headline-monthly",
            "filters": {
                "observation_month": "2026-01",
                "limit_hit": True,
                "count": 10,
                "missing": None,
            },
            "limit": 5,
        }
    ]
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "success"
    assert json.loads(captured.out)["coverage_status"] == "queryable"


def test_cli_query_rejects_positional_and_flag_dataset_id_together(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["query", "sama-pos-weekly", "--dataset-id", "sama-pos-weekly"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "provide either dataset_id or --dataset-id, not both" in captured.err


def test_cli_health_invokes_health_tool(
    monkeypatch,
    capsys,
) -> None:
    app = _DummyToolApp(
        {
            "dataset_health": _DummyToolRunner(
                {
                    "status": "found",
                    "dataset_id": "mof-budget-balance-quarterly",
                    "health_status": "unknown",
                    "coverage_status": "queryable",
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(["health", "mof-budget-balance-quarterly"])

    assert exit_code == 0
    assert app.calls["dataset_health"] == [{"dataset_id": "mof-budget-balance-quarterly"}]
    captured = capsys.readouterr()
    assert json.loads(captured.out)["dataset_id"] == "mof-budget-balance-quarterly"
    assert json.loads(captured.out)["coverage_status"] == "queryable"


def test_cli_preview_invokes_preview_tool(
    monkeypatch,
    capsys,
) -> None:
    app = _DummyToolApp(
        {
            "preview_dataset": _DummyToolRunner(
                {
                    "status": "record_derivable",
                    "dataset_id": "stats-gov-sa-cpi-headline-monthly",
                    "coverage_status": "queryable",
                    "resolution_outcome": "serve_local",
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(["preview", "stats-gov-sa-cpi-headline-monthly"])

    assert exit_code == 0
    assert app.calls["preview_dataset"] == [
        {"dataset_id": "stats-gov-sa-cpi-headline-monthly"}
    ]
    captured = capsys.readouterr()
    assert json.loads(captured.out)["resolution_outcome"] == "serve_local"
    assert json.loads(captured.out)["coverage_status"] == "queryable"


def test_cli_refresh_invokes_materialize_tool(
    monkeypatch,
    capsys,
) -> None:
    app = _DummyToolApp(
        {
            "materialize_hot_set": _DummyToolRunner(
                {
                    "requested_dataset_count": 6,
                    "materialized_count": 6,
                    "failed_count": 0,
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(["refresh", "--include-optional"])

    assert exit_code == 0
    assert app.calls["materialize_hot_set"] == [{"include_optional": True}]
    captured = capsys.readouterr()
    assert json.loads(captured.out)["materialized_count"] == 6


def test_cli_export_writes_query_result_to_output_file_and_respects_quiet(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "export.json"
    app = _DummyToolApp(
        {
            "query_dataset": _DummyToolRunner(
                {
                    "status": "success",
                    "dataset_id": "sama-pos-weekly",
                    "coverage_status": "queryable",
                    "matched_records": [{"dataset_id": "sama-pos-weekly"}],
                }
            )
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(
        [
            "export",
            "sama-pos-weekly",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )

    assert exit_code == 0
    assert app.calls["query_dataset"] == [
        {
            "dataset_id": "sama-pos-weekly",
            "filters": None,
            "limit": None,
        }
    ]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(output_path.read_text())["coverage_status"] == "queryable"
    assert json.loads(output_path.read_text())["matched_records"] == [
        {"dataset_id": "sama-pos-weekly"}
    ]


def test_cli_export_writes_excel_artifact_with_health_metadata(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "export.xml"
    app = _DummyToolApp(
        {
            "query_dataset": _DummyToolRunner(
                {
                    "dataset_id": "sama-pos-weekly",
                    "status": "success",
                    "coverage_status": "queryable",
                    "source": "sama",
                    "data_origin": "local_snapshot",
                    "applied_filters": {},
                    "limit": None,
                    "total_records_before_filter": 1,
                    "failure_stage": None,
                    "degradation_reason": None,
                    "matched_records": [
                        {
                            "dataset_id": "sama-pos-weekly",
                            "source": "sama",
                            "record_index": 0,
                            "fields": {"week_end_date": "2026-01-03", "value": 12},
                        }
                    ],
                    "limitations": [],
                    "failure": None,
                }
            ),
            "dataset_health": _DummyToolRunner(
                {
                    "dataset_id": "sama-pos-weekly",
                    "status": "found",
                    "health_status": "healthy",
                    "coverage_status": "queryable",
                    "schema_version": "0.1.0",
                    "caveats": [],
                    "known_issues": [],
                    "freshness": {
                        "source": "sama",
                        "dataset_id": "sama-pos-weekly",
                        "status": "fresh",
                        "reason": "within_expected_window",
                        "artifact_present": True,
                        "reference_time": "2026-04-07T08:00:00Z",
                        "snapshot_modified_at": "2026-04-06T00:00:00Z",
                        "snapshot_age": "P1D",
                        "update_frequency": "weekly",
                    },
                }
            ),
        }
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: app)

    exit_code = cli_module.main(
        [
            "export",
            "sama-pos-weekly",
            "--format",
            "excel",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )

    assert exit_code == 0
    assert app.calls["query_dataset"] == [
        {
            "dataset_id": "sama-pos-weekly",
            "filters": None,
            "limit": None,
        }
    ]
    assert app.calls["dataset_health"] == [{"dataset_id": "sama-pos-weekly"}]
    captured = capsys.readouterr()
    assert captured.out == ""
    rendered = output_path.read_text(encoding="utf-8")
    assert "<?mso-application progid=\"Excel.Sheet\"?>" in rendered
    assert "sama-pos-weekly" in rendered
    assert "fresh" in rendered


def test_cli_export_rejects_excel_without_output(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["export", "sama-pos-weekly", "--format", "excel"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--output is required when --format is excel" in captured.err


def test_cli_config_redacts_http_auth_token(
    monkeypatch,
    capsys,
) -> None:
    config = RuntimeConfig(
        transport=TransportConfig(
            http_auth_token=SecretStr("internal-test-token"),
            http_auth_role=HTTPAuthRole.VIEWER,
            http_auth_capabilities=frozenset({HTTPAuthCapability.READ}),
        )
    )
    monkeypatch.setattr(cli_module, "load_config", lambda: config)

    exit_code = cli_module.main(["config"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["transport"]["http_auth_token_configured"] is True
    assert payload["transport"]["http_auth_capabilities"] == ["read"]
    assert payload["transport"]["http_auth_role"] == "viewer"
    assert "http_auth_token" not in payload["transport"]
    assert "internal-test-token" not in captured.out


def test_cli_rejects_unsupported_output_format(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["config", "--format", "yaml"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unsupported --format 'yaml'; only json is currently supported" in captured.err


def test_cli_rejects_quiet_without_output(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["config", "--quiet"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--quiet requires --output" in captured.err


def test_cli_check_startup_reports_runtime_configuration_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "load_config", lambda: RuntimeConfig())

    def _boom(_runtime_config=None):
        raise RuntimeConfigurationError("SNAPSHOT_DIR must point to a directory path")

    monkeypatch.setattr(cli_module, "create_server", _boom)

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(["check-startup"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "SNAPSHOT_DIR must point to a directory path" in captured.err


def test_source_tree_cli_check_startup_runs_subprocess() -> None:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    python = Path(sys.prefix) / "bin" / "python"

    result = subprocess.run(
        [str(python), "src/saudi_open_data_mcp/cli.py", "--check-startup"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "startup wiring and registry bootstrap are valid" in result.stdout


@pytest.mark.asyncio
async def test_source_tree_cli_stdio_uses_explicit_runtime_paths_outside_repo_root(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    python = Path(sys.prefix) / "bin" / "python"
    registry_path = tmp_path / "runtime" / "registry.sqlite"
    snapshot_store = SnapshotStore(tmp_path / "runtime" / "snapshots")
    outside_repo_root = tmp_path / "outside-repo-root"
    outside_repo_root.mkdir()

    bootstrap_registry(RegistryRepository(registry_path))
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id="report.aspx?cid=55",
            content={
                "url": (
                    "https://www.sama.gov.sa/en-US/EconomicReports/Pages/"
                    "report.aspx?cid=55"
                ),
                "status_code": 200,
                "content_type": "application/json",
                "body": {"rows": [{"period": "2026-01", "value": 1}]},
            },
        )
    )

    transport = StdioTransport(
        command=str(python),
        args=[str(root / "src" / "saudi_open_data_mcp" / "cli.py"), "run-stdio"],
        cwd=str(outside_repo_root),
        env={
            "LOG_LEVEL": "ERROR",
            "REGISTRY_PATH": str(registry_path),
            "SNAPSHOT_DIR": str(snapshot_store.root),
        },
    )

    async with Client(transport) as client:
        result = await client.call_tool(
            "download_dataset",
            {"dataset_id": "sama-money-supply"},
        )

    assert result.structured_content["status"] == "available"
    assert result.structured_content["dataset_id"] == "sama-money-supply"
    assert result.structured_content["local_snapshot_exists"] is True
    assert result.structured_content["freshness"]["artifact_present"] is True
    assert "snapshot_path" not in result.structured_content
    assert "snapshot_path" not in result.structured_content["freshness"]


@pytest.mark.asyncio
async def test_source_tree_cli_stdio_supports_data_gov_sa_query_with_explicit_runtime_paths(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    python = Path(sys.prefix) / "bin" / "python"
    registry_path = tmp_path / "runtime" / "registry.sqlite"
    snapshot_store = SnapshotStore(tmp_path / "runtime" / "snapshots")
    outside_repo_root = tmp_path / "outside-repo-root"
    outside_repo_root.mkdir()

    bootstrap_registry(RegistryRepository(registry_path))
    snapshot_store.write_snapshot(
        RawPayload(
            source="data-gov-sa",
            dataset_id=DATA_GOV_SA_SOURCE_LOCATOR,
            content={
                "url": f"https://open.data.gov.sa{DATA_GOV_SA_SOURCE_LOCATOR}",
                "status_code": 200,
                "content_type": "application/json",
                "body": [{"marital_status": "Single", "count": 123}],
            },
        )
    )

    transport = StdioTransport(
        command=str(python),
        args=[str(root / "src" / "saudi_open_data_mcp" / "cli.py"), "run-stdio"],
        cwd=str(outside_repo_root),
        env={
            "LOG_LEVEL": "ERROR",
            "REGISTRY_PATH": str(registry_path),
            "SNAPSHOT_DIR": str(snapshot_store.root),
        },
    )

    async with Client(transport) as client:
        result = await client.call_tool(
            "query_dataset",
            {
                "dataset_id": DATA_GOV_SA_DATASET_ID,
                "filters": {"marital_status": "Single"},
                "limit": 1,
            },
        )

    assert result.structured_content["status"] == "limited"
    assert result.structured_content["dataset_id"] == DATA_GOV_SA_DATASET_ID
    assert result.structured_content["coverage_status"] == "catalog_only"
    assert result.structured_content["source"] == "data-gov-sa"
    assert result.structured_content["matched_records"] == []
    assert result.structured_content["limitations"] == [
        "dataset_registry_declares_no_current_queryable_support"
    ]


@pytest.mark.asyncio
async def test_source_tree_cli_stdio_uses_default_anchored_paths_outside_repo_root(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    python = Path(sys.prefix) / "bin" / "python"
    registry_path = root / ".local" / "registry.sqlite"
    snapshot_store = SnapshotStore(root / ".local" / "snapshots")
    snapshot_path = snapshot_store.snapshot_path("sama", "report.aspx?cid=55")
    outside_repo_root = tmp_path / "outside-repo-root"
    outside_repo_root.mkdir()
    env = os.environ.copy()
    env.pop("REGISTRY_PATH", None)
    env.pop("SNAPSHOT_DIR", None)
    env.pop("CACHE_DIR", None)
    env["LOG_LEVEL"] = "ERROR"

    original_registry = _read_optional_bytes(registry_path)
    original_snapshot = _read_optional_bytes(snapshot_path)

    try:
        if registry_path.exists():
            registry_path.unlink()
        if snapshot_path.exists():
            snapshot_path.unlink()

        bootstrap_registry(RegistryRepository(registry_path))
        snapshot_store.write_snapshot(
            RawPayload(
                source="sama",
                dataset_id="report.aspx?cid=55",
                content={
                    "url": (
                        "https://www.sama.gov.sa/en-US/EconomicReports/Pages/"
                        "report.aspx?cid=55"
                    ),
                    "status_code": 200,
                    "content_type": "application/json",
                    "body": {"rows": [{"period": "2026-01", "value": 1}]},
                },
            )
        )

        transport = StdioTransport(
            command=str(python),
            args=[str(root / "src" / "saudi_open_data_mcp" / "cli.py"), "run-stdio"],
            cwd=str(outside_repo_root),
            env=env,
        )

        async with Client(transport) as client:
            result = await client.call_tool(
                "download_dataset",
                {"dataset_id": "sama-money-supply"},
            )

        assert result.structured_content["status"] == "available"
        assert result.structured_content["dataset_id"] == "sama-money-supply"
        assert result.structured_content["local_snapshot_exists"] is True
        assert result.structured_content["freshness"]["artifact_present"] is True
        assert "snapshot_path" not in result.structured_content
        assert "snapshot_path" not in result.structured_content["freshness"]
    finally:
        _restore_optional_bytes(registry_path, original_registry)
        _restore_optional_bytes(snapshot_path, original_snapshot)


def _read_optional_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _restore_optional_bytes(path: Path, contents: bytes | None) -> None:
    if contents is None:
        if path.exists():
            path.unlink()
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


class _DummyToolRunner:
    def __init__(self, structured_content: dict[str, object]) -> None:
        self.structured_content = structured_content
        self.calls: list[dict[str, object]] = []

    async def run(self, arguments: dict[str, object]) -> SimpleNamespace:
        self.calls.append(arguments)
        return SimpleNamespace(structured_content=self.structured_content)


class _DummyToolApp:
    def __init__(self, tools: dict[str, _DummyToolRunner]) -> None:
        self._tools = tools
        self.calls: dict[str, list[dict[str, object]]] = {
            name: runner.calls for name, runner in tools.items()
        }

    async def get_tools(self) -> dict[str, _DummyToolRunner]:
        return self._tools
