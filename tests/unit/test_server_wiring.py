"""Unit tests for server-side MCP wiring."""

from __future__ import annotations

import json
from pathlib import Path

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.server import create_server


async def test_server_registers_catalog_resource_and_metadata_tool(
    tmp_path: Path,
) -> None:
    app = create_server(RuntimeConfig(registry_path=tmp_path / "registry.sqlite"))

    resources = await app.get_resources()
    tools = await app.get_tools()

    assert set(resources) == {"resource://catalog"}
    assert set(tools) == {"dataset_metadata"}

    catalog_payload = json.loads(await resources["resource://catalog"].read())
    assert catalog_payload["dataset_count"] == 3
    assert catalog_payload["datasets"][0]["dataset_id"] == "sama-balance-of-payments"

    tool_result = await tools["dataset_metadata"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert tool_result.structured_content["status"] == "found"
    assert tool_result.structured_content["dataset_id"] == "sama-money-supply"
    assert tool_result.structured_content["metadata"]["title"] == "Money Supply"


async def test_server_metadata_lookup_keeps_missing_dataset_explicit(
    tmp_path: Path,
) -> None:
    app = create_server(RuntimeConfig(registry_path=tmp_path / "registry.sqlite"))
    tools = await app.get_tools()

    tool_result = await tools["dataset_metadata"].run({"dataset_id": "missing-dataset"})

    assert tool_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "metadata": None,
    }