"""Contract tests for the first narrow stats.gov.sa labor dataset."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.contracts import (
    GASTAT_LABOR_CONTRACTS,
    GASTAT_LABOR_DATASET_IDS,
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
    "stats-gov-sa-unemployment-rate-total-quarterly": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.QUARTERLY,
        "primary_key": ("observation_quarter", "labor_series_code"),
        "dimensions": (
            "observation_quarter",
            "labor_series_code",
            "labor_series_name",
            "release_date",
        ),
        "measures": ("value_percent",),
    }
}


def test_gastat_labor_contracts_cover_the_expected_dataset_id() -> None:
    assert GASTAT_LABOR_DATASET_IDS == (
        "stats-gov-sa-unemployment-rate-total-quarterly",
    )


def test_gastat_labor_contract_pins_shape_keys_dimensions_and_measures() -> None:
    contract = get_canonical_dataset_contract("stats-gov-sa-unemployment-rate-total-quarterly")
    expected = EXPECTED_CONTRACT_SUMMARY["stats-gov-sa-unemployment-rate-total-quarterly"]

    assert contract.record_shape is expected["record_shape"]
    assert contract.temporal_granularity is expected["temporal_granularity"]
    assert contract.primary_key == expected["primary_key"]
    assert tuple(field.name for field in contract.dimensions) == expected["dimensions"]
    assert tuple(field.name for field in contract.measures) == expected["measures"]


def test_gastat_labor_contract_uses_backward_safe_schema_defaults() -> None:
    assert tuple(contract.schema_version for contract in GASTAT_LABOR_CONTRACTS) == ("1.0.0",)
    assert all(
        contract.evolution_policy is SchemaEvolutionPolicy.ADDITIVE_WITHIN_MAJOR
        for contract in GASTAT_LABOR_CONTRACTS
    )


def test_gastat_labor_contract_makes_narrow_source_scope_explicit() -> None:
    contract = get_canonical_dataset_contract("stats-gov-sa-unemployment-rate-total-quarterly")

    assert contract.structure_note is not None
    assert "official stats.gov.sa unemployment-filtered news surface" in contract.structure_note
    assert "does not yet claim full labor-market publication tables" in contract.structure_note


def test_gastat_labor_enriched_sample_matches_declared_contract_direction(
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
                        Unemployment rate of total population reaches 2.8% in Q1 2025
                      </h3>
                      <p class="card-date my-3">29-06-2025</p>
                      <div class="card-text max-lines-3 mt-2">
                        <p>
                          The General Authority for Statistics (GASTAT) released today the
                          Labor Market Statistics Publication for Q1 of 2025. According to
                          the results, the overall unemployment rate (including Saudis and
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
                </body></html>
            """,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
    )
    contract = get_canonical_dataset_contract("stats-gov-sa-unemployment-rate-total-quarterly")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.measures)


def test_unknown_dataset_id_has_no_declared_gastat_labor_contract() -> None:
    with pytest.raises(
        ValueError,
        match="No canonical contract is defined for dataset_id 'missing-gastat-labor-dataset'",
    ):
        get_canonical_dataset_contract("missing-gastat-labor-dataset")
