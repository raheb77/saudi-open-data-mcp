"""Smoke tests for the scaffold CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from saudi_open_data_mcp import __main__ as main_module
from saudi_open_data_mcp import cli as cli_module
from saudi_open_data_mcp.config import RuntimeConfig


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


def test_module_entrypoint_delegates_to_cli(monkeypatch) -> None:
    calls: list[object] = []

    def _fake_cli_main(argv=None) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(main_module, "cli_main", _fake_cli_main)

    assert main_module.main(["check-imports"]) == 0
    assert calls == [["check-imports"]]


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
