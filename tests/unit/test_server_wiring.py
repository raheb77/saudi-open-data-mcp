"""Unit tests for server-side MCP wiring."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from saudi_open_data_mcp import server as server_module
from saudi_open_data_mcp.config import RuntimeConfig, TierARefreshConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.observability import get_metrics
from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
)
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetHealthStatus,
    HealthMetadata,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.server import create_server
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools import download as download_module
from saudi_open_data_mcp.tools import health as health_module
from saudi_open_data_mcp.tools.preview import DatasetPreviewResult, PreviewStatus

REPORT_LOCATOR = "report.aspx?cid=55"
POS_PAGE_LOCATOR = "/en-US/Indices/Pages/POS.aspx"
EXCHANGE_RATES_PAGE_LOCATOR = "/en-US/FinExc/Pages/Currency.aspx"
WEEKLY_MONEY_SUPPLY_PAGE_LOCATOR = "/en-US/Indices/Pages/WeeklyMoneySupply.aspx"
REPO_RATE_PAGE_LOCATOR = "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx"
REVERSE_REPO_RATE_PAGE_LOCATOR = "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx"
DATA_GOV_SA_DATASET_ID = "data-gov-sa-census-marital-status"
DATA_GOV_SA_SOURCE_LOCATOR = (
    "/ar/datasets/view/104380ce-60b6-46bc-ba0a-6d5e10ac46cb/"
    "preview/parsed/Census%20Marital%20Status%20CSV.json"
)


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


def _data_gov_sa_preview_url() -> str:
    return f"https://open.data.gov.sa{DATA_GOV_SA_SOURCE_LOCATOR}"


def _page_url(locator: str) -> str:
    return f"https://www.sama.gov.sa{locator}"


def _pos_report_url(name: str) -> str:
    return f"https://www.sama.gov.sa/en-US/Indices/POS_EN/{name}"


def _pos_reports_page_html() -> str:
    return """
        <html><body>
          <a
            href="https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
          >04 Apr</a>
          <a
            href="https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf"
          >28 Mar</a>
        </body></html>
    """


def _exchange_rates_landing_page_html() -> str:
    return """
        <html><body>
          <form method="post" action="./Currency.aspx" id="aspnetForm">
            <input type="hidden" name="__VIEWSTATE" value="landing-viewstate" />
            <input type="hidden" name="__EVENTVALIDATION" value="landing-validation" />
            <select name="ctl00$ctl50$ctl00$ddlCurrencies">
              <option selected="selected" value="-1">All</option>
              <option value="USD=">US DOLLAR</option>
              <option value="EUR=">EURO</option>
              <option value="JPY=">JAPANESE YEN</option>
            </select>
            <input
              name="ctl00$ctl50$ctl00$txtDatePicker"
              type="text"
              value=""
            />
            <input
              type="submit"
              name="ctl00$ctl50$ctl00$btnSearch"
              value="Search"
            />
            <span id="ctl00_ctl50_ctl00_lblItemsCount">Number of result is 138511</span>
            <table class="tableCurrency grid" id="ctl00_ctl50_ctl00_dgResults">
              <tr class="headerstyle gridhead">
                <td>Currency Against S.R</td>
                <td>Closing Price</td>
                <td>Last Updated Date</td>
              </tr>
              <tr>
                <td>US DOLLAR</td><td>3.750000</td><td>21/03/2026</td>
              </tr>
              <tr class="AlternatingGridStyle gridalter">
                <td>EURO</td><td>4.050000</td><td>21/03/2026</td>
              </tr>
              <tr class="PagerStyle" align="center">
                <td colspan="3">
                  <span>1</span>&nbsp;
                  <a href="javascript:__doPostBack('page-2-target','')">2</a>
                </td>
              </tr>
            </table>
          </form>
        </body></html>
    """


def _exchange_rates_results_page_html(
    *,
    viewstate: str,
    rows: list[tuple[str, str, str]],
    total_results_count: int,
    pager_links: list[tuple[str, str]] | None = None,
) -> str:
    pager_html = ""
    if pager_links:
        links = "&nbsp;".join(
            f"<a href=\"javascript:__doPostBack('{target}','')\">{label}</a>"
            for label, target in pager_links
        )
        pager_html = (
            '<tr class="PagerStyle" align="center">'
            f"<td colspan=\"3\">{links}</td>"
            "</tr>"
        )
    rows_html = "".join(
        f"<tr><td>{currency}</td><td>{rate}</td><td>{date_text}</td></tr>"
        for currency, rate, date_text in rows
    )
    return f"""
        <html><body>
          <form method="post" action="./Currency.aspx" id="aspnetForm">
            <input type="hidden" name="__VIEWSTATE" value="{viewstate}" />
            <input type="hidden" name="__EVENTVALIDATION" value="{viewstate}-validation" />
            <select name="ctl00$ctl50$ctl00$ddlCurrencies">
              <option selected="selected" value="-1">All</option>
              <option value="USD=">US DOLLAR</option>
              <option value="EUR=">EURO</option>
              <option value="JPY=">JAPANESE YEN</option>
            </select>
            <input
              name="ctl00$ctl50$ctl00$txtDatePicker"
              type="text"
              value="21/03/2026"
            />
            <input
              type="submit"
              name="ctl00$ctl50$ctl00$btnSearch"
              value="Search"
            />
            <span id="ctl00_ctl50_ctl00_lblItemsCount">
              Number of result is {total_results_count}
            </span>
            <table class="tableCurrency grid" id="ctl00_ctl50_ctl00_dgResults">
              <tr class="headerstyle gridhead">
                <td>Currency Against S.R</td>
                <td>Closing Price</td>
                <td>Last Updated Date</td>
              </tr>
              {rows_html}
              {pager_html}
            </table>
          </form>
        </body></html>
    """


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
    )


@respx.mock
async def test_server_registers_current_mcp_surface(
    tmp_path: Path,
) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    respx.get(_data_gov_sa_preview_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"status": "single", "count": 10}]},
            headers={"content-type": "application/json"},
        )
    )
    app = create_server(_runtime_config(tmp_path))
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    expected_datasets = repository.list_datasets()
    assert len(expected_datasets) == len(INITIAL_DATASET_DESCRIPTORS)

    resources = await app.get_resources()
    tools = await app.get_tools()

    assert set(resources) == {
        "resource://catalog",
        "resource://observability",
        "resource://policies",
    }
    assert set(tools) == {
        "download_dataset",
        "dataset_health",
        "dataset_metadata",
        "materialize_hot_set",
        "preview_dataset",
        "query_dataset",
        "search_datasets",
    }

    catalog_payload = json.loads(await resources["resource://catalog"].read())
    observability_payload = json.loads(await resources["resource://observability"].read())
    policies_payload = json.loads(await resources["resource://policies"].read())
    assert catalog_payload["dataset_count"] == len(expected_datasets)
    assert catalog_payload["datasets"][0]["dataset_id"] == expected_datasets[0].dataset_id
    assert catalog_payload["datasets"][0]["coverage_status"] in {
        "queryable",
        "limited",
        "catalog_only",
    }
    assert observability_payload["process_local"] is True
    assert [group["name"] for group in observability_payload["groups"]] == [
        "startup",
        "preview",
        "auth",
        "connectors",
        "materialization",
        "tier_a_refresh",
    ]
    assert (
        observability_payload["groups"][0]["counters"][0]["name"]
        == "server.startup.attempts"
    )
    assert observability_payload["raw_counters"]["server.startup.attempts"] == 1
    assert observability_payload["raw_counters"]["server.startup.ready"] == 1
    assert "process restart" in observability_payload["notes"][0]
    assert policies_payload["decision"] == "keep_current_surface"
    assert policies_payload["query_primary_dataset_ids"] == [
        "sama-pos-weekly",
        "sama-money-supply-weekly",
        "sama-deposits-core",
        "sama-exchange-rates-current",
        "sama-repo-rate",
        "sama-reverse-repo-rate",
        "stats-gov-sa-cpi-headline-monthly",
        "stats-gov-sa-unemployment-rate-total-quarterly",
        "stats-gov-sa-real-gdp-growth-quarterly",
        "mof-budget-balance-quarterly",
    ]
    assert [policy["tool_name"] for policy in policies_payload["tool_policies"]] == [
        "query_dataset",
        "preview_dataset",
        "download_dataset",
        "materialize_hot_set",
    ]

    metadata_result = await tools["dataset_metadata"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert metadata_result.structured_content["status"] == "found"
    assert metadata_result.structured_content["dataset_id"] == "sama-money-supply"
    assert metadata_result.structured_content["metadata"]["title"] == "Money Supply"
    assert metadata_result.structured_content["metadata"]["coverage_status"] == "catalog_only"
    assert "source_locator" not in metadata_result.structured_content["metadata"]

    health_result = await tools["dataset_health"].run({"dataset_id": "sama-money-supply"})
    assert health_result.structured_content["status"] == "found"
    assert health_result.structured_content["dataset_id"] == "sama-money-supply"
    assert health_result.structured_content["health_status"] == "unknown"
    assert health_result.structured_content["coverage_status"] == "catalog_only"
    assert health_result.structured_content["schema_version"] == "0.1.0"
    assert health_result.structured_content["freshness"]["status"] == "missing"
    assert health_result.structured_content["freshness"]["reason"] == "no_snapshot"
    assert health_result.structured_content["freshness"]["artifact_present"] is False
    assert "snapshot_path" not in health_result.structured_content["freshness"]

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
    assert download_result.structured_content["freshness"]["artifact_present"] is False
    assert "snapshot_path" not in download_result.structured_content
    assert "snapshot_path" not in download_result.structured_content["freshness"]

    missing_query_result = await tools["query_dataset"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert missing_query_result.structured_content["dataset_id"] == "sama-money-supply"
    assert missing_query_result.structured_content["status"] == "snapshot_missing"
    assert missing_query_result.structured_content["source"] == "sama"
    assert missing_query_result.structured_content["matched_records"] == []

    _write_snapshot_with_mtime(
        SnapshotStore(tmp_path / "snapshots"),
        dataset_id=REPORT_LOCATOR,
        modified_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        body={
            "rows": [
                {"period": "2026-01", "value": 1},
                {"period": "2026-02", "value": 2},
            ]
        },
    )

    filtered_query_result = await tools["query_dataset"].run(
        {
            "dataset_id": "sama-money-supply",
            "filters": {"period": "2026-02"},
        }
    )
    assert filtered_query_result.structured_content["dataset_id"] == "sama-money-supply"
    assert filtered_query_result.structured_content["status"] == "success"
    assert filtered_query_result.structured_content["source"] == "sama"
    assert filtered_query_result.structured_content["applied_filters"] == {
        "period": "2026-02"
    }
    assert filtered_query_result.structured_content["total_records_before_filter"] == 2
    assert filtered_query_result.structured_content["matched_records"] == [
        {
            "dataset_id": "sama-money-supply",
            "source": "sama",
            "record_index": 1,
            "fields": {"period": "2026-02", "value": 2},
        }
    ]

    limited_query_result = await tools["query_dataset"].run(
        {
            "dataset_id": "sama-money-supply",
            "limit": 1,
        }
    )
    assert limited_query_result.structured_content["status"] == "success"
    assert limited_query_result.structured_content["dataset_id"] == "sama-money-supply"
    assert limited_query_result.structured_content["limit"] == 1
    assert limited_query_result.structured_content["total_records_before_filter"] == 2
    assert limited_query_result.structured_content["matched_records"] == [
        {
            "dataset_id": "sama-money-supply",
            "source": "sama",
            "record_index": 0,
            "fields": {"period": "2026-01", "value": 1},
        }
    ]

    search_result = await tools["search_datasets"].run({"query": "money"})
    expected_money_matches = repository.search_datasets("money")
    assert search_result.structured_content["query"] == "money"
    assert search_result.structured_content["normalized_query"] == "money"
    assert search_result.structured_content["status"] == "results"
    assert search_result.structured_content["mode"] == "filtered"
    assert search_result.structured_content["match_count"] == len(expected_money_matches)
    assert [
        match["dataset_id"] for match in search_result.structured_content["matches"]
    ] == [descriptor.dataset_id for descriptor in expected_money_matches]

    all_datasets_result = await tools["search_datasets"].run({"query": "   "})
    assert all_datasets_result.structured_content["query"] == "   "
    assert all_datasets_result.structured_content["normalized_query"] == ""
    assert all_datasets_result.structured_content["status"] == "results"
    assert all_datasets_result.structured_content["mode"] == "all_datasets"
    assert all_datasets_result.structured_content["match_count"] == len(expected_datasets)
    assert [
        match["dataset_id"] for match in all_datasets_result.structured_content["matches"]
    ] == [descriptor.dataset_id for descriptor in expected_datasets]

    preview_result = await tools["preview_dataset"].run(
        {"dataset_id": "sama-money-supply"}
    )
    assert preview_result.structured_content["status"] == "limited"
    assert preview_result.structured_content["dataset_id"] == "sama-money-supply"
    assert preview_result.structured_content["coverage_status"] == "catalog_only"
    assert preview_result.structured_content["resolution_outcome"] == "refresh_then_serve"
    assert preview_result.structured_content["data_origin"] == "live_refresh"
    assert preview_result.structured_content["freshness_status"] == "fresh"
    assert preview_result.structured_content["snapshot_modified_at"] is not None
    assert preview_result.structured_content["failure"] is None
    assert preview_result.structured_content["limitations"] == [
        "dataset_registry_declares_no_current_queryable_support"
    ]
    assert preview_result.structured_content["records"] == []

    data_gov_preview_result = await tools["preview_dataset"].run(
        {"dataset_id": DATA_GOV_SA_DATASET_ID}
    )
    assert data_gov_preview_result.structured_content["status"] == "limited"
    assert data_gov_preview_result.structured_content["dataset_id"] == DATA_GOV_SA_DATASET_ID
    assert data_gov_preview_result.structured_content["coverage_status"] == "catalog_only"
    assert data_gov_preview_result.structured_content["resolution_outcome"] == (
        "refresh_then_serve"
    )
    assert data_gov_preview_result.structured_content["data_origin"] == "live_refresh"
    assert data_gov_preview_result.structured_content["freshness_status"] == "unknown"
    assert data_gov_preview_result.structured_content["snapshot_modified_at"] is not None
    assert data_gov_preview_result.structured_content["failure"] is None
    assert data_gov_preview_result.structured_content["limitations"] == [
        "dataset_registry_declares_no_current_queryable_support"
    ]
    assert data_gov_preview_result.structured_content["records"] == []


@respx.mock
async def test_server_materialize_hot_set_persists_wave_one_safe_subset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pos_route = respx.get(_page_url(POS_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text=_pos_reports_page_html(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    pos_pdf_latest_route = respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=(
                "Weekly Points of Sale Transactions Table 1: By Activities "
                "Value of Transactions: In Thousand "
                "Number of Transactions: In Thousand "
                "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26 "
                "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26 "
                "Total 226,928 16,149,247 223,899 14,793,365 "
                "219,827 12,969,718 246,506 14,707,441 12.1 13.4 "
                "Table 2.1: By Cities"
            ).encode("utf-8"),
            headers={"content-type": "application/pdf"},
        )
    )
    pos_pdf_older_route = respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=(
                "Weekly Points of Sale Transactions Table 1: By Activities "
                "Value of Transactions: In Thousand "
                "Number of Transactions: In Thousand "
                "1 Mar,26 - 7 Mar,26 8 Mar,26 - 14 Mar,26 "
                "15 Mar,26 - 21 Mar,26 22 Mar,26 - 28 Mar,26 "
                "Total 210,100 13,000,000 226,928 16,149,247 "
                "223,899 14,793,365 219,827 12,969,718 -1.8 -12.3 "
                "Table 2.1: By Cities"
            ).encode("utf-8"),
            headers={"content-type": "application/pdf"},
        )
    )
    weekly_money_route = respx.get(_page_url(WEEKLY_MONEY_SUPPLY_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official weekly money supply page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    exchange_landing_route = respx.get(_page_url(EXCHANGE_RATES_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text=_exchange_rates_landing_page_html(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    exchange_search_route = respx.post(_page_url(EXCHANGE_RATES_PAGE_LOCATOR)).mock(
        side_effect=[
            httpx.Response(
                200,
                text=_exchange_rates_results_page_html(
                    viewstate="search-viewstate",
                    rows=[
                        ("US DOLLAR", "3.750000", "21/03/2026"),
                        ("EURO", "4.050000", "21/03/2026"),
                    ],
                    total_results_count=3,
                    pager_links=[("2", "page-2-target")],
                ),
                headers={"content-type": "text/html; charset=utf-8"},
            ),
            httpx.Response(
                200,
                text=_exchange_rates_results_page_html(
                    viewstate="page-2-viewstate",
                    rows=[("JAPANESE YEN", "0.025300", "21/03/2026")],
                    total_results_count=3,
                ),
                headers={"content-type": "text/html; charset=utf-8"},
            ),
        ]
    )
    repo_route = respx.get(_page_url(REPO_RATE_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official repo rate page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    reverse_repo_route = respx.get(_page_url(REVERSE_REPO_RATE_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official reverse repo rate page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    deposits_route = respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"series": "deposits", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    monkeypatch.setattr(
        SAMAConnector,
        "_extract_pdf_text",
        staticmethod(lambda pdf_bytes, *, dataset_id: pdf_bytes.decode("utf-8")),
    )
    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()

    result = await tools["materialize_hot_set"].run({})

    assert result.structured_content["include_optional"] is False
    assert result.structured_content["requested_dataset_count"] == len(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert result.structured_content["materialized_count"] == len(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert result.structured_content["failed_count"] == 0
    assert [
        item["dataset_id"] for item in result.structured_content["results"]
    ] == list(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert pos_route.called
    assert pos_pdf_latest_route.called
    assert pos_pdf_older_route.called
    assert exchange_landing_route.called
    assert exchange_search_route.called
    assert weekly_money_route.called
    assert repo_route.called
    assert reverse_repo_route.called
    assert deposits_route.called

    weekly_download = await tools["download_dataset"].run(
        {"dataset_id": "sama-money-supply-weekly"}
    )
    deposits_download = await tools["download_dataset"].run(
        {"dataset_id": "sama-deposits-core"}
    )
    legacy_download = await tools["download_dataset"].run(
        {"dataset_id": "sama-balance-of-payments"}
    )

    assert weekly_download.structured_content["status"] == "available"
    assert weekly_download.structured_content["local_snapshot_exists"] is True
    assert deposits_download.structured_content["status"] == "available"
    assert deposits_download.structured_content["local_snapshot_exists"] is True
    assert legacy_download.structured_content["status"] == "artifact_missing"
    assert legacy_download.structured_content["local_snapshot_exists"] is False


async def test_server_missing_dataset_lookup_stays_explicit(
    tmp_path: Path,
) -> None:
    app = create_server(_runtime_config(tmp_path))
    tools = await app.get_tools()

    metadata_result = await tools["dataset_metadata"].run({"dataset_id": "missing-dataset"})
    health_result = await tools["dataset_health"].run({"dataset_id": "missing-dataset"})
    download_result = await tools["download_dataset"].run(
        {"dataset_id": "missing-dataset"}
    )
    query_result = await tools["query_dataset"].run({"dataset_id": "missing-dataset"})
    preview_result = await tools["preview_dataset"].run({"dataset_id": "missing-dataset"})

    assert metadata_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "metadata": None,
    }
    assert health_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "health_status": None,
        "coverage_status": None,
        "schema_version": None,
        "caveats": [],
        "known_issues": [],
    }
    assert download_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "reason": "dataset_not_in_registry",
        "local_snapshot_exists": False,
        "source": None,
        "data_origin": None,
        "freshness_status": None,
        "freshness": None,
    }
    assert query_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "source": None,
        "data_origin": None,
        "applied_filters": {},
        "limit": None,
        "total_records_before_filter": None,
        "failure_stage": None,
        "degradation_reason": None,
        "matched_records": [],
        "limitations": [],
        "failure": None,
    }
    assert preview_result.structured_content == {
        "dataset_id": "missing-dataset",
        "status": "missing",
        "coverage_status": "unavailable",
        "resolution_outcome": None,
        "data_origin": None,
        "freshness_status": None,
        "failure_stage": None,
        "degradation_reason": None,
        "snapshot_modified_at": None,
        "resolution_notice": None,
        "records": [],
        "limitations": [],
        "failure": None,
    }


async def test_server_startup_preserves_existing_health_state(tmp_path: Path) -> None:
    runtime_config = _runtime_config(tmp_path)
    updated_health = HealthMetadata(
        dataset_id="sama-money-supply",
        health_status=DatasetHealthStatus.DEGRADED,
    )

    create_server(runtime_config)
    repository = RegistryRepository(runtime_config.registry_path)
    repository.upsert_health(updated_health)

    app = create_server(runtime_config)
    tools = await app.get_tools()
    health_result = await tools["dataset_health"].run({"dataset_id": "sama-money-supply"})

    assert health_result.structured_content["status"] == "found"
    assert health_result.structured_content["health_status"] == "degraded"
    assert repository.get_health("sama-money-supply") == updated_health
    assert repository.get_dataset("sama-money-supply") is not None
    assert repository.get_dataset("sama-money-supply").health_status is (
        DatasetHealthStatus.DEGRADED
    )


async def test_server_lifespan_can_trigger_tier_a_background_refresh(
    tmp_path: Path,
    caplog,
    monkeypatch,
) -> None:
    class RefreshConnectorSpy:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.completed = asyncio.Event()

        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            self.calls.append(dataset_id)
            if len(self.calls) == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS):
                self.completed.set()

            if dataset_id == REPORT_LOCATOR:
                body: object = {"rows": [{"series": "deposits", "value": 1}]}
                content_type = "application/json"
            else:
                body = "<html><body>official sama page</body></html>"
                content_type = "text/html"

            if dataset_id.startswith("/"):
                url = _page_url(dataset_id)
            else:
                url = _report_url()

            return RawPayload(
                source="sama",
                dataset_id=dataset_id,
                content={
                    "url": url,
                    "status_code": 200,
                    "content_type": content_type,
                    "body": body,
                },
            )

    caplog.set_level("INFO")
    connector = RefreshConnectorSpy()
    runtime_config = _runtime_config(tmp_path).model_copy(
        update={
            "tier_a_refresh": TierARefreshConfig(
                enabled=True,
                interval_seconds=3600,
            )
        }
    )

    monkeypatch.setattr(
        server_module,
        "build_default_connector_resolver",
        lambda **_: SourceConnectorResolver({"sama": connector}),
    )

    app = create_server(runtime_config)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")

    async with app._lifespan_manager():
        await asyncio.wait_for(connector.completed.wait(), timeout=1.0)

    assert connector.calls == [
        POS_PAGE_LOCATOR,
        EXCHANGE_RATES_PAGE_LOCATOR,
        WEEKLY_MONEY_SUPPLY_PAGE_LOCATOR,
        REPO_RATE_PAGE_LOCATOR,
        REVERSE_REPO_RATE_PAGE_LOCATOR,
        REPORT_LOCATOR,
    ]
    assert snapshot_store.snapshot_exists("sama", POS_PAGE_LOCATOR)
    assert snapshot_store.snapshot_exists("sama", EXCHANGE_RATES_PAGE_LOCATOR)
    assert snapshot_store.snapshot_exists("sama", WEEKLY_MONEY_SUPPLY_PAGE_LOCATOR)
    assert snapshot_store.snapshot_exists("sama", REPO_RATE_PAGE_LOCATOR)
    assert snapshot_store.snapshot_exists("sama", REVERSE_REPO_RATE_PAGE_LOCATOR)
    assert snapshot_store.snapshot_exists("sama", REPORT_LOCATOR)
    assert get_metrics().get("materialize.requests") == 1
    assert get_metrics().get("materialize.successes") == len(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert get_metrics().get("materialize.failures") == 0
    assert any(
        json.loads(record.getMessage()).get("event") == "tier_a_refresh.loop.enabled"
        for record in caplog.records
    )
    assert any(
        json.loads(record.getMessage()).get("event") == "tier_a_refresh.run.completed"
        for record in caplog.records
    )


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
    assert health_result.structured_content["freshness"]["artifact_present"] is True
    assert "snapshot_path" not in health_result.structured_content["freshness"]


async def test_server_download_tool_can_expose_local_snapshot_availability(
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
    assert download_result.structured_content["freshness"]["status"] == "fresh"
    assert download_result.structured_content["freshness"]["reason"] == (
        "within_expected_window"
    )
    assert download_result.structured_content["freshness"]["artifact_present"] is True
    assert download_result.structured_content["freshness"]["dataset_id"] == (
        "sama-money-supply"
    )
    assert "snapshot_path" not in download_result.structured_content
    assert "snapshot_path" not in download_result.structured_content["freshness"]


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

    preview_result = await tools["preview_dataset"].run(
        {"dataset_id": "sama-money-supply"}
    )

    assert preview_result.structured_content["status"] == "limited"
    assert preview_result.structured_content["coverage_status"] == "catalog_only"
    assert preview_result.structured_content["resolution_outcome"] == "refresh_then_serve"
    assert preview_result.structured_content["data_origin"] == "live_refresh"
    assert preview_result.structured_content["freshness_status"] == "fresh"
    assert preview_result.structured_content["snapshot_modified_at"] is not None
    assert preview_result.structured_content["resolution_notice"] is None
    assert preview_result.structured_content["failure"] is None
    assert preview_result.structured_content["dataset_id"] == "sama-money-supply"
    assert preview_result.structured_content["records"] == []
    assert preview_result.structured_content["limitations"] == [
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization"
    ]


async def test_server_wires_preview_through_connector_resolver(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    resolver_sentinel = object()

    def _resolver_factory(
        *,
        source_config,
    ):
        captured["source_config"] = source_config
        return resolver_sentinel

    class PreviewToolSpy:
        def __init__(self, repository, connector_resolver, **kwargs) -> None:
            captured["connector_resolver"] = connector_resolver

        async def preview_dataset(self, dataset_id: str) -> DatasetPreviewResult:
            return DatasetPreviewResult(
                dataset_id=dataset_id,
                status=PreviewStatus.MISSING,
                coverage_status=DatasetCoverageStatus.UNAVAILABLE,
            )

    monkeypatch.setattr(server_module, "build_default_connector_resolver", _resolver_factory)
    monkeypatch.setattr(server_module, "DatasetPreviewTool", PreviewToolSpy)

    app = server_module.create_server(
        RuntimeConfig(
            registry_path=tmp_path / "registry.sqlite",
            snapshot_dir=tmp_path / "snapshots",
            source={
                "sama_base_url": "https://www.sama.gov.sa",
                "data_gov_sa_base_url": "https://open.data.gov.sa",
                "stats_gov_sa_base_url": "https://www.stats.gov.sa",
                "mof_base_url": "https://www.mof.gov.sa",
            },
        )
    )
    tools = await app.get_tools()
    preview_result = await tools["preview_dataset"].run({"dataset_id": "missing-dataset"})

    assert preview_result.structured_content["status"] == "missing"
    assert preview_result.structured_content["coverage_status"] == "unavailable"
    assert captured["connector_resolver"] is resolver_sentinel
    assert captured["source_config"].sama_base_url == "https://www.sama.gov.sa"
    assert captured["source_config"].data_gov_sa_base_url == "https://open.data.gov.sa"
    assert captured["source_config"].stats_gov_sa_base_url == "https://www.stats.gov.sa"
    assert captured["source_config"].mof_base_url == "https://www.mof.gov.sa"


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    dataset_id: str,
    modified_at: datetime,
    body: object | None = None,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=dataset_id,
        content={
            "url": f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{dataset_id}",
            "status_code": 200,
            "content_type": "application/json",
            "body": body if body is not None else {"rows": []},
        },
    )
    path = store.write_snapshot(payload)
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
