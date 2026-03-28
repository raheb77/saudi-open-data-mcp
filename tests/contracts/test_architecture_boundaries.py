"""Contract tests for architectural boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from pydantic import BaseModel

from saudi_open_data_mcp.normalization.pipeline import CanonicalRecord, NormalizationResult


def _tool_module_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return sorted((root / "src" / "saudi_open_data_mcp" / "tools").glob("*.py"))


def test_tool_modules_do_not_import_connectors() -> None:
    for path in _tool_module_paths():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "connectors" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "connectors" not in alias.name


def test_normalization_outputs_are_typed_models() -> None:
    assert issubclass(CanonicalRecord, BaseModel)
    assert issubclass(NormalizationResult, BaseModel)
