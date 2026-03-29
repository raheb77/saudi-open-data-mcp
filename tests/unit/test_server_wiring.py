"""Unit tests for server-side MCP wiring."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from saudi_open_data_mcp.config import RuntimeConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.server import create_server
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools import download as download_module
from saudi_open_data_mcp.tools import health as health_module

REPORT_LOCATOR = "report.aspx?cid=55"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
    )


@respx.mock
async def test_server_registers_catalog_resource_metadata_health_search_preview_and_download_tools(
    tmp_path: Path,
) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    app = create_server(_runtime_config(tmp_path))

    resources = await app.get_resources()
    tools = await app.get_tools()

    assert set(resources) == {"resource://catalog"}
    assert set(tools) == {
        "download_dataset",
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
    assert health_result.structured_content["freshness"]["status"] == "missing"
    assert health_result.structured_content["freshness"]["reason"] == "no_snapshot"

    download_result = await tools["download_dataset"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert download_result.structured_content["dataset_id"] == "sama-money-supply"
    assert download_result.structured_content["status"] == "artifact_missing"
    assert download_result.structured_content["reason"] == "no_local_snapshot"
    assert download_result.structured_content["local_snapshot_exists"] is False
    assert download_result.structured_content["source"] == "sama"
    assert download_result.structured_content["freshness"]["status"] == "missing"
    assert download_result.structured_content["freshness"]["reason"] == "no_snapshot"

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


async def test_server_metadata_health_and_download_lookup_keep_missing_dataset_explicit(
    tmp_path: Path,
) -> None:
    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()

    metadata_result = await tools["dataset_metadata"].run({"dataset_id": "missing-dataset"})
    health_result = await tools["dataset_health"].run({"dataset_id": "missing-dataset"})
    download_result = await tools["download_dataset"].run(
        {"dataset_id": "missing-dataset"}
    )

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
    assert download_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "unknown_dataset",
        "reason": "dataset_not_in_registry",
        "local_snapshot_exists": False,
        "source": None,
        "snapshot_path": None,
        "freshness": None,
    }


async def test_server_health_tool_can_expose_recent_snapshot_freshness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reference_time = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    _write_snapshot_with_mtime(
        snapshot_store,
        dataset_id=REPORT_LOCATOR,
        modified_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )

    original = health_module.evaluate_snapshot_freshness

    def _fixed_reference_freshness(**kwargs):
        kwargs["reference_time"] = reference_time
        return original(**kwargs)

    # The server does not pass reference_time into the health tool today.
    # Patch the freshness seam so this server-wiring check stays deterministic.
    monkeypatch.setattr(health_module, "evaluate_snapshot_freshness", _fixed_reference_freshness)

    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()
    health_result = await tools["dataset_health"].run({"dataset_id": "sama-money-supply"})

    assert health_result.structured_content["status"] == "found"
    assert health_result.structured_content["freshness"]["status"] == "fresh"
    assert health_result.structured_content["freshness"]["reason"] == "within_expected_window"
    assert health_result.structured_content["freshness"]["dataset_id"] == "sama-money-supply"


async def test_server_download_tool_can_expose_local_snapshot_availability(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reference_time = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    snapshot_path = _write_snapshot_with_mtime(
        snapshot_store,
        dataset_id=REPORT_LOCATOR,
        modified_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )

    original = download_module.evaluate_snapshot_freshness

    def _fixed_reference_freshness(**kwargs):
        kwargs["reference_time"] = reference_time
        return original(**kwargs)

    # The server does not pass reference_time into the download tool today.
    # Patch the freshness seam so this server-wiring check stays deterministic.
    monkeypatch.setattr(
        download_module,
        "evaluate_snapshot_freshness",
        _fixed_reference_freshness,
    )

    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()
    download_result = await tools["download_dataset"].run(
        {"dataset_id": "sama-money-supply"}
    )

    assert download_result.structured_content["status"] == "available"
    assert download_result.structured_content["reason"] == "local_snapshot_available"
    assert download_result.structured_content["local_snapshot_exists"] is True
    assert download_result.structured_content["snapshot_path"] == str(snapshot_path)
    assert download_result.structured_content["freshness"]["status"] == "fresh"
    assert download_result.structured_content["freshness"]["reason"] == (
        "within_expected_window"
    )
    assert download_result.structured_content["freshness"]["dataset_id"] == (
        "sama-money-supply"
    )


@respx.mock
async def test_server_preview_tool_keeps_html_preview_limited(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()

    preview_result = await tools["preview_dataset"].run({"dataset_id": REPORT_LOCATOR})

    assert preview_result.structured_content["status"] == "limited"
    assert preview_result.structured_content["failure"] is None
    assert preview_result.structured_content["normalization_result"]["status"] == "limited"


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    dataset_id: str,
    modified_at: datetime,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=dataset_id,
        content={"body": {"rows": []}},
    )
    path = store.write_snapshot(payload)
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
