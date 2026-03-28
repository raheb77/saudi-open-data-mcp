"""Unit tests for server-side MCP wiring."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.server import create_server

REPORT_LOCATOR = "report.aspx?cid=55"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


@respx.mock
async def test_server_registers_catalog_resource_metadata_health_search_and_preview_tools(
    tmp_path: Path,
) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    app = create_server(RuntimeConfig(registry_path=tmp_path / "registry.sqlite"))

    resources = await app.get_resources()
    tools = await app.get_tools()

    assert set(resources) == {"resource://catalog"}
    assert set(tools) == {
        "dataset_health",
        "dataset_metadata",
        "preview_dataset",
        "search_datasets",
    }

    catalog_payload = json.loads(await resources["resource://catalog"].read())
    assert catalog_payload["dataset_count"] == 3
    assert catalog_payload["datasets"][0]["dataset_id"] == "sama-balance-of-payments"

    metadata_result = await tools["dataset_metadata"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert metadata_result.structured_content["status"] == "found"
    assert metadata_result.structured_content["dataset_id"] == "sama-money-supply"
    assert metadata_result.structured_content["metadata"]["title"] == "Money Supply"

    health_result = await tools["dataset_health"].run({"dataset_id": "sama-money-supply"})
    assert health_result.structured_content["status"] == "found"
    assert health_result.structured_content["dataset_id"] == "sama-money-supply"
    assert health_result.structured_content["health_status"] == "unknown"
    assert health_result.structured_content["schema_version"] == "0.1.0"

    search_result = await tools["search_datasets"].run({"query": "money"})
    assert search_result.structured_content["query"] == "money"
    assert search_result.structured_content["normalized_query"] == "money"
    assert search_result.structured_content["mode"] == "filtered"
    assert search_result.structured_content["match_count"] == 1
    assert search_result.structured_content["matches"] == [
        {
            "dataset_id": "sama-money-supply",
            "source": "sama",
            "title": "Money Supply",
            "update_frequency": "monthly",
            "health_status": "unknown",
        }
    ]

    all_datasets_result = await tools["search_datasets"].run({"query": "   "})
    assert all_datasets_result.structured_content["query"] == "   "
    assert all_datasets_result.structured_content["normalized_query"] == ""
    assert all_datasets_result.structured_content["mode"] == "all_datasets"
    assert all_datasets_result.structured_content["match_count"] == 3
    assert [
        match["dataset_id"] for match in all_datasets_result.structured_content["matches"]
    ] == [
        "sama-balance-of-payments",
        "sama-interest-rates",
        "sama-money-supply",
    ]

    preview_result = await tools["preview_dataset"].run({"dataset_id": REPORT_LOCATOR})
    assert preview_result.structured_content["status"] == "record_derivable"
    assert preview_result.structured_content["dataset_id"] == REPORT_LOCATOR
    assert preview_result.structured_content["failure"] is None
    assert preview_result.structured_content["normalization_result"]["status"] == (
        "record_derivable"
    )


async def test_server_metadata_and_health_lookup_keep_missing_dataset_explicit(
    tmp_path: Path,
) -> None:
    app = create_server(RuntimeConfig(registry_path=tmp_path / "registry.sqlite"))
    tools = await app.get_tools()

    metadata_result = await tools["dataset_metadata"].run({"dataset_id": "missing-dataset"})
    health_result = await tools["dataset_health"].run({"dataset_id": "missing-dataset"})

    assert metadata_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "metadata": None,
    }
    assert health_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "health_status": None,
        "schema_version": None,
        "caveats": [],
        "known_issues": [],
    }


@respx.mock
async def test_server_preview_tool_keeps_html_preview_limited(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    app = create_server(RuntimeConfig(registry_path=tmp_path / "registry.sqlite"))
    tools = await app.get_tools()

    preview_result = await tools["preview_dataset"].run({"dataset_id": REPORT_LOCATOR})

    assert preview_result.structured_content["status"] == "limited"
    assert preview_result.structured_content["failure"] is None
    assert preview_result.structured_content["normalization_result"]["status"] == "limited"
