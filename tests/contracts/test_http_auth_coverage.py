"""Contract tests for HTTP auth capability coverage over the exposed MCP surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.security.http_auth import (
    ALL_CAPABILITY_MAPPED_TOOL_NAMES,
    READ_RESOURCE_URIS,
)
from saudi_open_data_mcp.server import create_server


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
    )


@pytest.mark.asyncio
async def test_http_auth_coverage_matches_registered_server_surface(
    tmp_path: Path,
) -> None:
    app = create_server(_runtime_config(tmp_path))

    resources = await app.get_resources()
    tools = await app.get_tools()

    assert set(resources) == READ_RESOURCE_URIS
    assert set(tools) == ALL_CAPABILITY_MAPPED_TOOL_NAMES
