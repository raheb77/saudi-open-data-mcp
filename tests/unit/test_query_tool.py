"""Unit tests for the dataset query tool."""

from __future__ import annotations

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationFailure,
    NormalizationFailureStage,
    NormalizationPipelineStatus,
    NormalizationResult,
)
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.query import (
    DatasetQueryStatus,
    DatasetQueryTool,
    QueryFailureStage,
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


def _exchange_rates_current_html() -> str:
    return """
        <html><body>
          <p>As of 2026-03-21</p>
          <table>
            <caption>Current Exchange Rates</caption>
            <tr>
              <th>Currency</th>
              <th>Buy Rate (SAR)</th>
              <th>Sell Rate (SAR)</th>
            </tr>
            <tr>
              <td>USD - US Dollar</td>
              <td>3.7500</td>
              <td>3.7600</td>
            </tr>
            <tr>
              <td>EUR - Euro</td>
              <td>4.0500</td>
              <td>4.0600</td>
            </tr>
          </table>
        </body></html>
    """


def _repo_rate_html() -> str:
    return """
        <html><body>
          <h1>Official Repo Rate</h1>
          <p>Effective Date: 2026-03-21</p>
          <p>Rate: 5.25%</p>
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


def test_query_dataset_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetQueryTool(repository, SnapshotStore(tmp_path / "snapshots"))

    result = tool.query_dataset("missing-dataset")

    assert result.status is DatasetQueryStatus.MISSING
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
    assert result.dataset_id == descriptor.dataset_id
    assert result.source == "sama"
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {}
    assert result.limit is None
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
        caveats=(
            "Current canonical extraction covers supported daily quote tables with "
            "an explicit as-of date.",
        ),
        known_issues=("Only supported currency/buy/sell table shapes are normalized.",),
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
                "body": _exchange_rates_current_html(),
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
    assert result.total_records_before_filter == 2
    assert result.applied_filters == {
        "as_of_date": "2026-03-21",
        "currency_code": "EUR",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "as_of_date": "2026-03-21",
        "currency_code": "EUR",
        "currency_name": "Euro",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "buy_rate_sar": 4.05,
        "sell_rate_sar": 4.06,
        "source_locator": "/en-US/FinExc/Pages/Currency.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
        "source_currency_text": "EUR - Euro",
        "source_as_of_text": "As of 2026-03-21",
        "source_table_title": "Current Exchange Rates",
    }


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
            "effective_date": "2026-03-21",
            "policy_rate_code": "repo_rate",
        },
    )

    assert result.status is DatasetQueryStatus.SUCCESS
    assert result.total_records_before_filter == 1
    assert result.applied_filters == {
        "effective_date": "2026-03-21",
        "policy_rate_code": "repo_rate",
    }
    assert len(result.matched_records) == 1
    assert result.matched_records[0].fields == {
        "effective_date": "2026-03-21",
        "policy_rate_code": "repo_rate",
        "policy_rate_name": "Official Repo Rate",
        "rate_percent": 5.25,
        "source_locator": "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "source_url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "source_effective_date_text": "Effective Date: 2026-03-21",
        "source_rate_text": "Rate: 5.25%",
    }


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
    assert result.source == "sama"
    assert result.total_records_before_filter is None
    assert result.matched_records == ()
    assert result.limitations == (
        "json_body_requires_supported_object_list_shape_for_record_normalization",
    )


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
    assert result.source == "sama"
    assert result.matched_records == ()
    assert result.failure is not None
    assert result.failure.stage is QueryFailureStage.NORMALIZATION
    assert result.failure.error_type == "ValueError"
    assert result.failure.message == "forced normalization failure"


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
