"""Unit tests for the hybrid dataset preview tool."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceUnavailableError
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.rate_limit import RateLimitPolicy
from saudi_open_data_mcp.storage.freshness import SnapshotFreshnessStatus
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.preview import (
    LOCAL_PREVIEW_MISS_NOTICE,
    STALE_FALLBACK_NOTICE,
    DatasetPreviewResult,
    DatasetPreviewTool,
    PreviewDataOrigin,
    PreviewFailureStage,
    PreviewResolutionOutcome,
    PreviewStatus,
)

DATASET_ID = "sama-money-supply"
REPORT_LOCATOR = "report.aspx?cid=55"
REFERENCE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class _ConnectorSpy:
    def __init__(self, responses: list[RawPayload | Exception]) -> None:
        self._responses = iter(responses)
        self.calls: list[str] = []

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        self.calls.append(dataset_id)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _repository(
    tmp_path: Path,
    *,
    source: str = "sama",
    dataset_id: str = DATASET_ID,
    source_locator: str = REPORT_LOCATOR,
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY,
) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        DatasetDescriptor(
            dataset_id=dataset_id,
            source=source,
            source_locator=source_locator,
            title="Money Supply",
            description="Official monetary aggregate dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=update_frequency,
            health_status=DatasetHealthStatus.UNKNOWN,
            caveats=("Publication timing may vary by release cycle.",),
            known_issues=("Historical revisions may occur.",),
        )
    )
    return repository


def _snapshot_store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


def _tool(
    tmp_path: Path,
    connector: _ConnectorSpy,
    *,
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY,
    rate_limit_policy: RateLimitPolicy | None = None,
    time_source=None,
) -> DatasetPreviewTool:
    return DatasetPreviewTool(
        _repository(tmp_path, update_frequency=update_frequency),
        SourceConnectorResolver({"sama": connector}),
        snapshot_store=_snapshot_store(tmp_path),
        rate_limit_policy=rate_limit_policy,
        time_source=time_source,
    )


def _payload(
    *,
    source: str = "sama",
    locator: str = REPORT_LOCATOR,
    body: object | None = None,
    content_type: str = "application/json",
) -> RawPayload:
    if source == "stats-gov-sa":
        if not locator.startswith("/"):
            raise ValueError("stats-gov-sa test payloads must use absolute locators")
        url = f"https://www.stats.gov.sa{locator}"
    elif locator.startswith("/"):
        url = f"https://www.sama.gov.sa{locator}"
    else:
        url = f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{locator}"

    return RawPayload(
        source=source,
        dataset_id=locator,
        content={
            "url": url,
            "status_code": 200,
            "content_type": content_type,
            "body": body if body is not None else {"rows": [{"period": "2026-01", "value": 1}]},
        },
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


def _write_snapshot_with_mtime(
    store: SnapshotStore,
    *,
    source: str = "sama",
    locator: str = REPORT_LOCATOR,
    modified_at: datetime,
    body: object | None = None,
    content_type: str = "application/json",
) -> Path:
    path = store.write_snapshot(
        _payload(
            source=source,
            locator=locator,
            body=body,
            content_type=content_type,
        )
    )
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


@pytest.mark.asyncio
async def test_fresh_snapshot_is_served_locally(tmp_path: Path) -> None:
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        modified_at=datetime(2026, 1, 14, 12, 0, tzinfo=UTC),
    )
    connector = _ConnectorSpy([])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert isinstance(result, DatasetPreviewResult)
    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.snapshot_modified_at == datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    assert result.resolution_notice is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == DATASET_ID
    assert connector.calls == []


@pytest.mark.asyncio
async def test_sama_pos_weekly_fresh_snapshot_is_served_as_queryable_html_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-pos-weekly",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        update_frequency=UpdateFrequency.WEEKLY,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="/en-US/Indices/Pages/POS.aspx",
        modified_at=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
        body=_pos_weekly_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-pos-weekly",
        reference_time=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.limitations == ()
    assert result.records[0].fields["week_start_date"] == "2026-03-01"
    assert result.records[0].fields["week_end_date"] == "2026-03-07"
    assert result.records[0].fields["transaction_count"] == 1234
    assert result.records[0].fields["transaction_value_sar"] == 246800.0


@pytest.mark.asyncio
async def test_sama_money_supply_weekly_fresh_snapshot_is_served_as_queryable_html_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-money-supply-weekly",
        source_locator="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        update_frequency=UpdateFrequency.WEEKLY,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        modified_at=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
        body=_money_supply_weekly_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-money-supply-weekly",
        reference_time=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.limitations == ()
    assert len(result.records) == 3
    assert result.records[0].fields["week_end_date"] == "2026-03-07"
    assert result.records[0].fields["monetary_aggregate_code"] == "m0"
    assert result.records[0].fields["amount_sar"] == 120000.5


@pytest.mark.asyncio
async def test_sama_deposits_core_fresh_snapshot_is_served_as_queryable_bundled_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-deposits-core",
        source_locator="report.aspx?cid=55",
        update_frequency=UpdateFrequency.MONTHLY,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="report.aspx?cid=55",
        modified_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        body=_deposits_core_json(),
        content_type="application/json",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-deposits-core",
        reference_time=datetime(2026, 4, 2, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.limitations == ()
    assert len(result.records) == 3
    assert result.records[1].fields["deposit_category_code"] == "time_and_savings_deposits"
    assert result.records[1].fields["related_monetary_aggregate_code"] == "m2"
    assert result.records[1].fields["amount_sar"] == 250000.75


@pytest.mark.asyncio
async def test_sama_exchange_rates_current_fresh_snapshot_is_served_as_queryable_quote_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-exchange-rates-current",
        source_locator="/en-US/FinExc/Pages/Currency.aspx",
        update_frequency=UpdateFrequency.DAILY,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="/en-US/FinExc/Pages/Currency.aspx",
        modified_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        body=_exchange_rates_current_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-exchange-rates-current",
        reference_time=datetime(2026, 3, 21, 18, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.limitations == ()
    assert len(result.records) == 2
    assert result.records[0].fields["currency_code"] == "USD"
    assert result.records[0].fields["quote_currency_code"] == "SAR"
    assert result.records[0].fields["buy_rate_sar"] == 3.75


@pytest.mark.asyncio
async def test_sama_repo_rate_fresh_snapshot_is_served_as_queryable_policy_rate_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-repo-rate",
        source_locator="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        update_frequency=UpdateFrequency.AD_HOC,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        modified_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        body=_repo_rate_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-repo-rate",
        reference_time=datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.UNKNOWN
    assert result.limitations == ()
    assert len(result.records) == 1
    assert result.records[0].fields["policy_rate_code"] == "repo_rate"
    assert result.records[0].fields["rate_percent"] == 5.25


@pytest.mark.asyncio
async def test_sama_reverse_repo_rate_fresh_snapshot_is_served_as_queryable_policy_rate_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        dataset_id="sama-reverse-repo-rate",
        source_locator="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        update_frequency=UpdateFrequency.AD_HOC,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        locator="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        modified_at=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        body=_reverse_repo_rate_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"sama": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "sama-reverse-repo-rate",
        reference_time=datetime(2026, 3, 22, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.UNKNOWN
    assert result.limitations == ()
    assert len(result.records) == 1
    assert result.records[0].fields["policy_rate_code"] == "reverse_repo_rate"
    assert result.records[0].fields["rate_percent"] == 4.75


@pytest.mark.asyncio
async def test_stats_gov_sa_cpi_headline_monthly_fresh_snapshot_is_served_as_queryable_preview(
    tmp_path: Path,
) -> None:
    repository = _repository(
        tmp_path,
        source="stats-gov-sa",
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        source_locator="/en/news?q=inflation&delta=20&start=0",
        update_frequency=UpdateFrequency.MONTHLY,
    )
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        source="stats-gov-sa",
        locator="/en/news?q=inflation&delta=20&start=0",
        modified_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        body=_stats_gov_sa_cpi_headline_monthly_html(),
        content_type="text/html",
    )
    tool = DatasetPreviewTool(
        repository,
        SourceConnectorResolver({"stats-gov-sa": _ConnectorSpy([])}),
        snapshot_store=store,
    )

    result = await tool.preview_dataset(
        "stats-gov-sa-cpi-headline-monthly",
        reference_time=datetime(2026, 1, 16, 12, 0, tzinfo=UTC),
    )

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.limitations == ()
    assert len(result.records) == 2
    assert result.records[0].fields["observation_month"] == "2025-12"
    assert result.records[0].fields["inflation_series_code"] == "headline_cpi_all_items"
    assert result.records[0].fields["yoy_rate_percent"] == 2.1
    assert result.records[0].fields["mom_rate_percent"] == 0.1


@pytest.mark.asyncio
async def test_fresh_snapshot_local_miss_logs_and_refreshes_live(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    snapshot_path = _snapshot_store(tmp_path).snapshot_path("sama", REPORT_LOCATOR)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("not valid raw payload json", encoding="utf-8")
    timestamp = datetime(2026, 1, 14, 12, 0, tzinfo=UTC).timestamp()
    os.utime(snapshot_path, (timestamp, timestamp))

    connector = _ConnectorSpy([_payload()])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.resolution_notice == LOCAL_PREVIEW_MISS_NOTICE
    assert connector.calls == [REPORT_LOCATOR]
    assert any(
        json.loads(record.getMessage()).get("event")
        == "preview.request.local_artifact_unusable"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_stale_snapshot_refreshes_successfully_then_serves_live(tmp_path: Path) -> None:
    store = _snapshot_store(tmp_path)
    _write_snapshot_with_mtime(
        store,
        modified_at=datetime(2025, 12, 1, 0, 0, tzinfo=UTC),
        body={"rows": [{"period": "2025-12", "value": 1}]},
    )
    connector = _ConnectorSpy(
        [_payload(body={"rows": [{"period": "2026-01", "value": 2}]})]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.FRESH
    assert result.snapshot_modified_at is not None
    assert result.records[0].fields == {"period": "2026-01", "value": 2}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_stale_snapshot_failed_refresh_falls_back_to_stale_snapshot(
    tmp_path: Path,
) -> None:
    store = _snapshot_store(tmp_path)
    stale_time = datetime(2025, 12, 1, 0, 0, tzinfo=UTC)
    _write_snapshot_with_mtime(
        store,
        modified_at=stale_time,
        body={"rows": [{"period": "2025-12", "value": 1}]},
    )
    connector = _ConnectorSpy(
        [
            SourceUnavailableError(
                source_name="sama",
                dataset_id=REPORT_LOCATOR,
                message="SAMA source request failed for preview testing",
            )
        ]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
    assert result.data_origin is PreviewDataOrigin.STALE_SNAPSHOT
    assert result.freshness_status is SnapshotFreshnessStatus.STALE
    assert result.snapshot_modified_at == stale_time
    assert result.resolution_notice == STALE_FALLBACK_NOTICE
    assert result.records[0].fields == {"period": "2025-12", "value": 1}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_missing_snapshot_refresh_uses_unknown_freshness_for_unspecified_frequency(
    tmp_path: Path,
) -> None:
    connector = _ConnectorSpy(
        [_payload(body={"rows": [{"status": "single", "count": 10}]})]
    )
    tool = _tool(
        tmp_path,
        connector,
        update_frequency=UpdateFrequency.UNSPECIFIED,
    )

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.RECORD_DERIVABLE
    assert result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert result.freshness_status is SnapshotFreshnessStatus.UNKNOWN
    assert result.snapshot_modified_at is not None
    assert result.records[0].fields == {"status": "single", "count": 10}
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_missing_snapshot_failed_refresh_fails_closed(tmp_path: Path) -> None:
    connector = _ConnectorSpy(
        [
            SourceUnavailableError(
                source_name="sama",
                dataset_id=REPORT_LOCATOR,
                message="SAMA source request failed for preview testing",
            )
        ]
    )
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.FAILED
    assert result.resolution_outcome is PreviewResolutionOutcome.FAIL_CLOSED
    assert result.data_origin is None
    assert result.freshness_status is SnapshotFreshnessStatus.MISSING
    assert result.snapshot_modified_at is None
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "SourceUnavailableError"
    assert result.failure.message == "SAMA source request failed for preview testing"
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_missing_snapshot_write_failure_after_successful_fetch_is_distinguished(
    tmp_path: Path,
) -> None:
    class WriteFailingSnapshotStore(SnapshotStore):
        def write_snapshot(self, payload: RawPayload) -> Path:
            raise OSError("snapshot write failed for preview testing")

    connector = _ConnectorSpy([_payload()])
    tool = DatasetPreviewTool(
        _repository(tmp_path),
        SourceConnectorResolver({"sama": connector}),
        snapshot_store=WriteFailingSnapshotStore(tmp_path / "snapshots"),
    )

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.FAILED
    assert result.resolution_outcome is PreviewResolutionOutcome.FAIL_CLOSED
    assert result.data_origin is None
    assert result.freshness_status is SnapshotFreshnessStatus.MISSING
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.SNAPSHOT
    assert result.failure.error_type == "OSError"
    assert result.failure.message == "snapshot write failed for preview testing"
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_rate_limit_applies_only_to_refresh_path_not_local_reads(
    tmp_path: Path,
) -> None:
    connector = _ConnectorSpy([_payload()])
    tool = _tool(
        tmp_path,
        connector,
        rate_limit_policy=RateLimitPolicy(requests=1, window_seconds=60),
        time_source=lambda: 100.0,
    )

    first_result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)
    second_result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert first_result.status is PreviewStatus.RECORD_DERIVABLE
    assert first_result.resolution_outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
    assert first_result.data_origin is PreviewDataOrigin.LIVE_REFRESH
    assert second_result.status is PreviewStatus.RECORD_DERIVABLE
    assert second_result.resolution_outcome is PreviewResolutionOutcome.SERVE_LOCAL
    assert second_result.data_origin is PreviewDataOrigin.LOCAL_SNAPSHOT
    assert connector.calls == [REPORT_LOCATOR]


@pytest.mark.asyncio
async def test_preview_tool_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    tool = DatasetPreviewTool(
        RegistryRepository(tmp_path / "registry.sqlite"),
        SourceConnectorResolver({}),
        snapshot_store=_snapshot_store(tmp_path),
    )

    result = await tool.preview_dataset("missing-dataset")

    assert result.status is PreviewStatus.MISSING
    assert result.dataset_id == "missing-dataset"
    assert result.resolution_outcome is None
    assert result.data_origin is None
    assert result.freshness_status is None
    assert result.snapshot_modified_at is None
    assert result.records == ()
    assert result.limitations == ()
    assert result.failure is None


@pytest.mark.asyncio
async def test_non_connector_failures_keep_standard_string_representation(
    tmp_path: Path,
) -> None:
    class FormattedError(Exception):
        def __str__(self) -> str:
            return "formatted generic failure"

    connector = _ConnectorSpy([FormattedError()])
    tool = _tool(tmp_path, connector)

    result = await tool.preview_dataset(DATASET_ID, reference_time=REFERENCE_TIME)

    assert result.status is PreviewStatus.FAILED
    assert result.resolution_outcome is PreviewResolutionOutcome.FAIL_CLOSED
    assert result.failure is not None
    assert result.failure.stage is PreviewFailureStage.FETCH
    assert result.failure.error_type == "FormattedError"
    assert result.failure.message == "formatted generic failure"
