"""Contract tests for the Wave 3 SAMA high-frequency economic core models."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.contracts import (
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS,
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS,
    CanonicalRecordShape,
    SchemaEvolutionPolicy,
    TemporalGranularity,
    get_canonical_dataset_contract,
)
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)

EXPECTED_CONTRACT_SUMMARIES = {
    "sama-pos-weekly": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.WEEKLY,
        "primary_key": ("week_start_date", "week_end_date"),
        "dimensions": ("week_start_date", "week_end_date"),
        "measures": (
            "transaction_count",
            "transaction_value_sar",
            "average_ticket_sar",
        ),
    },
    "sama-money-supply-weekly": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.WEEKLY,
        "primary_key": ("week_end_date", "monetary_aggregate_code"),
        "dimensions": (
            "week_end_date",
            "monetary_aggregate_code",
            "monetary_aggregate_name",
        ),
        "measures": ("amount_sar",),
    },
    "sama-deposits-core": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.MONTHLY,
        "primary_key": ("observation_month", "deposit_category_code"),
        "dimensions": (
            "observation_month",
            "deposit_category_code",
            "deposit_category_name",
            "related_monetary_aggregate_code",
            "related_monetary_aggregate_name",
        ),
        "measures": ("amount_sar",),
    },
    "sama-exchange-rates-current": {
        "record_shape": CanonicalRecordShape.SNAPSHOT_OBSERVATION,
        "temporal_granularity": TemporalGranularity.DAILY,
        "primary_key": ("as_of_date", "currency_code"),
        "dimensions": (
            "as_of_date",
            "currency_code",
            "currency_name",
            "quote_currency_code",
            "quote_currency_name",
        ),
        "measures": ("closing_rate_sar",),
    },
    "sama-repo-rate": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.EVENT,
        "primary_key": ("effective_date",),
        "dimensions": ("effective_date", "policy_rate_code", "policy_rate_name"),
        "measures": ("rate_percent",),
    },
    "sama-reverse-repo-rate": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.EVENT,
        "primary_key": ("effective_date",),
        "dimensions": ("effective_date", "policy_rate_code", "policy_rate_name"),
        "measures": ("rate_percent",),
    },
}


def test_wave_three_high_frequency_core_contracts_cover_the_expected_dataset_ids() -> None:
    assert SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS == tuple(EXPECTED_CONTRACT_SUMMARIES)


@pytest.mark.parametrize(
    ("dataset_id", "expected"),
    tuple(EXPECTED_CONTRACT_SUMMARIES.items()),
)
def test_high_frequency_core_contracts_pin_shape_keys_dimensions_and_measures(
    dataset_id: str,
    expected: dict[str, object],
) -> None:
    contract = get_canonical_dataset_contract(dataset_id)

    assert contract.record_shape is expected["record_shape"]
    assert contract.temporal_granularity is expected["temporal_granularity"]
    assert contract.primary_key == expected["primary_key"]
    assert tuple(field.name for field in contract.dimensions) == expected["dimensions"]
    assert tuple(field.name for field in contract.measures) == expected["measures"]


def test_high_frequency_core_contracts_use_backward_safe_schema_evolution_defaults() -> None:
    schema_versions = tuple(
        contract.schema_version
        for contract in SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS
    )

    assert schema_versions == (
        "1.0.0",
        "1.0.0",
        "1.0.0",
        "1.0.0",
        "1.0.0",
        "1.0.0",
    )
    assert all(
        contract.evolution_policy is SchemaEvolutionPolicy.ADDITIVE_WITHIN_MAJOR
        for contract in SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS
    )


def test_high_frequency_core_contracts_pin_non_empty_analytical_utility() -> None:
    for contract in SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS:
        assert len(contract.intended_analytical_uses) >= 2


def test_sama_deposits_core_contract_makes_the_current_bundle_decision_explicit() -> None:
    contract = get_canonical_dataset_contract("sama-deposits-core")

    assert contract.structure_note is not None
    assert "bundled canonical dataset" in contract.structure_note
    assert "shared report payload" in contract.structure_note


def test_sama_exchange_rates_current_contract_makes_daily_snapshot_scope_explicit() -> None:
    contract = get_canonical_dataset_contract("sama-exchange-rates-current")

    assert contract.structure_note is not None
    assert "daily published closing-price snapshot" in contract.structure_note
    assert "does not claim buy/sell quotes" in contract.structure_note


@pytest.mark.parametrize(
    ("dataset_id", "expected_phrase"),
    (
        ("sama-repo-rate", "current-page surface"),
        ("sama-reverse-repo-rate", "current-page surface"),
    ),
)
def test_policy_rate_contracts_make_current_page_scope_explicit(
    dataset_id: str,
    expected_phrase: str,
) -> None:
    contract = get_canonical_dataset_contract(dataset_id)

    assert contract.structure_note is not None
    assert expected_phrase in contract.structure_note
    assert "ad-hoc policy updates" in contract.structure_note


def test_unknown_dataset_id_has_no_declared_canonical_contract() -> None:
    with pytest.raises(
        ValueError,
        match="No canonical contract is defined for dataset_id 'missing-dataset'",
    ):
        get_canonical_dataset_contract("missing-dataset")


def test_sama_pos_weekly_enriched_sample_matches_declared_contract_direction() -> None:
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
    contract = get_canonical_dataset_contract("sama-pos-weekly")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.measures)


def test_sama_money_supply_weekly_enriched_sample_matches_declared_contract_direction() -> None:
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
    contract = get_canonical_dataset_contract("sama-money-supply-weekly")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 3
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.measures)


def test_sama_deposits_core_enriched_sample_matches_declared_contract_direction() -> None:
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
    contract = get_canonical_dataset_contract("sama-deposits-core")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 3
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.dimensions)
    assert all(field.name in sample_fields for field in contract.measures)


def test_sama_exchange_rates_current_enriched_sample_matches_declared_contract_direction() -> None:
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
    contract = get_canonical_dataset_contract("sama-exchange-rates-current")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 2
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.dimensions)
    assert all(field.name in sample_fields for field in contract.measures)


@pytest.mark.parametrize(
    ("dataset_id", "locator", "policy_rate_name", "rate_text", "expected_code"),
    (
        (
            "sama-repo-rate",
            "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "Official Repo Rate",
            "5.25%",
            "repo_rate",
        ),
        (
            "sama-reverse-repo-rate",
            "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
            "Reverse Repo Rate",
            "4.75%",
            "reverse_repo_rate",
        ),
    ),
)
def test_policy_rate_enriched_samples_match_declared_contract_direction(
    dataset_id: str,
    locator: str,
    policy_rate_name: str,
    rate_text: str,
    expected_code: str,
) -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id=locator,
        content={
            "url": f"https://www.sama.gov.sa{locator}",
            "status_code": 200,
            "content_type": "text/html",
            "body": f"""
                <html><body>
                  <h1>{policy_rate_name}</h1>
                  <p>Effective Date: 2026-03-21</p>
                  <p>Rate: {rate_text}</p>
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id=dataset_id,
    )
    contract = get_canonical_dataset_contract(dataset_id)

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 1
    sample_fields = result.records[0].fields
    assert sample_fields["policy_rate_code"] == expected_code
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.dimensions)
    assert all(field.name in sample_fields for field in contract.measures)
