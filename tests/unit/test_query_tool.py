"""Unit tests for the dataset query tool."""

from __future__ import annotations

import ast
import json
import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.field_mapping import (
    SAMA_EXCHANGE_RATES_CURRENT_SNAPSHOT_REFRESH_REQUIRED_LIMITATION,
    SNAPSHOT_INCOMPATIBLE_WITH_CURRENT_NORMALIZATION_LIMITATION,
)
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationFailure,
    NormalizationFailureStage,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.query import (
    QUERY_SNAPSHOT_READ_FAILURE_MESSAGE,
    REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_QUERY_LIMITATION,
    DatasetQueryStatus,
    DatasetQueryTool,
    QueryFailureStage,
)
from saudi_open_data_mcp.tools.result_metadata import (
    ObservationRecencyStatus,
    ResultDataOrigin,
    ResultDegradationReason,
)


def _descriptor(dataset_id: str = "sama-money-supply") -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        source_locator=f"report.aspx?cid={sum(dataset_id.encode('utf-8'))}",
        title="Money Supply",
        description="Official monetary aggregate dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Publication timing may vary by release cycle.",),
        known_issues=("Historical revisions may occur.",),
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
            },
            {
                "report_url": (
                    "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
                    "Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf"
                ),
                "report_text": (
                    "Weekly Points of Sale Transactions\n"
                    "Table 1: By Activities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "1 Mar,26 - 7 Mar,26 8 Mar,26 - 14 Mar,26 "
                    "15 Mar,26 - 21 Mar,26 22 Mar,26 - 28 Mar,26\n"
                    "Total 210,100 13,000,000 226,928 16,149,247 "
                    "223,899 14,793,365 219,827 12,969,718 -1.8 -12.3\n"
                    "Table 2.1: By Cities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "1 Mar,26 - 7 Mar,26 8 Mar,26 - 14 Mar,26 "
                    "15 Mar,26 - 21 Mar,26 22 Mar,26 - 28 Mar,26\n"
                    "Riyadhالرياض65,000 4,700,000 69,308 5,328,904 "
                    "66,217 4,698,782 66,115 4,156,638 18.1 19.6\n"
                    "Table 2.2: By Cities\n"
                    "Value of Transactions: In Thousand\n"
                    "Number of Transactions: In Thousand\n"
                    "1 Mar,26 - 7 Mar,26 8 Mar,26 - 14 Mar,26 "
                    "15 Mar,26 - 21 Mar,26 22 Mar,26 - 28 Mar,26\n"
                    "Jeddahجدة27,784 2,340,402 28,197 2,421,418 "
                    "26,625 2,174,940 25,579 1,814,450 10.4 10.2\n"
                    "Note: Points of sale transactions by activity for cities are "
                    "available on Saudi Central Bank Portal for Open Data.\n"
                ),
            },
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


def _stats_gov_sa_cpi_headline_monthly_html() -> str:
    return """
        <html><body>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT holds a workshop on developing the Consumer Price Index (CPI)
              </h3>
              <p class="card-date my-3">01-04-2026</p>
              <div class="card-text max-lines-3 mt-2">
                <p>The workshop reviewed the developmental journey of the CPI.</p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/176">
                Read More
              </a>
            </div>
          </div>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT: Saudi Arabia’s inflation rate records 2.1% in December 2025
              </h3>
              <p class="card-date my-3">15-01-2026</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  The annual inflation rate in Saudi Arabia reached 2.1% in December 2025,
                  compared to December 2024, while it recorded a monthly increase of 0.1%
                  compared to November 2025. It is worth noting that the Consumer Price
                  Index (CPI) reflects changes in prices paid by consumers.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/155">
                Read More
              </a>
            </div>
          </div>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT: Inflation in Saudi Arabia reaches 1.9% in November 2025
              </h3>
              <p class="card-date my-3">15-12-2025</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  The annual inflation rate of the Consumer Price Index (CPI) in Saudi
                  Arabia reached 1.9% in November 2025, compared with November 2024,
                  recording relative stability on a monthly basis at 0.1% compared with
                  October 2025. It is noteworthy that CPI reflects changes in the prices
                  paid by consumers.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/136">
                Read More
              </a>
            </div>
          </div>
        </body></html>
    """


def _stats_gov_sa_unemployment_rate_total_quarterly_html() -> str:
    return """
        <html><body>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                Unemployment rate of total population reaches 2.8% in Q1 2025
              </h3>
              <p class="card-date my-3">29-06-2025</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  The General Authority for Statistics (GASTAT) released today the
                  Labor Market Statistics Publication for Q1 of 2025. According to the
                  results, the overall unemployment rate (including Saudis and
                  non-Saudis) stood at 2.8%, while the overall labor force
                  participation rate reached 68.2%.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/201">
                Read More
              </a>
            </div>
          </div>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT publishes Labor Market Statistics for Q2 of 2025
              </h3>
              <p class="card-date my-3">30-09-2025</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  GASTAT released Labor Market Statistics Publication for Q2 of 2025.
                  Overall labor force participation rate (for Saudis and non-Saudis)
                  reached 67.1%, while the overall unemployment rate (for Saudis and
                  non-Saudis) reached 3.2%.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/202">
                Read More
              </a>
            </div>
          </div>
        </body></html>
    """


def _stats_gov_sa_real_gdp_growth_quarterly_html() -> str:
    return """
        <html><body>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT Real GDP grows by 3.9% in Q2 of 2025
              </h3>
              <p class="card-date my-3">31-07-2025</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  The General Authority for Statistics (GASTAT) released flash
                  estimates for the Gross Domestic Product (GDP) for Q2 of 2025.
                  The real GDP grew by 3.9% compared to the same period in 2024.
                  Non-oil activities recorded a growth of 4.7%, oil activities grew
                  by 3.8%, while government activities increased by 0.6%.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/401">
                Read More
              </a>
            </div>
          </div>
          <div class="card card-box media-card mb-0">
            <div class="card-body">
              <h3 class="card-title fw-700 max-lines-2">
                GASTAT Real GDP contracts by 0.8% in Q4 of 2024
              </h3>
              <p class="card-date my-3">30-01-2025</p>
              <div class="card-text max-lines-3 mt-2">
                <p>
                  The General Authority for Statistics (GASTAT) released flash
                  estimates for the Gross Domestic Product (GDP) for Q4 of 2024.
                  The real GDP contracted by 0.8% compared to the same period in
                  2023, while non-oil activities grew by 4.1%.
                </p>
              </div>
            </div>
            <div class="card-footer-link m-4">
              <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/402">
                Read More
              </a>
            </div>
          </div>
        </body></html>
    """


def _mof_budget_balance_quarterly_body() -> dict[str, object]:
    return {
        "reports_page_url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
        "reports": [
            {
                "report_url": (
                    "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
                    "Q1E%202025-%20Final.pdf"
                ),
                "report_text": (
                    "Results of Surplus/(Deficit) and financing sources in Q1 of FY 2025 "
                    "Item Q1 2025 Total Surplus/(Deficit) (58,701) Financing Sources "
                    "Government Reserves 0"
                ),
            },
            {
                "report_url": (
                    "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
                    "Q2E%202025-%20Final.pdf"
                ),
                "report_text": (
                    "Results of Surplus/(Deficit) and financing sources in H1 of FY 2025 "
                    "Item Q1 2025 Q2 2025 Total Surplus/(Deficit) (58,701) (34,534) "
                    "Financing Sources Government Reserves 0 0"
                ),
            },
        ],
    }


def test_query_dataset_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetQueryTool(repository, SnapshotStore(tmp_path / "snapshots"))

    result = tool.query_dataset("missing-dataset")

    assert result.status is DatasetQueryStatus.MISSING
    assert result.coverage_status is DatasetCoverageStatus.UNAVAILABLE
    assert result.dataset_id == "missing-dataset"
    assert result.source is None
    assert result.total_records_before_filter is None
    assert result.matched_records == ()


def test_query_dataset_returns_explicit_snapshot_missing_result(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SNAPSHOT_MISSING
    assert result.coverage_status is DatasetCoverageStatus.UNAVAILABLE
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == descriptor.source
    assert result.total_records_before_filter is None
    assert result.matched_records == ()


def test_query_dataset_uses_source_locator_not_canonical_dataset_id_for_snapshot_reads(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.dataset_id,
        body={"rows": [{"period": "2026-01", "value": 1}]},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SNAPSHOT_MISSING
    assert result.coverage_status is DatasetCoverageStatus.UNAVAILABLE
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == descriptor.source


def test_query_dataset_returns_local_canonical_records_for_supported_json_snapshot(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={
            "rows": [
                {"period": "2026-01", "value": 1},
                {"period": "2026-02", "value": 2},
            ]
        },
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == "sama"
    assert result.snapshot_id == snapshot_store.snapshot_id(
        descriptor.source,
        descriptor.source_locator,
    )
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {}
    assert result.limit is None
    result_payload = json.dumps(result.model_dump(mode="json"))
    assert "snapshot_path" not in result_payload
    assert str(tmp_path) not in result_payload
    assert len(result.matched_records) == 2
    assert result.matched_records[0].dataset_id == descriptor.dataset_id
    assert result.matched_records[0].record_index == 0
    assert result.matched_records[0].fields == {"period": "2026-01", "value": 1}
    assert result.matched_records[1].dataset_id == descriptor.dataset_id
    assert result.matched_records[1].record_index == 1
    assert result.matched_records[1].fields == {"period": "2026-02", "value": 2}


def test_query_dataset_returns_queryable_canonical_records_for_sama_pos_weekly_html(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-pos-weekly",
        source="sama",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        title="POS Weekly",
        description="Official weekly point-of-sale reporting published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("HTML extraction currently covers the supported weekly summary table only.",),
        known_issues=("City-level tables remain outside this canonical contract.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": _pos_weekly_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"week_end_date": "2026-03-14"},
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {"week_end_date": "2026-03-14"}
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "week_start_date": "2026-03-08",
        "week_end_date": "2026-03-14",
        "transaction_count": 1000,
        "transaction_value_sar": 150000.0,
        "average_ticket_sar": 150.0,
        "source_locator": "/en-US/Indices/Pages/POS.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
        "source_period_text": "2026-03-08 to 2026-03-14",
        "source_table_title": "Weekly POS Summary",
    }


def test_query_dataset_returns_queryable_canonical_records_for_sama_pos_weekly_report_bundle(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-pos-weekly",
        source="sama",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        title="POS Weekly",
        description="Official weekly point-of-sale reporting published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("PDF-backed extraction covers the supported weekly summary table only.",),
        known_issues=("City-level tables remain outside this canonical contract.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": _pos_weekly_report_bundle_json(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"week_end_date": "2026-04-04"},
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 5
    assert result.applied_filters == {"week_end_date": "2026-04-04"}
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "week_start_date": "2026-03-29",
        "week_end_date": "2026-04-04",
        "transaction_count": 246506000,
        "transaction_value_sar": 14707441000.0,
        "average_ticket_sar": 59.66,
        "source_locator": "/en-US/Indices/Pages/POS.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
        "source_period_text": "29 Mar,26 - 04 Apr,26",
        "source_table_title": "Table 1: By Activities",
        "source_report_url": (
            "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
            "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
        ),
        "source_release_title": "Weekly Points of Sale Transactions",
    }


def test_query_dataset_returns_queryable_time_series_records_for_sama_money_supply_weekly_html(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-money-supply-weekly",
        source="sama",
        source_locator="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        title="Money Supply Weekly",
        description="Official weekly money-supply reporting published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("HTML extraction currently covers the supported weekly aggregate table only.",),
        known_issues=("Only recognized monetary aggregate columns are normalized.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": _money_supply_weekly_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "week_end_date": "2026-03-14",
            "monetary_aggregate_code": "m2",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 6
    assert result.applied_filters == {
        "week_end_date": "2026-03-14",
        "monetary_aggregate_code": "m2",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "week_end_date": "2026-03-14",
        "monetary_aggregate_code": "m2",
        "monetary_aggregate_name": "M2",
        "amount_sar": 381800.75,
        "source_locator": "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "source_series_name": "M2",
        "source_week_end_text": "2026-03-14",
        "source_table_title": "Weekly Money Supply",
    }


def test_query_dataset_applies_exact_match_filters(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={
            "rows": [
                {"period": "2026-01", "value": 1},
                {"period": "2026-02", "value": 2},
            ]
        },
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"period": "2026-02"},
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {"period": "2026-02"}
    assert len(result.matched_records) == 1
    assert result.matched_records[0].record_index == 1
    assert result.matched_records[0].fields == {"period": "2026-02", "value": 2}


def test_query_dataset_returns_queryable_canonical_records_for_sama_deposits_core(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-deposits-core",
        source="sama",
        source_locator="report.aspx?cid=55",
        title="Deposits Core Series",
        description="Bundled SAMA core deposit components.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction remains bundled because the source publishes "
            "these components inside one shared monthly report payload.",
        ),
        known_issues=("Only recognized deposit-component rows are normalized.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body=_deposits_core_json(),
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "observation_month": "2026-03",
            "related_monetary_aggregate_code": "m2",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 3
    assert result.applied_filters == {
        "observation_month": "2026-03",
        "related_monetary_aggregate_code": "m2",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "observation_month": "2026-03",
        "deposit_category_code": "time_and_savings_deposits",
        "deposit_category_name": "Time and Savings Deposits",
        "related_monetary_aggregate_code": "m2",
        "related_monetary_aggregate_name": "M2",
        "amount_sar": 250000.75,
        "source_locator": "report.aspx?cid=55",
        "source_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
        "source_series_name": "Time and Savings Deposits",
        "source_observation_month_text": "2026-03",
    }


def test_query_dataset_returns_queryable_canonical_records_for_stats_gov_sa_cpi_headline_monthly(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        source="stats-gov-sa",
        source_locator="/en/news?q=inflation&delta=20&start=0",
        title="CPI Headline Inflation Monthly",
        description="Official headline CPI release cards published by stats.gov.sa.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers supported official headline "
            "CPI release cards only.",
        ),
        known_issues=("Category tables and index values remain outside this first contract.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="stats-gov-sa",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
                "status_code": 200,
                "content_type": "text/html",
                "body": _stats_gov_sa_cpi_headline_monthly_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "observation_month": "2025-11",
            "inflation_series_code": "headline_cpi_all_items",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.source == "stats-gov-sa"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "observation_month": "2025-11",
        "inflation_series_code": "headline_cpi_all_items",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "observation_month": "2025-11",
        "inflation_series_code": "headline_cpi_all_items",
        "inflation_series_name": "Headline CPI",
        "release_date": "2025-12-15",
        "yoy_rate_percent": 1.9,
        "mom_rate_percent": 0.1,
        "source_locator": "/en/news?q=inflation&delta=20&start=0",
        "source_url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
        "source_release_url": "https://www.stats.gov.sa/en/w/news/136",
        "source_release_title": "GASTAT: Inflation in Saudi Arabia reaches 1.9% in November 2025",
        "source_release_date_text": "15-12-2025",
        "source_summary_text": (
            "The annual inflation rate of the Consumer Price Index (CPI) in Saudi "
            "Arabia reached 1.9% in November 2025, compared with November 2024, "
            "recording relative stability on a monthly basis at 0.1% compared with "
            "October 2025. It is noteworthy that CPI reflects changes in the prices "
            "paid by consumers."
        ),
    }


def test_query_dataset_exposes_stale_observation_recency_for_monthly_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        source="stats-gov-sa",
        source_locator="/en/news?q=inflation&delta=20&start=0",
        title="CPI Headline Inflation Monthly",
        description="Official headline CPI release cards published by stats.gov.sa.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers supported official headline "
            "CPI release cards only.",
        ),
        known_issues=("Category tables and index values remain outside this first contract.",),
    )
    tool = DatasetQueryTool(
        repository,
        snapshot_store,
        observation_reference_date_provider=lambda: date(2026, 4, 13),
    )

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="stats-gov-sa",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
                "status_code": 200,
                "content_type": "text/html",
                "body": _stats_gov_sa_cpi_headline_monthly_html(),
            },
        )
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.observation_recency is not None
    assert result.observation_recency.latest_observation == "2025-12"
    assert result.observation_recency.latest_observation_field == "observation_month"
    assert result.observation_recency.status is ObservationRecencyStatus.STALE
    assert (
        result.observation_recency.warning
        == "latest observation 2025-12 is materially behind the expected monthly recency window"
    )


def test_query_dataset_returns_queryable_labor_records_for_stats_gov_sa(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
        source="stats-gov-sa",
        source_locator="/en/news?q=unemployment&delta=20&start=0",
        title="Unemployment Rate Total Population Quarterly",
        description="Official quarterly labor-market release cards published by stats.gov.sa.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers supported total-unemployment release "
            "cards only.",
        ),
        known_issues=(
            "Participation rates, Saudi-only series, and demographic cuts remain outside "
            "this first contract.",
        ),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="stats-gov-sa",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.stats.gov.sa/en/news?q=unemployment&delta=20&start=0",
                "status_code": 200,
                "content_type": "text/html",
                "body": _stats_gov_sa_unemployment_rate_total_quarterly_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "observation_quarter": "2025-Q2",
            "labor_series_code": "unemployment_rate_total_population_15_plus",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.source == "stats-gov-sa"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "observation_quarter": "2025-Q2",
        "labor_series_code": "unemployment_rate_total_population_15_plus",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "observation_quarter": "2025-Q2",
        "labor_series_code": "unemployment_rate_total_population_15_plus",
        "labor_series_name": "Unemployment Rate of Total Population (15+)",
        "release_date": "2025-09-30",
        "value_percent": 3.2,
        "source_locator": "/en/news?q=unemployment&delta=20&start=0",
        "source_url": "https://www.stats.gov.sa/en/news?q=unemployment&delta=20&start=0",
        "source_release_url": "https://www.stats.gov.sa/en/w/news/202",
        "source_release_title": "GASTAT publishes Labor Market Statistics for Q2 of 2025",
        "source_release_date_text": "30-09-2025",
        "source_summary_text": (
            "GASTAT released Labor Market Statistics Publication for Q2 of 2025. "
            "Overall labor force participation rate (for Saudis and non-Saudis) "
            "reached 67.1%, while the overall unemployment rate (for Saudis and "
            "non-Saudis) reached 3.2%."
        ),
    }


def test_query_dataset_returns_queryable_gdp_records_for_stats_gov_sa(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="stats-gov-sa-real-gdp-growth-quarterly",
        source="stats-gov-sa",
        source_locator="/en/news?q=gdp&delta=20&start=0",
        title="GDP Headline Growth Quarterly",
        description="Official quarterly headline real GDP release cards published by stats.gov.sa.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers supported headline real GDP release "
            "cards only.",
        ),
        known_issues=(
            "GDP levels, activity breakdowns, and seasonally adjusted quarterly "
            "growth remain outside this first contract.",
        ),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="stats-gov-sa",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.stats.gov.sa/en/news?q=gdp&delta=20&start=0",
                "status_code": 200,
                "content_type": "text/html",
                "body": _stats_gov_sa_real_gdp_growth_quarterly_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "observation_quarter": "2025-Q2",
            "gdp_series_code": "real_gdp_growth_rate_yoy",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.source == "stats-gov-sa"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "observation_quarter": "2025-Q2",
        "gdp_series_code": "real_gdp_growth_rate_yoy",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "observation_quarter": "2025-Q2",
        "gdp_series_code": "real_gdp_growth_rate_yoy",
        "gdp_series_name": "Real GDP Growth Rate (Year-on-Year)",
        "release_date": "2025-07-31",
        "value_percent": 3.9,
        "source_locator": "/en/news?q=gdp&delta=20&start=0",
        "source_url": "https://www.stats.gov.sa/en/news?q=gdp&delta=20&start=0",
        "source_release_url": "https://www.stats.gov.sa/en/w/news/401",
        "source_release_title": "GASTAT Real GDP grows by 3.9% in Q2 of 2025",
        "source_release_date_text": "31-07-2025",
        "source_summary_text": (
            "The General Authority for Statistics (GASTAT) released flash "
            "estimates for the Gross Domestic Product (GDP) for Q2 of 2025. "
            "The real GDP grew by 3.9% compared to the same period in 2024. "
            "Non-oil activities recorded a growth of 4.7%, oil activities grew "
            "by 3.8%, while government activities increased by 0.6%."
        ),
    }


def test_query_dataset_returns_queryable_mof_budget_balance_records(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="mof-budget-balance-quarterly",
        source="mof",
        source_locator="/en/financialreport/2025/Pages/default.aspx",
        title="Budget Balance Quarterly",
        description="Official headline budget-balance series from MoF quarterly reports.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers one supported top-line budget-balance "
            "series only.",
        ),
        known_issues=(
            "Revenue, expenditure, financing sources, and broader fiscal statements "
            "remain outside this first contract.",
        ),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="mof",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": _mof_budget_balance_quarterly_body(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "observation_quarter": "2025-Q2",
            "fiscal_series_code": "headline_budget_balance",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.source == "mof"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "observation_quarter": "2025-Q2",
        "fiscal_series_code": "headline_budget_balance",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "observation_quarter": "2025-Q2",
        "fiscal_series_code": "headline_budget_balance",
        "fiscal_series_name": "Headline Budget Balance",
        "value_sar_bn": -34.534,
        "source_locator": "/en/financialreport/2025/Pages/default.aspx",
        "source_url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
        "source_report_url": (
            "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
            "Q2E%202025-%20Final.pdf"
        ),
        "source_release_title": "Quarterly Budget Performance Q2 of FY 2025",
    }


def test_query_dataset_exposes_stale_observation_recency_for_quarterly_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="mof-budget-balance-quarterly",
        source="mof",
        source_locator="/en/financialreport/2025/Pages/default.aspx",
        title="Budget Balance Quarterly",
        description="Official headline budget-balance series from MoF quarterly reports.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers one supported top-line budget-balance "
            "series only.",
        ),
        known_issues=(
            "Revenue, expenditure, financing sources, and broader fiscal statements "
            "remain outside this first contract.",
        ),
    )
    tool = DatasetQueryTool(
        repository,
        snapshot_store,
        observation_reference_date_provider=lambda: date(2026, 4, 13),
    )

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="mof",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": _mof_budget_balance_quarterly_body(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"observation_quarter": "2025-Q2"},
    )

    assert result.observation_recency is not None
    assert result.observation_recency.latest_observation == "2025-Q2"
    assert result.observation_recency.latest_observation_field == "observation_quarter"
    assert result.observation_recency.status is ObservationRecencyStatus.STALE
    assert (
        result.observation_recency.warning
        == "latest observation 2025-Q2 is materially behind the expected quarterly recency window"
    )


def test_query_dataset_returns_queryable_canonical_records_for_sama_exchange_rates_current(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-exchange-rates-current",
        source="sama",
        source_locator="/en-US/FinExc/Pages/Currency.aspx",
        title="Current Exchange Rates",
        description="Daily current exchange-rate quotes.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.DAILY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=(
            "Current canonical extraction covers supported latest-date closing-price "
            "pages from the official SAMA currency surface.",
        ),
        known_issues=(
            "Only supported paginated latest-date rows with resolvable currency codes "
            "are normalized.",
        ),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": _exchange_rates_current_bundle_json(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "as_of_date": "2026-03-21",
            "currency_code": "EUR",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "as_of_date": "2026-03-21",
        "currency_code": "EUR",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "as_of_date": "2026-03-21",
        "currency_code": "EUR",
        "currency_name": "EURO",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "closing_rate_sar": 4.05,
        "source_locator": "/en-US/FinExc/Pages/Currency.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
        "source_currency_text": "EURO",
        "source_last_updated_date_text": "21/03/2026",
        "source_page_number": 1,
    }


def test_query_dataset_returns_explicitly_limited_for_legacy_exchange_rates_snapshot(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-exchange-rates-current",
        source="sama",
        source_locator="/en-US/FinExc/Pages/Currency.aspx",
        title="Current Exchange Rates",
        description="Daily current exchange-rate quotes.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.DAILY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Legacy raw snapshots may require a live refresh.",),
        known_issues=("Only the current JSON page-bundle contract is queryable.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": "<html><body><h1>Currency Rate</h1></body></html>",
            },
        )
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.LIMITED
    assert result.coverage_status is DatasetCoverageStatus.LIMITED
    assert result.data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert result.degradation_reason is ResultDegradationReason.NORMALIZATION_LIMITED
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        SNAPSHOT_INCOMPATIBLE_WITH_CURRENT_NORMALIZATION_LIMITATION,
        SAMA_EXCHANGE_RATES_CURRENT_SNAPSHOT_REFRESH_REQUIRED_LIMITATION,
    )


def test_query_dataset_returns_queryable_canonical_records_for_sama_repo_rate(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-repo-rate",
        source="sama",
        source_locator="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        title="Official Repo Rate",
        description="Official SAMA repo rate page.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.AD_HOC,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Current canonical extraction covers supported published repo-rate rows.",),
        known_issues=("Only supported Publish Date / Rate (%) table layouts are normalized.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": _repo_rate_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "effective_date": "2025-10-29",
            "policy_rate_code": "repo_rate",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 3
    assert result.applied_filters == {
        "effective_date": "2025-10-29",
        "policy_rate_code": "repo_rate",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "effective_date": "2025-10-29",
        "policy_rate_code": "repo_rate",
        "policy_rate_name": "Official Repo Rate",
        "rate_percent": 4.5,
        "source_locator": "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "source_publish_date_text": "29/10/2025",
        "source_rate_text": "4.5",
        "source_change_points_text": "-25",
    }


def test_query_dataset_marks_observation_recency_not_applicable_for_ad_hoc_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-repo-rate",
        source="sama",
        source_locator="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        title="Official Repo Rate",
        description="Official SAMA repo rate page.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.AD_HOC,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Current canonical extraction covers supported published repo-rate rows.",),
        known_issues=("Only supported Publish Date / Rate (%) table layouts are normalized.",),
    )
    tool = DatasetQueryTool(
        repository,
        snapshot_store,
        observation_reference_date_provider=lambda: date(2026, 4, 13),
    )

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": _repo_rate_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={"effective_date": "2025-10-29"},
    )

    assert result.observation_recency is not None
    assert result.observation_recency.latest_observation == "2025-12-10"
    assert result.observation_recency.latest_observation_field == "effective_date"
    assert result.observation_recency.status is ObservationRecencyStatus.NOT_APPLICABLE
    assert result.observation_recency.warning is None


def test_query_dataset_returns_queryable_canonical_records_for_sama_reverse_repo_rate(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-reverse-repo-rate",
        source="sama",
        source_locator="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        title="Reverse Repo Rate",
        description="Official SAMA reverse repo rate page.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.AD_HOC,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Current canonical extraction covers supported effective-date and rate text.",),
        known_issues=("Only supported page text or simple table layouts are normalized.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
                "status_code": 200,
                "content_type": "text/html",
                "body": _reverse_repo_rate_html(),
            },
        )
    )

    result = tool.query_dataset(
        descriptor.dataset_id,
        filters={
            "effective_date": "2026-03-21",
            "policy_rate_code": "reverse_repo_rate",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 1
    assert result.applied_filters == {
        "effective_date": "2026-03-21",
        "policy_rate_code": "reverse_repo_rate",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "effective_date": "2026-03-21",
        "policy_rate_code": "reverse_repo_rate",
        "policy_rate_name": "Reverse Repo Rate",
        "rate_percent": 4.75,
        "source_locator": "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "source_effective_date_text": "Effective Date: 2026-03-21",
        "source_rate_text": "Rate: 4.75%",
    }


def test_query_dataset_applies_limit_deterministically(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body=[
            {"period": "2026-01", "value": 1},
            {"period": "2026-02", "value": 2},
            {"period": "2026-03", "value": 3},
        ],
    )

    result = tool.query_dataset(descriptor.dataset_id, limit=2)

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.total_records_before_filter == 3
    assert result.limit == 2
    assert [record.record_index for record in result.matched_records] == [0, 1]


def test_query_dataset_returns_explicit_limited_result_for_unsupported_json_shape(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={"summary": {"count": 2}},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.LIMITED
    assert result.coverage_status is DatasetCoverageStatus.LIMITED
    assert result.source == "sama"
    assert result.data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert result.total_records_before_filter is None
    assert result.failure_stage is None
    assert result.degradation_reason is ResultDegradationReason.NORMALIZATION_LIMITED
    assert result.matched_records == ()
    assert result.limitations == (
        "json_body_requires_supported_object_list_shape_for_record_normalization",
    )


def test_query_dataset_returns_queryable_city_records_for_sama_pos_by_city_bundle(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = DatasetDescriptor(
        dataset_id="sama-pos-by-city",
        source="sama",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        title="POS by City",
        description="Official weekly point-of-sale reporting by city published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("The shared POS report bundle publishes supported city tables.",),
        known_issues=("Only supported rows from Table 2.1 and Table 2.2 are normalized.",),
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    snapshot_store.write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=descriptor.source_locator,
            content={
                "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": _pos_weekly_report_bundle_json(),
            },
        )
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.coverage_status is DatasetCoverageStatus.QUERYABLE
    assert result.source == "sama"
    assert result.data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert result.total_records_before_filter == 10
    assert result.failure_stage is None
    assert result.degradation_reason is None
    assert result.limitations == ()
    assert len(result.matched_records) == 10
    assert result.matched_records[-1].fields == {
        "week_start_date": "2026-03-29",
        "week_end_date": "2026-04-04",
        "city_name": "Riyadh",
        "city_name_ar": "الرياض",
        "transaction_count": 78055000,
        "transaction_value_sar": 4970461000.0,
        "source_locator": "/en-US/Indices/Pages/POS.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
        "source_report_url": (
            "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
            "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
        ),
        "source_period_text": "29 Mar,26 - 04 Apr,26",
        "source_table_title": "Table 2.1: By Cities",
        "source_release_title": "Weekly Points of Sale Transactions",
    }


def test_query_dataset_returns_explicit_failed_result_for_failed_normalization(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor()

    class FailedPipeline:
        def normalize(
            self,
            raw_payload: RawPayload,
            *,
            canonical_dataset_id: str | None = None,
        ) -> NormalizationResult:
            assert canonical_dataset_id == descriptor.dataset_id
            return NormalizationResult(
                dataset_id=raw_payload.dataset_id,
                status=NormalizationPipelineStatus.FAILED,
                failure=NormalizationFailure(
                    stage=NormalizationFailureStage.VALIDATION,
                    error_type="ValueError",
                    message="forced normalization failure",
                ),
            )

    tool = DatasetQueryTool(
        repository,
        snapshot_store,
        normalization_pipeline=FailedPipeline(),
    )

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={"rows": [{"period": "2026-01", "value": 1}]},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.FAILED
    assert result.coverage_status is DatasetCoverageStatus.UNAVAILABLE
    assert result.source == "sama"
    assert result.data_origin is ResultDataOrigin.LOCAL_SNAPSHOT
    assert result.matched_records == ()
    assert result.failure_stage is QueryFailureStage.NORMALIZATION
    assert result.degradation_reason is None
    assert result.failure is not None
    assert result.failure.stage is QueryFailureStage.NORMALIZATION
    assert result.failure.error_type == "ValueError"
    assert result.failure.message == "forced normalization failure"


def test_query_dataset_sanitizes_snapshot_read_failure_but_logs_internal_detail(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenSnapshotStore(SnapshotStore):
        def read_snapshot(self, source: str, dataset_id: str) -> RawPayload:
            del source, dataset_id
            raise OSError(
                "permission denied while reading "
                "/private/var/tmp/saudi-open-data-mcp/secret-snapshot.json"
            )

    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor()
    repository.upsert_dataset(descriptor)
    tool = DatasetQueryTool(
        repository,
        BrokenSnapshotStore(tmp_path / "snapshots"),
    )

    caplog.set_level(logging.ERROR)
    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.FAILED
    assert result.failure_stage is QueryFailureStage.SNAPSHOT_READ
    assert result.failure is not None
    assert result.failure.error_type == "OSError"
    assert result.failure.message == QUERY_SNAPSHOT_READ_FAILURE_MESSAGE
    assert "/private/var/tmp/saudi-open-data-mcp/secret-snapshot.json" not in result.failure.message
    assert any(
        json.loads(record.getMessage()).get("event") == "query.request.failed_internal"
        and json.loads(record.getMessage()).get("dataset_id") == descriptor.dataset_id
        and json.loads(record.getMessage()).get("stage") == "snapshot_read"
        and json.loads(record.getMessage()).get("public_message")
        == QUERY_SNAPSHOT_READ_FAILURE_MESSAGE
        and "/private/var/tmp/saudi-open-data-mcp/secret-snapshot.json"
        in json.loads(record.getMessage()).get("internal_message", "")
        for record in caplog.records
    )


def test_query_dataset_respects_registry_coverage_for_catalog_only_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    descriptor = _descriptor().model_copy(
        update={"coverage_status": DatasetCoverageStatus.CATALOG_ONLY}
    )
    tool = DatasetQueryTool(repository, snapshot_store)

    repository.upsert_dataset(descriptor)
    _write_snapshot(
        snapshot_store,
        snapshot_dataset_id=descriptor.source_locator,
        body={"rows": [{"period": "2026-01", "value": 1}]},
    )

    result = tool.query_dataset(descriptor.dataset_id)

    assert result.status is DatasetQueryStatus.LIMITED
    assert result.coverage_status is DatasetCoverageStatus.CATALOG_ONLY
    assert result.total_records_before_filter is None
    assert result.matched_records == ()
    assert result.limitations == (
        REGISTRY_COVERAGE_RESTRICTS_QUERYABLE_QUERY_LIMITATION,
    )


def test_query_tool_module_does_not_import_connectors_directly() -> None:
    project_root = Path(__file__).resolve().parents[2]
    query_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "query.py"
    tree = ast.parse(query_module.read_text(), filename=str(query_module))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "connectors" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "connectors" not in alias.name


def _write_snapshot(
    store: SnapshotStore,
    *,
    snapshot_dataset_id: str,
    body: object,
) -> Path:
    payload = RawPayload(
        source="sama",
        dataset_id=snapshot_dataset_id,
        content={
            "url": (
                "https://www.sama.gov.sa/en-US/EconomicReports/Pages/"
                f"{snapshot_dataset_id}"
            ),
            "status_code": 200,
            "content_type": "application/json",
            "body": body,
        },
    )
    path = store.write_snapshot(payload)
    timestamp = datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path
