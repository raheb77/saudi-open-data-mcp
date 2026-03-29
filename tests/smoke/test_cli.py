"""Smoke tests for the scaffold CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from saudi_open_data_mcp import cli as cli_module
from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.registry.bootstrap import bootstrap_registry
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


def test_cli_check_imports_mode_returns_success() -> None:
    assert cli_module.main(["--check-imports"]) == 0


def test_cli_check_imports_subcommand_returns_success() -> None:
    assert cli_module.main(["check-imports"]) == 0


def test_cli_run_http_dispatches_to_server(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class DummyApp:
        async def run_http_async(self, **kwargs) -> None:
            calls.append(kwargs)

    config = RuntimeConfig()

    monkeypatch.setattr(cli_module, "load_config", lambda: config)
    monkeypatch.setattr(cli_module, "create_server", lambda runtime_config=None: DummyApp())

    exit_code = cli_module.main(
        ["run-http", "--host", "127.0.0.1", "--port", "8081", "--log-level", "DEBUG"]
    )

    assert exit_code == 0
    assert calls == [
        {
            "transport": "streamable-http",
            "host": "127.0.0.1",
            "port": 8081,
            "log_level": "DEBUG",
        }
    ]


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


def test_source_tree_cli_check_imports_runs_subprocess() -> None:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    python = Path(sys.prefix) / "bin" / "python"

    result = subprocess.run(
        [str(python), "src/saudi_open_data_mcp/cli.py", "--check-imports"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "server wiring is importable" in result.stdout


@pytest.mark.asyncio
async def test_source_tree_cli_stdio_uses_explicit_runtime_paths_outside_repo_root(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    python = Path(sys.prefix) / "bin" / "python"
    registry_path = tmp_path / "runtime" / "registry.sqlite"
    snapshot_store = SnapshotStore(tmp_path / "runtime" / "snapshots")
    snapshot_path = snapshot_store.snapshot_path("sama", "report.aspx?cid=55")
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
    assert result.structured_content["snapshot_path"] == str(snapshot_path)
