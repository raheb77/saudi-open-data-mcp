"""Smoke tests for the scaffold CLI."""

from saudi_open_data_mcp.cli import main


def test_cli_check_imports_mode_returns_success() -> None:
    assert main(["--check-imports"]) == 0
