"""Unit tests for Wave 1 hot-set materialization."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.normalization.pipeline import NormalizationPipelineStatus
from saudi_open_data_mcp.observability import get_metrics
from saudi_open_data_mcp.registry.bootstrap import (
    WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.download import DatasetDownloadStatus, DatasetDownloadTool
from saudi_open_data_mcp.tools.materialize import (
    MATERIALIZE_FETCH_FAILURE_MESSAGE,
    HotSetDatasetMaterializationResult,
    HotSetMaterializationFailureStage,
    HotSetMaterializationResult,
    HotSetMaterializationSkipReason,
    HotSetMaterializationStatus,
    HotSetMaterializationTool,
    HotSetTier,
    TierABackgroundRefreshService,
)
from saudi_open_data_mcp.tools.result_metadata import (
    ResultDataOrigin,
)


def _pos_weekly_html() -> str:
    return """
        <html><body>
          <table>
            <caption>Weekly POS Summary</caption>
            <tr>
              <th>Week</th>
              <th>Transactions</th>
              <th>Value (SAR)</th>
            </tr>
            <tr>
              <td>2026-03-01 to 2026-03-07</td>
              <td>1,234</td>
              <td>246,800.00</td>
            </tr>
            <tr>
              <td>2026-03-08 to 2026-03-14</td>
              <td>1,000</td>
              <td>150,000.00</td>
            </tr>
          </table>
        </body></html>
    """


def _pos_weekly_report_bundle_json() -> dict[str, object]:
    return {
        "reports_page_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
        "reports": [
            {
                "report_url": (
                    "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
                    "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
                ),
                "report_text": (
                    "Weekly Points of Sale Transactions\n"
                    "Table 1: By Activities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26 "
                    "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26\n"
                    "Total 226,928 16,149,247 223,899 14,793,365 "
                    "219,827 12,969,718 246,506 14,707,441 12.1 13.4\n"
                    "Table 2.1: By Cities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26 "
                    "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26\n"
                    "Riyadhالرياض69,308 5,328,904 66,217 4,698,782 "
                    "66,115 4,156,638 78,055 4,970,461 18.1 19.6\n"
                    "Table 2.2: By Cities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26 "
                    "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26\n"
                    "Jeddahجدة28,197 2,421,418 26,625 2,174,940 "
                    "25,579 1,814,450 28,230 2,000,003 10.4 10.2\n"
                    "Note: Points of sale transactions by activity for cities are "
                    "available on Saudi Central Bank Portal for Open Data.\n"
                ),
            }
        ],
    }


def _money_supply_weekly_html() -> str:
    return """
        <html><body>
          <table>
            <caption>Weekly Money Supply</caption>
            <tr>
              <th>Week End</th>
              <th>M0</th>
              <th>M1</th>
              <th>M2</th>
            </tr>
            <tr>
              <td>2026-03-07</td>
              <td>120,000.50</td>
              <td>245,300.75</td>
              <td>380,450.00</td>
            </tr>
            <tr>
              <td>2026-03-14</td>
              <td>121,100.00</td>
              <td>246,500.25</td>
              <td>381,800.75</td>
            </tr>
          </table>
        </body></html>
    """


def _deposits_core_json() -> dict[str, list[dict[str, object]]]:
    return {
        "rows": [
            {
                "month": "2026-03",
                "series": "Demand Deposits",
                "value": "123,400.50",
            },
            {
                "month": "2026-03",
                "series": "Time and Savings Deposits",
                "value": "250,000.75",
            },
            {
                "month": "2026-03",
                "series": "Other Quasi-Money Deposits",
                "value": "380,500.00",
            },
        ]
    }


def _exchange_rates_current_bundle_json() -> dict[str, object]:
    return {
        "results_page_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
        "current_date_text": "21/03/2026",
        "total_results_count": 2,
        "pages": [
            {
                "page_number": 1,
                "page_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "body": """
                    <html><body>
                      <select name="ctl00$ctl50$ctl00$ddlCurrencies">
                        <option selected="selected" value="-1">All</option>
                        <option value="USD=">US DOLLAR</option>
                        <option value="EUR=">EURO</option>
                      </select>
                      <span id="ctl00_ctl50_ctl00_lblItemsCount">Number of result is 2</span>
                      <table class="tableCurrency grid" id="ctl00_ctl50_ctl00_dgResults">
                        <tr class="headerstyle gridhead">
                          <td>Currency Against S.R</td>
                          <td>Closing Price</td>
                          <td>Last Updated Date</td>
                        </tr>
                        <tr>
                          <td>US DOLLAR</td><td>3.750000</td><td>21/03/2026</td>
                        </tr>
                        <tr>
                          <td>EURO</td><td>4.050000</td><td>21/03/2026</td>
                        </tr>
                      </table>
                    </body></html>
                """,
            }
        ],
    }


def _repo_rate_html() -> str:
    return """
        <html><body>
          <h1>Repo Rate</h1>
          <nav>Reverse Repo Rate</nav>
          <table summary="Official Repo Rate">
            <tr>
              <th></th>
              <th>Publish Date</th>
              <th>Rate (%)</th>
              <th>Change Points(Bps)</th>
            </tr>
            <tr>
              <td></td><td>10/12/2025</td><td>4.25</td><td>-25</td>
            </tr>
            <tr>
              <td></td><td>29/10/2025</td><td>4.5</td><td>-25</td>
            </tr>
            <tr>
              <td></td><td>17/09/2025</td><td>4.75</td><td>-25</td>
            </tr>
          </table>
        </body></html>
    """


def _reverse_repo_rate_html() -> str:
    return """
        <html><body>
          <h1>Reverse Repo Rate</h1>
          <p>Effective Date: 2026-03-21</p>
          <p>Rate: 4.75%</p>
        </body></html>
    """


class _SAMAConnectorSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        self.calls.append(dataset_id)
        if dataset_id == "report.aspx?cid=55":
            body: object = _deposits_core_json()
            content_type = "application/json"
        elif dataset_id == "/en-US/FinExc/Pages/Currency.aspx":
            body = _exchange_rates_current_bundle_json()
            content_type = "application/json"
        elif dataset_id == "/en-US/Indices/Pages/POS.aspx":
            body = _pos_weekly_report_bundle_json()
            content_type = "application/json"
        elif dataset_id == "/en-US/Indices/Pages/WeeklyMoneySupply.aspx":
            body = _money_supply_weekly_html()
            content_type = "text/html"
        elif dataset_id == "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx":
            body = _repo_rate_html()
            content_type = "text/html"
        elif dataset_id == "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx":
            body = _reverse_repo_rate_html()
            content_type = "text/html"
        else:
            body = "<html><body>official sama page</body></html>"
            content_type = "text/html"

        return RawPayload(
            source="sama",
            dataset_id=dataset_id,
            content={
                "url": _source_url(dataset_id),
                "status_code": 200,
                "content_type": content_type,
                "body": body,
            },
        )


def _source_url(locator: str) -> str:
    if locator.startswith("/"):
        return f"https://www.sama.gov.sa{locator}"
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{locator}"


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.current = start

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def _bootstrapped_repository(tmp_path: Path) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrap_registry(repository)
    return repository


@pytest.mark.asyncio
async def test_materialize_hot_set_persists_wave_one_tier_a_snapshots(tmp_path: Path) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    result = await tool.materialize_hot_set(
        reference_time=datetime.now(tz=UTC),
    )

    assert result.include_optional is False
    assert result.requested_dataset_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert result.materialized_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert result.skipped_count == 0
    assert result.failed_count == 0
    assert [item.dataset_id for item in result.results] == list(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert connector.calls == [
        "/en-US/Indices/Pages/POS.aspx",
        "/en-US/FinExc/Pages/Currency.aspx",
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "report.aspx?cid=55",
    ]

    for dataset_id in WAVE_1_HOT_SET_TIER_A_DATASET_IDS:
        descriptor = repository.get_dataset(dataset_id)
        assert descriptor is not None
        assert snapshot_store.snapshot_exists(descriptor.source, descriptor.source_locator)

    results_by_id = {result.dataset_id: result for result in result.results}
    assert (
        results_by_id["sama-pos-weekly"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-pos-weekly"].data_origin is ResultDataOrigin.LIVE_REFRESH
    assert results_by_id["sama-pos-weekly"].freshness_status is SnapshotFreshnessStatus.FRESH
    assert results_by_id["sama-pos-weekly"].failure_stage is None
    assert results_by_id["sama-pos-weekly"].degradation_reason is None
    assert results_by_id["sama-pos-weekly"].limitations == ()
    assert (
        results_by_id["sama-exchange-rates-current"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-exchange-rates-current"].limitations == ()
    assert (
        results_by_id["sama-deposits-core"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-deposits-core"].limitations == ()
    assert (
        results_by_id["sama-money-supply-weekly"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-money-supply-weekly"].limitations == ()
    assert (
        results_by_id["sama-repo-rate"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-repo-rate"].limitations == ()
    assert (
        results_by_id["sama-reverse-repo-rate"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-reverse-repo-rate"].limitations == ()
    assert results_by_id["sama-deposits-core"].freshness is not None
    assert (
        results_by_id["sama-deposits-core"].freshness.status
        is SnapshotFreshnessStatus.FRESH
    )
    assert results_by_id["sama-repo-rate"].freshness is not None
    assert results_by_id["sama-repo-rate"].freshness.status is SnapshotFreshnessStatus.UNKNOWN
    assert (
        results_by_id["sama-repo-rate"].freshness.reason
        is SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE
    )


@pytest.mark.asyncio
async def test_materialize_hot_set_can_include_optional_pos_by_city_without_refetching(
    tmp_path: Path,
) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    result = await tool.materialize_hot_set(include_optional=True)

    assert result.requested_dataset_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS) + len(
        WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS
    )
    assert result.materialized_count == result.requested_dataset_count - 1
    assert result.skipped_count == 1
    assert result.failed_count == 0
    assert connector.calls.count("/en-US/Indices/Pages/POS.aspx") == 1
    assert set(connector.calls) == {
        "/en-US/Indices/Pages/POS.aspx",
        "/en-US/FinExc/Pages/Currency.aspx",
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "report.aspx?cid=55",
    }

    results_by_id = {result.dataset_id: result for result in result.results}
    assert (
        results_by_id["sama-pos-weekly"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-pos-weekly"].limitations == ()
    assert (
        results_by_id["sama-exchange-rates-current"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-exchange-rates-current"].limitations == ()
    assert (
        results_by_id["sama-money-supply-weekly"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-money-supply-weekly"].limitations == ()
    assert results_by_id["sama-pos-by-city"].tier is HotSetTier.TIER_B_OPTIONAL
    assert results_by_id["sama-pos-by-city"].status is HotSetMaterializationStatus.SKIPPED
    assert (
        results_by_id["sama-pos-by-city"].skip_reason
        is HotSetMaterializationSkipReason.FRESH_SNAPSHOT_REUSED
    )
    assert results_by_id["sama-pos-by-city"].data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert results_by_id["sama-pos-by-city"].local_snapshot_exists is True
    assert (
        results_by_id["sama-pos-by-city"].freshness_status
        is SnapshotFreshnessStatus.FRESH
    )
    assert results_by_id["sama-pos-by-city"].normalization_status is None
    assert results_by_id["sama-pos-by-city"].degradation_reason is None
    assert results_by_id["sama-pos-by-city"].limitations == ()


@pytest.mark.asyncio
async def test_tier_a_materialization_makes_intentional_shared_locator_artifacts_visible(
    tmp_path: Path,
) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    result = await tool.materialize_hot_set(include_optional=False)
    download_tool = DatasetDownloadTool(repository, snapshot_store)
    pos_by_city_download = download_tool.get_dataset_download("sama-pos-by-city")
    money_supply_download = download_tool.get_dataset_download("sama-money-supply")

    assert result.include_optional is False
    assert [item.dataset_id for item in result.results] == list(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert pos_by_city_download.status is DatasetDownloadStatus.AVAILABLE
    assert pos_by_city_download.local_snapshot_exists is True
    assert pos_by_city_download.source == "sama"
    assert money_supply_download.status is DatasetDownloadStatus.AVAILABLE
    assert money_supply_download.local_snapshot_exists is True
    assert money_supply_download.source == "sama"


@pytest.mark.asyncio
async def test_materialize_hot_set_keeps_partial_success_when_one_locator_fails(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class PartiallyFailingConnector(_SAMAConnectorSpy):
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            if dataset_id == "report.aspx?cid=55":
                self.calls.append(dataset_id)
                raise RuntimeError("deposits report fetch failed for testing")
            return await super().fetch_dataset_payload(dataset_id)

    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = PartiallyFailingConnector()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    caplog.set_level(logging.ERROR)
    result = await tool.materialize_hot_set()

    results_by_id = {item.dataset_id: item for item in result.results}
    assert result.requested_dataset_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert result.materialized_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS) - 1
    assert result.skipped_count == 0
    assert result.failed_count == 1
    assert results_by_id["sama-deposits-core"].status is HotSetMaterializationStatus.FAILED
    assert results_by_id["sama-deposits-core"].data_origin is None
    assert (
        results_by_id["sama-deposits-core"].freshness_status
        is SnapshotFreshnessStatus.MISSING
    )
    assert (
        results_by_id["sama-deposits-core"].failure_stage
        is HotSetMaterializationFailureStage.FETCH
    )
    assert results_by_id["sama-deposits-core"].degradation_reason is None
    assert (
        results_by_id["sama-deposits-core"].failure.stage
        is HotSetMaterializationFailureStage.FETCH
    )
    assert results_by_id["sama-deposits-core"].failure is not None
    assert results_by_id["sama-deposits-core"].failure.message == MATERIALIZE_FETCH_FAILURE_MESSAGE
    assert "deposits report fetch failed for testing" not in (
        results_by_id["sama-deposits-core"].failure.message
    )
    assert results_by_id["sama-pos-weekly"].status is HotSetMaterializationStatus.MATERIALIZED
    assert snapshot_store.snapshot_exists("sama", "/en-US/Indices/Pages/POS.aspx")
    assert snapshot_store.snapshot_exists("sama", "/en-US/Indices/Pages/WeeklyMoneySupply.aspx")
    assert snapshot_store.snapshot_exists(
        "sama",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
    )
    assert snapshot_store.snapshot_exists(
        "sama",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
    )
    assert snapshot_store.snapshot_exists("sama", "report.aspx?cid=55") is False
    assert any(
        json.loads(record.getMessage()).get("event") == "materialize.request.failed_internal"
        and json.loads(record.getMessage()).get("dataset_id") == "sama-deposits-core"
        and json.loads(record.getMessage()).get("stage") == "fetch"
        and json.loads(record.getMessage()).get("public_message")
        == MATERIALIZE_FETCH_FAILURE_MESSAGE
        and "deposits report fetch failed for testing"
        in json.loads(record.getMessage()).get("internal_message", "")
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_materialize_hot_set_skips_fresh_snapshots_and_cools_down_unknown_freshness(
    tmp_path: Path,
) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    clock = _FakeClock()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
        time_source=clock,
    )

    first_result = await tool.materialize_hot_set()
    second_result = await tool.materialize_hot_set()

    assert first_result.materialized_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert first_result.skipped_count == 0
    assert second_result.materialized_count == 0
    assert second_result.skipped_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert second_result.failed_count == 0
    assert connector.calls == [
        "/en-US/Indices/Pages/POS.aspx",
        "/en-US/FinExc/Pages/Currency.aspx",
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "report.aspx?cid=55",
    ]

    results_by_id = {item.dataset_id: item for item in second_result.results}
    assert results_by_id["sama-pos-weekly"].status is HotSetMaterializationStatus.SKIPPED
    assert (
        results_by_id["sama-pos-weekly"].skip_reason
        is HotSetMaterializationSkipReason.FRESH_SNAPSHOT_REUSED
    )
    assert results_by_id["sama-pos-weekly"].data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert results_by_id["sama-pos-weekly"].freshness_status is SnapshotFreshnessStatus.FRESH
    assert results_by_id["sama-repo-rate"].status is HotSetMaterializationStatus.SKIPPED
    assert (
        results_by_id["sama-repo-rate"].skip_reason
        is HotSetMaterializationSkipReason.COOLDOWN_ACTIVE
    )
    assert results_by_id["sama-repo-rate"].freshness_status is SnapshotFreshnessStatus.UNKNOWN
    assert results_by_id["sama-reverse-repo-rate"].status is HotSetMaterializationStatus.SKIPPED
    assert (
        results_by_id["sama-reverse-repo-rate"].skip_reason
        is HotSetMaterializationSkipReason.COOLDOWN_ACTIVE
    )


@pytest.mark.asyncio
async def test_materialize_hot_set_does_not_refetch_failed_locator_during_cooldown(
    tmp_path: Path,
) -> None:
    class PartiallyFailingConnector(_SAMAConnectorSpy):
        async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
            if dataset_id == "report.aspx?cid=55":
                self.calls.append(dataset_id)
                raise RuntimeError("deposits report fetch failed for testing")
            return await super().fetch_dataset_payload(dataset_id)

    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = PartiallyFailingConnector()
    clock = _FakeClock()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
        time_source=clock,
    )

    first_result = await tool.materialize_hot_set()
    second_result = await tool.materialize_hot_set()

    assert first_result.failed_count == 1
    assert second_result.materialized_count == 0
    assert second_result.skipped_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS) - 1
    assert second_result.failed_count == 1
    assert connector.calls.count("report.aspx?cid=55") == 1
    deposits_result = {item.dataset_id: item for item in second_result.results}[
        "sama-deposits-core"
    ]
    assert deposits_result.status is HotSetMaterializationStatus.FAILED
    assert deposits_result.failure_stage is HotSetMaterializationFailureStage.FETCH
    assert deposits_result.failure is not None
    assert deposits_result.failure.message == (
        "materialize cooldown active and no reusable local snapshot is available"
    )


@pytest.mark.asyncio
async def test_tier_a_background_refresh_service_runs_tier_a_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class RunnerSpy:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        async def materialize_hot_set(
            self,
            *,
            include_optional: bool = False,
            reference_time: datetime | None = None,
        ) -> HotSetMaterializationResult:
            self.calls.append(include_optional)
            return HotSetMaterializationResult(
                include_optional=include_optional,
                requested_dataset_count=1,
                materialized_count=0,
                failed_count=1,
                results=(
                    HotSetDatasetMaterializationResult.failed(
                        dataset_id="sama-pos-weekly",
                        tier=HotSetTier.TIER_A,
                        stage=HotSetMaterializationFailureStage.FETCH,
                        error=RuntimeError("tier a refresh failed for testing"),
                    ),
                ),
            )

    caplog.set_level(logging.INFO)
    runner = RunnerSpy()
    service = TierABackgroundRefreshService(runner, interval_seconds=3600)

    result = await service.run_once()

    assert runner.calls == [False]
    assert result.include_optional is False
    assert result.failed_count == 1
    assert get_metrics().get("tier_a_refresh.runs") == 1
    assert get_metrics().get("tier_a_refresh.run_failures") == 0
    assert any(
        json.loads(record.getMessage()).get("event") == "tier_a_refresh.run.completed"
        and json.loads(record.getMessage()).get("failed_count") == 1
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tier_a_background_refresh_service_run_forever_logs_failure_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class RunnerSpy:
        def __init__(self) -> None:
            self.calls = 0
            self.second_cycle_started = asyncio.Event()

        async def materialize_hot_set(
            self,
            *,
            include_optional: bool = False,
            reference_time: datetime | None = None,
        ) -> HotSetMaterializationResult:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("tier a refresh cycle failed")

            self.second_cycle_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable after cancellation")

    caplog.set_level(logging.INFO)
    runner = RunnerSpy()
    service = TierABackgroundRefreshService(runner, interval_seconds=0)

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(runner.second_cycle_started.wait(), timeout=1.0)
        assert runner.calls == 2
        assert task.done() is False
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert get_metrics().get("tier_a_refresh.runs") == 2
    assert get_metrics().get("tier_a_refresh.run_failures") == 1
    assert any(
        json.loads(record.getMessage()).get("event") == "tier_a_refresh.run.failed"
        and json.loads(record.getMessage()).get("error_type") == "RuntimeError"
        and json.loads(record.getMessage()).get("message")
        == "tier a refresh cycle failed"
        for record in caplog.records
    )
