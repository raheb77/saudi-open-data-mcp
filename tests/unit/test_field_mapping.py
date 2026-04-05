"""Unit tests for normalization field mapping."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization import field_mapping as field_mapping_module
from saudi_open_data_mcp.normalization.errors import UnknownNormalizationSourceError
from saudi_open_data_mcp.normalization.field_mapping import (
    FieldMappingResult,
    MappingBodyKind,
    RawResponseMetadata,
    RecordExtractionShape,
    get_field_mapping,
)
from saudi_open_data_mcp.normalization.sama_deposits_core import (
    SAMA_DEPOSITS_CORE_JSON_ROWS_LIMITATION,
)
from saudi_open_data_mcp.normalization.sama_exchange_rates_current import (
    SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION,
)
from saudi_open_data_mcp.normalization.sama_money_supply_weekly import (
    SAMA_MONEY_SUPPLY_WEEKLY_HTML_TABLE_LIMITATION,
)
from saudi_open_data_mcp.normalization.sama_policy_rates import (
    SAMA_POLICY_RATE_HTML_LIMITATION,
)
from saudi_open_data_mcp.normalization.sama_pos_weekly import (
    SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION,
)
from saudi_open_data_mcp.normalization.stats_gov_sa_cpi_headline_monthly import (
    STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
)
from saudi_open_data_mcp.normalization.stats_gov_sa_unemployment_rate_total_quarterly import (
    STATS_GOV_SA_UNEMPLOYMENT_RATE_TOTAL_QUARTERLY_HTML_LIMITATION,
)


def test_json_raw_payload_maps_to_structured_field_mapping_result() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": [{"period": "2026-01", "value": 1}]},
        },
    )

    result = get_field_mapping(raw_payload)

    assert isinstance(result, FieldMappingResult)
    assert result.body_kind is MappingBodyKind.JSON
    assert result.dataset_locator == "report.aspx?cid=55"
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.response_metadata.status_code == 200
    assert result.canonical_fields == {
        "dataset_locator": "report.aspx?cid=55",
        "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
        "response_status_code": 200,
        "response_content_type": "application/json",
        "structured_body": {"rows": [{"period": "2026-01", "value": 1}]},
    }


def test_html_raw_payload_maps_to_limited_explicit_result() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body>official sama page</body></html>",
        },
    )

    result = get_field_mapping(raw_payload)

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.raw_body == "<html><body>official sama page</body></html>"
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
    )
    assert result.canonical_fields == {
        "dataset_locator": "report.aspx?cid=55",
        "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
        "response_status_code": 200,
        "response_content_type": "text/html",
    }


def test_sama_pos_weekly_html_can_map_to_structured_weekly_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/Indices/Pages/POS.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
            """,
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-pos-weekly")

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "week_start_date": "2026-03-01",
                "week_end_date": "2026-03-07",
                "transaction_count": 1234,
                "transaction_value_sar": 246800.0,
                "average_ticket_sar": 200.0,
                "source_locator": "/en-US/Indices/Pages/POS.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
                "source_period_text": "2026-03-01 to 2026-03-07",
                "source_table_title": "Weekly POS Summary",
            }
        ]
    }


def test_sama_pos_weekly_html_without_supported_table_remains_limited() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/Indices/Pages/POS.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body><p>No supported weekly table</p></body></html>",
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-pos-weekly")

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION,
    )


def test_sama_money_supply_weekly_html_can_map_to_structured_weekly_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="sama-money-supply-weekly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "week_end_date": "2026-03-07",
                "monetary_aggregate_code": "m0",
                "monetary_aggregate_name": "M0",
                "amount_sar": 120000.5,
                "source_locator": "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_series_name": "M0",
                "source_week_end_text": "2026-03-07",
                "source_table_title": "Weekly Money Supply",
            },
            {
                "week_end_date": "2026-03-07",
                "monetary_aggregate_code": "m1",
                "monetary_aggregate_name": "M1",
                "amount_sar": 245300.75,
                "source_locator": "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_series_name": "M1",
                "source_week_end_text": "2026-03-07",
                "source_table_title": "Weekly Money Supply",
            },
            {
                "week_end_date": "2026-03-07",
                "monetary_aggregate_code": "m2",
                "monetary_aggregate_name": "M2",
                "amount_sar": 380450.0,
                "source_locator": "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
                "source_series_name": "M2",
                "source_week_end_text": "2026-03-07",
                "source_table_title": "Weekly Money Supply",
            },
        ]
    }


def test_sama_money_supply_weekly_html_without_supported_table_remains_limited() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body><p>No supported money-supply table</p></body></html>",
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="sama-money-supply-weekly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        SAMA_MONEY_SUPPLY_WEEKLY_HTML_TABLE_LIMITATION,
    )


def test_sama_exchange_rates_current_html_can_map_to_structured_quote_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/FinExc/Pages/Currency.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="sama-exchange-rates-current",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "as_of_date": "2026-03-21",
                "currency_code": "USD",
                "currency_name": "US Dollar",
                "quote_currency_code": "SAR",
                "quote_currency_name": "Saudi Riyal",
                "buy_rate_sar": 3.75,
                "sell_rate_sar": 3.76,
                "source_locator": "/en-US/FinExc/Pages/Currency.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "source_currency_text": "USD - US Dollar",
                "source_as_of_text": "As of 2026-03-21",
                "source_table_title": "Current Exchange Rates",
            },
            {
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
            },
        ]
    }


def test_sama_exchange_rates_current_html_without_supported_quote_table_remains_limited() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/FinExc/Pages/Currency.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body><p>Current Exchange Rates</p></body></html>",
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="sama-exchange-rates-current",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION,
    )


def test_sama_repo_rate_html_can_map_to_structured_policy_rate_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <h1>Official Repo Rate</h1>
                  <p>Effective Date: 2026-03-21</p>
                  <p>Rate: 5.25%</p>
                </body></html>
            """,
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-repo-rate")

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "effective_date": "2026-03-21",
                "policy_rate_code": "repo_rate",
                "policy_rate_name": "Official Repo Rate",
                "rate_percent": 5.25,
                "source_locator": "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
                "source_effective_date_text": "Effective Date: 2026-03-21",
                "source_rate_text": "Rate: 5.25%",
            }
        ]
    }


def test_sama_reverse_repo_rate_html_can_map_to_structured_policy_rate_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <h1>Reverse Repo Rate</h1>
                  <p>Effective Date: 2026-03-21</p>
                  <p>Rate: 4.75%</p>
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="sama-reverse-repo-rate",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "effective_date": "2026-03-21",
                "policy_rate_code": "reverse_repo_rate",
                "policy_rate_name": "Reverse Repo Rate",
                "rate_percent": 4.75,
                "source_locator": "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
                "source_url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
                "source_effective_date_text": "Effective Date: 2026-03-21",
                "source_rate_text": "Rate: 4.75%",
            }
        ]
    }


def test_sama_policy_rate_html_without_supported_text_remains_limited() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body><p>Official Repo Rate page</p></body></html>",
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-repo-rate")

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        SAMA_POLICY_RATE_HTML_LIMITATION,
    )


def test_sama_deposits_core_json_can_map_to_structured_monthly_bundle_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
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
            },
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-deposits-core")

    assert result.body_kind is MappingBodyKind.JSON
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "observation_month": "2026-03",
                "deposit_category_code": "demand_deposits",
                "deposit_category_name": "Demand Deposits",
                "related_monetary_aggregate_code": "m1",
                "related_monetary_aggregate_name": "M1",
                "amount_sar": 123400.5,
                "source_locator": "report.aspx?cid=55",
                "source_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
                "source_series_name": "Demand Deposits",
                "source_observation_month_text": "2026-03",
            },
            {
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
            },
            {
                "observation_month": "2026-03",
                "deposit_category_code": "other_quasi_money_deposits",
                "deposit_category_name": "Other Quasi-Money Deposits",
                "related_monetary_aggregate_code": "m3",
                "related_monetary_aggregate_name": "M3",
                "amount_sar": 380500.0,
                "source_locator": "report.aspx?cid=55",
                "source_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
                "source_series_name": "Other Quasi-Money Deposits",
                "source_observation_month_text": "2026-03",
            },
        ]
    }


def test_sama_deposits_core_json_without_supported_component_rows_remains_limited() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": [{"month": "2026-03", "series": "Loans", "value": 10}]},
        },
    )

    result = get_field_mapping(raw_payload, canonical_dataset_id="sama-deposits-core")

    assert result.body_kind is MappingBodyKind.JSON
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "json_body_requires_supported_object_list_shape_for_record_normalization",
        SAMA_DEPOSITS_CORE_JSON_ROWS_LIMITATION,
    )


def test_stats_gov_sa_cpi_headline_monthly_html_can_map_to_structured_monthly_rows() -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=inflation&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "observation_month": "2025-12",
                "inflation_series_code": "headline_cpi_all_items",
                "inflation_series_name": "Headline CPI",
                "release_date": "2026-01-15",
                "yoy_rate_percent": 2.1,
                "mom_rate_percent": 0.1,
                "source_locator": "/en/news?q=inflation&delta=20&start=0",
                "source_url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
                "source_release_url": "https://www.stats.gov.sa/en/w/news/155",
                "source_release_title": (
                    "GASTAT: Saudi Arabia's inflation rate records 2.1% in "
                    "December 2025"
                ),
                "source_release_date_text": "15-01-2026",
                "source_summary_text": (
                    "The annual inflation rate in Saudi Arabia reached 2.1% in "
                    "December 2025, compared to December 2024, while it recorded "
                    "a monthly increase of 0.1% compared to November 2025. It is "
                    "worth noting that the Consumer Price Index (CPI) reflects "
                    "changes in prices paid by consumers."
                ),
            },
            {
                "observation_month": "2025-11",
                "inflation_series_code": "headline_cpi_all_items",
                "inflation_series_name": "Headline CPI",
                "release_date": "2025-12-15",
                "yoy_rate_percent": 1.9,
                "mom_rate_percent": 0.1,
                "source_locator": "/en/news?q=inflation&delta=20&start=0",
                "source_url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
                "source_release_url": "https://www.stats.gov.sa/en/w/news/136",
                "source_release_title": (
                    "GASTAT: Inflation in Saudi Arabia reaches 1.9% in "
                    "November 2025"
                ),
                "source_release_date_text": "15-12-2025",
                "source_summary_text": (
                    "The annual inflation rate of the Consumer Price Index (CPI) in "
                    "Saudi Arabia reached 1.9% in November 2025, compared with "
                    "November 2024, recording relative stability on a monthly basis "
                    "at 0.1% compared with October 2025. It is noteworthy that CPI "
                    "reflects changes in the prices paid by consumers."
                ),
            },
        ]
    }


def test_stats_gov_sa_cpi_headline_monthly_html_without_supported_release_cards_remains_limited(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=inflation&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
    )


def test_stats_gov_sa_cpi_headline_monthly_html_without_parseable_monthly_rate_degrades_to_limited(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=inflation&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <div class="card card-box media-card mb-0">
                    <div class="card-body">
                      <h3 class="card-title fw-700 max-lines-2">
                        GASTAT: Saudi Arabia’s inflation rate records 2.1% in December 2025
                      </h3>
                      <p class="card-date my-3">15-01-2026</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>
                          The annual inflation rate in Saudi Arabia reached 2.1% in December 2025,
                          compared to December 2024. It is worth noting that the Consumer Price
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
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
    )


def test_stats_gov_sa_cpi_headline_monthly_html_without_parseable_yoy_degrades_to_limited(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=inflation&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <div class="card card-box media-card mb-0">
                    <div class="card-body">
                      <h3 class="card-title fw-700 max-lines-2">
                        GASTAT: Saudi Arabia’s inflation rate remains under review
                      </h3>
                      <p class="card-date my-3">15-01-2026</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>
                          The annual inflation rate of the Consumer Price Index (CPI) in Saudi
                          Arabia remained under review this month, while it recorded a monthly
                          increase of 0.1% compared to November 2025.
                        </p>
                      </div>
                    </div>
                    <div class="card-footer-link m-4">
                      <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/155">
                        Read More
                      </a>
                    </div>
                  </div>
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
    )


def test_stats_gov_sa_cpi_headline_monthly_html_with_monthly_decrease_still_extracts(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=inflation&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=inflation&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <div class="card card-box media-card mb-0">
                    <div class="card-body">
                      <h3 class="card-title fw-700 max-lines-2">
                        GASTAT: Saudi Arabia’s inflation rate records 2.1% in December 2025
                      </h3>
                      <p class="card-date my-3">15-01-2026</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>
                          The annual inflation rate in Saudi Arabia reached 2.1% in December 2025,
                          compared to December 2024, while it recorded a monthly decrease of 0.2%
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
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is True
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"]["rows"][0]["mom_rate_percent"] == -0.2


def test_stats_gov_sa_unemployment_rate_total_quarterly_html_can_map_to_structured_quarterly_rows(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=unemployment&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=unemployment&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <div class="card card-box media-card mb-0">
                    <div class="card-body">
                      <h3 class="card-title fw-700 max-lines-2">
                        GASTAT holds a labor-market workshop with regional partners
                      </h3>
                      <p class="card-date my-3">01-10-2025</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>The workshop reviewed labor-market measurement concepts.</p>
                      </div>
                    </div>
                    <div class="card-footer-link m-4">
                      <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/301">
                        Read More
                      </a>
                    </div>
                  </div>
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
                          results, the overall unemployment rate (including Saudis and non-Saudis)
                          stood at 2.8%, while the overall labor force participation rate reached
                          68.2%.
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
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST
    assert result.can_derive_records is True
    assert result.limitations == ()
    assert result.canonical_fields["structured_body"] == {
        "rows": [
            {
                "observation_quarter": "2025-Q1",
                "labor_series_code": "unemployment_rate_total_population_15_plus",
                "labor_series_name": "Unemployment Rate of Total Population (15+)",
                "release_date": "2025-06-29",
                "value_percent": 2.8,
                "source_locator": "/en/news?q=unemployment&delta=20&start=0",
                "source_url": "https://www.stats.gov.sa/en/news?q=unemployment&delta=20&start=0",
                "source_release_url": "https://www.stats.gov.sa/en/w/news/201",
                "source_release_title": (
                    "Unemployment rate of total population reaches 2.8% in Q1 2025"
                ),
                "source_release_date_text": "29-06-2025",
                "source_summary_text": (
                    "The General Authority for Statistics (GASTAT) released today the "
                    "Labor Market Statistics Publication for Q1 of 2025. According to the "
                    "results, the overall unemployment rate (including Saudis and "
                    "non-Saudis) stood at 2.8%, while the overall labor force "
                    "participation rate reached 68.2%."
                ),
            },
            {
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
            },
        ]
    }


def test_stats_gov_sa_unemployment_release_cards_without_supported_rows_remain_limited(
) -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=unemployment&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=unemployment&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <div class="card card-box media-card mb-0">
                    <div class="card-body">
                      <h3 class="card-title fw-700 max-lines-2">
                        GASTAT holds a labor-market workshop with regional partners
                      </h3>
                      <p class="card-date my-3">01-10-2025</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>The workshop reviewed labor-market measurement concepts.</p>
                      </div>
                    </div>
                    <div class="card-footer-link m-4">
                      <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/301">
                        Read More
                      </a>
                    </div>
                  </div>
                </body></html>
            """,
        },
    )

    result = get_field_mapping(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
    )

    assert result.body_kind is MappingBodyKind.HTML
    assert result.can_derive_records is False
    assert result.record_extraction_shape is RecordExtractionShape.NONE
    assert result.limitations == (
        "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        STATS_GOV_SA_UNEMPLOYMENT_RATE_TOTAL_QUARTERLY_HTML_LIMITATION,
    )


def test_field_mapping_dispatches_by_source(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_payload = RawPayload(
        source="source-2",
        dataset_id="dataset-1",
        content={
            "url": "https://example.com/dataset-1",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": []},
        },
    )
    sentinel_result = FieldMappingResult(
        source="source-2",
        dataset_locator="dataset-1",
        response_metadata=RawResponseMetadata(
            url="https://example.com/dataset-1",
            status_code=200,
            content_type="application/json",
        ),
        body_kind=MappingBodyKind.JSON,
        raw_body={"rows": []},
        canonical_fields={
            "dataset_locator": "dataset-1",
            "response_url": "https://example.com/dataset-1",
            "response_status_code": 200,
            "response_content_type": "application/json",
            "structured_body": {"rows": []},
        },
        record_extraction_shape=RecordExtractionShape.ROWS_OBJECT_LIST,
        can_derive_records=True,
        limitations=(),
    )
    seen_sources: list[str] = []

    def _source_two_mapper(
        payload: RawPayload,
        canonical_dataset_id: str | None = None,
    ) -> FieldMappingResult:
        assert canonical_dataset_id is None
        seen_sources.append(payload.source)
        return sentinel_result

    monkeypatch.setitem(
        field_mapping_module._FIELD_MAPPERS,
        "source-2",
        _source_two_mapper,
    )

    result = get_field_mapping(raw_payload)

    assert result is sentinel_result
    assert seen_sources == ["source-2"]


def test_field_mapping_fails_explicitly_for_unsupported_source() -> None:
    raw_payload = RawPayload(
        source="other-source",
        dataset_id="dataset-1",
        content={
            "url": "https://example.com/dataset-1",
            "status_code": 200,
            "content_type": "application/json",
            "body": {},
        },
    )

    with pytest.raises(
        UnknownNormalizationSourceError,
        match="No field mapping registered for source 'other-source'",
    ):
        get_field_mapping(raw_payload)


def test_field_mapping_rejects_incomplete_raw_payload_content() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
        },
    )

    with pytest.raises(ValueError, match="missing required keys: body"):
        get_field_mapping(raw_payload)


def test_field_mapping_rejects_invalid_content_type_body_combinations() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": "<html>not json</html>",
        },
    )

    with pytest.raises(ValueError, match="json content_type requires a dict or list body"):
        get_field_mapping(raw_payload)
