"""Unit tests for the normalization pipeline."""

from __future__ import annotations

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization import pipeline as pipeline_module
from saudi_open_data_mcp.normalization.errors import UnknownNormalizationSourceError
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationFailureStage,
    NormalizationPipeline,
    NormalizationPipelineStatus,
)


def test_json_raw_payload_produces_record_derivable_pipeline_result() -> None:
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

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert result.mapping_result is not None
    assert result.validation_result is not None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "report.aspx?cid=55"
    assert result.records[0].source == "sama"
    assert result.records[0].record_index == 0
    assert result.records[0].fields == {"period": "2026-01", "value": 1}


def test_html_raw_payload_produces_limited_pipeline_result() -> None:
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

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.LIMITED
    assert result.failure is None
    assert result.mapping_result is not None
    assert result.validation_result is not None
    assert result.records == ()


def test_sama_pos_weekly_html_with_canonical_dataset_id_produces_queryable_records() -> None:
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

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-pos-weekly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "/en-US/Indices/Pages/POS.aspx"
    assert result.records[0].fields["week_start_date"] == "2026-03-01"
    assert result.records[0].fields["week_end_date"] == "2026-03-07"
    assert result.records[0].fields["transaction_count"] == 1234
    assert result.records[0].fields["transaction_value_sar"] == 246800.0


def test_sama_pos_weekly_json_report_bundle_produces_queryable_records() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/Indices/Pages/POS.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
                "reports_page_url": "https://www.sama.gov.sa/en-US/Indices/Pages/POS.aspx",
                "reports": [
                    {
                        "report_url": (
                            "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
                            "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
                        ),
                        "report_text": (
                            "Weekly Points of Sale Transactions Table 1: By Activities "
                            "Value of Transactions: In Thousand "
                            "Number of Transactions: In Thousand "
                            "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26 "
                            "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26 "
                            "Total 226,928 16,149,247 223,899 14,793,365 "
                            "219,827 12,969,718 246,506 14,707,441 12.1 13.4 "
                            "Table 2.1: By Cities"
                        ),
                    }
                ],
            },
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-pos-weekly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 4
    assert result.records[0].dataset_id == "/en-US/Indices/Pages/POS.aspx"
    assert result.records[-1].fields["week_start_date"] == "2026-03-29"
    assert result.records[-1].fields["week_end_date"] == "2026-04-04"
    assert result.records[-1].fields["transaction_count"] == 246506000
    assert result.records[-1].fields["transaction_value_sar"] == 14707441000.0


def test_sama_money_supply_weekly_html_produces_time_series_records() -> None:
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

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-money-supply-weekly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 3
    assert result.records[0].dataset_id == "/en-US/Indices/Pages/WeeklyMoneySupply.aspx"
    assert result.records[0].fields["week_end_date"] == "2026-03-07"
    assert result.records[0].fields["monetary_aggregate_code"] == "m0"
    assert result.records[0].fields["amount_sar"] == 120000.5


def test_sama_exchange_rates_current_html_produces_queryable_quote_records() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/FinExc/Pages/Currency.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
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
                              <span id="ctl00_ctl50_ctl00_lblItemsCount">
                                Number of result is 2
                              </span>
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
            },
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-exchange-rates-current",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 2
    assert result.records[0].dataset_id == "/en-US/FinExc/Pages/Currency.aspx"
    assert result.records[0].fields["as_of_date"] == "2026-03-21"
    assert result.records[0].fields["currency_code"] == "USD"
    assert result.records[0].fields["quote_currency_code"] == "SAR"
    assert result.records[0].fields["closing_rate_sar"] == 3.75


def test_sama_exchange_rates_current_invalid_quote_value_produces_limited_result() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/FinExc/Pages/Currency.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
                "results_page_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "current_date_text": "21/03/2026",
                "total_results_count": 1,
                "pages": [
                    {
                        "page_number": 1,
                        "page_url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                        "body": """
                            <html><body>
                              <select name="ctl00$ctl50$ctl00$ddlCurrencies">
                                <option selected="selected" value="-1">All</option>
                                <option value="USD=">US DOLLAR</option>
                              </select>
                              <span id="ctl00_ctl50_ctl00_lblItemsCount">
                                Number of result is 1
                              </span>
                              <table class="tableCurrency grid" id="ctl00_ctl50_ctl00_dgResults">
                                <tr class="headerstyle gridhead">
                                  <td>Currency Against S.R</td>
                                  <td>Closing Price</td>
                                  <td>Last Updated Date</td>
                                </tr>
                                <tr>
                                  <td>US DOLLAR</td><td>0</td><td>21/03/2026</td>
                                </tr>
                              </table>
                            </body></html>
                        """,
                    }
                ],
            },
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-exchange-rates-current",
    )

    assert result.status is NormalizationPipelineStatus.LIMITED
    assert result.failure is None
    assert result.mapping_result is not None
    assert result.validation_result is not None
    assert result.records == ()


def test_sama_repo_rate_html_produces_queryable_policy_rate_record() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
                  </table>
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-repo-rate",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 2
    assert result.records[0].dataset_id == "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx"
    assert result.records[0].fields["effective_date"] == "2025-12-10"
    assert result.records[0].fields["policy_rate_code"] == "repo_rate"
    assert result.records[0].fields["rate_percent"] == 4.25
    assert result.records[0].fields["source_publish_date_text"] == "10/12/2025"


def test_sama_reverse_repo_rate_html_produces_queryable_policy_rate_record() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        content={
            "url": "https://www.sama.gov.sa/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
                <html><body>
                  <title>Reverse Repo Rate</title>
                  <nav>Official Repo Rate</nav>
                  <table summary="Reverse Repo Rate">
                    <tr>
                      <th></th>
                      <th>Publish Date</th>
                      <th>Rate (%)</th>
                      <th>Change Points(Bps)</th>
                    </tr>
                    <tr>
                      <td></td><td>10/12/2025</td><td>3.75</td><td>-25</td>
                    </tr>
                    <tr>
                      <td></td><td>29/10/2025</td><td>4</td><td>-25</td>
                    </tr>
                  </table>
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-reverse-repo-rate",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 2
    assert result.records[0].dataset_id == "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx"
    assert result.records[0].fields["effective_date"] == "2025-12-10"
    assert result.records[0].fields["policy_rate_code"] == "reverse_repo_rate"
    assert result.records[0].fields["rate_percent"] == 3.75
    assert result.records[0].fields["source_publish_date_text"] == "10/12/2025"


def test_sama_deposits_core_json_produces_queryable_monthly_bundle_records() -> None:
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

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-deposits-core",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 3
    assert result.records[0].dataset_id == "report.aspx?cid=55"
    assert result.records[0].fields["observation_month"] == "2026-03"
    assert result.records[0].fields["deposit_category_code"] == "demand_deposits"
    assert result.records[0].fields["related_monetary_aggregate_code"] == "m1"
    assert result.records[0].fields["amount_sar"] == 123400.5


def test_stats_gov_sa_cpi_headline_monthly_html_produces_queryable_monthly_records() -> None:
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
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "/en/news?q=inflation&delta=20&start=0"
    assert result.records[0].fields["observation_month"] == "2025-12"
    assert result.records[0].fields["inflation_series_code"] == "headline_cpi_all_items"
    assert result.records[0].fields["release_date"] == "2026-01-15"
    assert result.records[0].fields["yoy_rate_percent"] == 2.1
    assert result.records[0].fields["mom_rate_percent"] == 0.1


def test_stats_gov_sa_unemployment_rate_total_quarterly_html_produces_queryable_quarterly_records(
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

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "/en/news?q=unemployment&delta=20&start=0"
    assert result.records[0].fields["observation_quarter"] == "2025-Q2"
    assert result.records[0].fields["labor_series_code"] == (
        "unemployment_rate_total_population_15_plus"
    )
    assert result.records[0].fields["release_date"] == "2025-09-30"
    assert result.records[0].fields["value_percent"] == 3.2


def test_stats_gov_sa_real_gdp_growth_quarterly_html_produces_queryable_records() -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id="/en/news?q=gdp&delta=20&start=0",
        content={
            "url": "https://www.stats.gov.sa/en/news?q=gdp&delta=20&start=0",
            "status_code": 200,
            "content_type": "text/html",
            "body": """
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
                          Non-oil activities recorded a growth of 4.7%, oil activities
                          grew by 3.8%, while government activities increased by 0.6%.
                        </p>
                      </div>
                    </div>
                    <div class="card-footer-link m-4">
                      <a class="dl-btn dl-btn-default" href="https://www.stats.gov.sa/en/w/news/401">
                        Read More
                      </a>
                    </div>
                  </div>
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-real-gdp-growth-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "/en/news?q=gdp&delta=20&start=0"
    assert result.records[0].fields["observation_quarter"] == "2025-Q2"
    assert result.records[0].fields["gdp_series_code"] == "real_gdp_growth_rate_yoy"
    assert result.records[0].fields["release_date"] == "2025-07-31"
    assert result.records[0].fields["value_percent"] == 3.9


def test_mof_budget_balance_quarterly_json_produces_queryable_records() -> None:
    raw_payload = RawPayload(
        source="mof",
        dataset_id="/en/financialreport/2025/Pages/default.aspx",
        content={
            "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
                "reports_page_url": (
                    "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx"
                ),
                "reports": [
                    {
                        "report_url": (
                            "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
                            "Q2E%202025-%20Final.pdf"
                        ),
                        "report_text": (
                            "Results of Surplus/(Deficit) and financing sources in "
                            "H1 of FY 2025 Item Q1 2025 Q2 2025 Total "
                            "Surplus/(Deficit) (58,701) (34,534) Financing Sources "
                            "Government Reserves 0 0"
                        ),
                    }
                ],
            },
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="mof-budget-balance-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "/en/financialreport/2025/Pages/default.aspx"
    assert result.records[0].fields["observation_quarter"] == "2025-Q2"
    assert result.records[0].fields["fiscal_series_code"] == "headline_budget_balance"
    assert result.records[0].fields["value_sar_bn"] == -34.534


def test_data_gov_sa_json_raw_payload_produces_record_derivable_pipeline_result() -> None:
    raw_payload = RawPayload(
        source="data-gov-sa",
        dataset_id=(
            "/ar/datasets/view/104380ce-60b6-46bc-ba0a-6d5e10ac46cb/"
            "preview/parsed/Census%20Marital%20Status%20CSV.json"
        ),
        content={
            "url": (
                "https://open.data.gov.sa/ar/datasets/view/"
                "104380ce-60b6-46bc-ba0a-6d5e10ac46cb/preview/parsed/"
                "Census%20Marital%20Status%20CSV.json"
            ),
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": [{"status": "single", "count": 10}]},
        },
    )

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.failure is None
    assert result.mapping_result is not None
    assert result.validation_result is not None
    assert len(result.records) == 1
    assert result.records[0].dataset_id == raw_payload.dataset_id
    assert result.records[0].source == "data-gov-sa"
    assert result.records[0].record_index == 0
    assert result.records[0].fields == {"status": "single", "count": 10}


def test_unsupported_json_shape_produces_limited_pipeline_result_without_records() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"summary": {"count": 1}},
        },
    )

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.LIMITED
    assert result.failure is None
    assert result.mapping_result is not None
    assert result.validation_result is not None
    assert result.records == ()


def test_invalid_raw_payload_content_fails_explicitly_at_mapping_stage() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
        },
    )

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.FAILED
    assert result.failure is not None
    assert result.failure.stage is NormalizationFailureStage.MAPPING
    assert result.mapping_result is None
    assert result.validation_result is None


def test_unsupported_source_fails_explicitly_at_mapping_stage() -> None:
    raw_payload = RawPayload(
        source="other-source",
        dataset_id="dataset-1",
        content={
            "url": "https://example.com/dataset-1",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": []},
        },
    )

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.FAILED
    assert result.failure is not None
    assert result.failure.stage is NormalizationFailureStage.MAPPING
    assert result.failure.error_type == UnknownNormalizationSourceError.__name__
    assert "other-source" in result.failure.message
    assert result.mapping_result is None
    assert result.validation_result is None


def test_invalid_validated_state_fails_explicitly_at_validation_stage(
    monkeypatch,
) -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": []},
        },
    )

    def _raise_invalid_mapping(*args, **kwargs):
        raise ValueError("forced validation failure")

    monkeypatch.setattr(pipeline_module, "validate_field_mapping", _raise_invalid_mapping)

    result = NormalizationPipeline().normalize(raw_payload)

    assert result.status is NormalizationPipelineStatus.FAILED
    assert result.failure is not None
    assert result.failure.stage is NormalizationFailureStage.VALIDATION
    assert result.mapping_result is not None
    assert result.validation_result is None
