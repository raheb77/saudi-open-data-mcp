"""Contract tests for the narrow stats.gov.sa inflation dataset."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.contracts import (
    GASTAT_INFLATION_CONTRACTS,
    GASTAT_INFLATION_DATASET_IDS,
    CanonicalRecordShape,
    SchemaEvolutionPolicy,
    TemporalGranularity,
    get_canonical_dataset_contract,
)
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)

EXPECTED_CONTRACT_SUMMARY = {
    "stats-gov-sa-cpi-headline-monthly": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.MONTHLY,
        "primary_key": ("observation_month", "inflation_series_code"),
        "dimensions": (
            "observation_month",
            "inflation_series_code",
            "inflation_series_name",
            "release_date",
        ),
        "measures": ("yoy_rate_percent", "mom_rate_percent"),
    }
}


def test_gastat_inflation_contracts_cover_the_expected_dataset_id() -> None:
    assert GASTAT_INFLATION_DATASET_IDS == ("stats-gov-sa-cpi-headline-monthly",)


def test_gastat_inflation_contract_pins_shape_keys_dimensions_and_measures() -> None:
    contract = get_canonical_dataset_contract("stats-gov-sa-cpi-headline-monthly")
    expected = EXPECTED_CONTRACT_SUMMARY["stats-gov-sa-cpi-headline-monthly"]

    assert contract.record_shape is expected["record_shape"]
    assert contract.temporal_granularity is expected["temporal_granularity"]
    assert contract.primary_key == expected["primary_key"]
    assert tuple(field.name for field in contract.dimensions) == expected["dimensions"]
    assert tuple(field.name for field in contract.measures) == expected["measures"]


def test_gastat_inflation_contract_uses_backward_safe_schema_defaults() -> None:
    assert tuple(contract.schema_version for contract in GASTAT_INFLATION_CONTRACTS) == (
        "1.0.0",
    )
    assert all(
        contract.evolution_policy is SchemaEvolutionPolicy.ADDITIVE_WITHIN_MAJOR
        for contract in GASTAT_INFLATION_CONTRACTS
    )


def test_gastat_inflation_contract_makes_narrow_source_scope_explicit() -> None:
    contract = get_canonical_dataset_contract("stats-gov-sa-cpi-headline-monthly")

    assert contract.structure_note is not None
    assert "official stats.gov.sa inflation-filtered news surface" in contract.structure_note
    assert "does not yet claim full CPI category tables" in contract.structure_note


def test_stats_gov_sa_cpi_headline_monthly_enriched_sample_matches_declared_contract_direction(
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
    contract = get_canonical_dataset_contract("stats-gov-sa-cpi-headline-monthly")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.measures)


def test_unknown_dataset_id_has_no_declared_gastat_contract() -> None:
    with pytest.raises(
        ValueError,
        match="No canonical contract is defined for dataset_id 'missing-gastat-dataset'",
    ):
        get_canonical_dataset_contract("missing-gastat-dataset")
