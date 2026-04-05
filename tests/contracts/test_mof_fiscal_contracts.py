"""Contract tests for the first narrow Ministry of Finance fiscal dataset."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.contracts import (
    MOF_FISCAL_CONTRACTS,
    MOF_FISCAL_DATASET_IDS,
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
    "mof-budget-balance-quarterly": {
        "record_shape": CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        "temporal_granularity": TemporalGranularity.QUARTERLY,
        "primary_key": ("observation_quarter", "fiscal_series_code"),
        "dimensions": (
            "observation_quarter",
            "fiscal_series_code",
            "fiscal_series_name",
        ),
        "measures": ("value_sar_bn",),
    }
}


def test_mof_fiscal_contracts_cover_the_expected_dataset_id() -> None:
    assert MOF_FISCAL_DATASET_IDS == ("mof-budget-balance-quarterly",)


def test_mof_fiscal_contract_pins_shape_keys_dimensions_and_measures() -> None:
    contract = get_canonical_dataset_contract("mof-budget-balance-quarterly")
    expected = EXPECTED_CONTRACT_SUMMARY["mof-budget-balance-quarterly"]

    assert contract.record_shape is expected["record_shape"]
    assert contract.temporal_granularity is expected["temporal_granularity"]
    assert contract.primary_key == expected["primary_key"]
    assert tuple(field.name for field in contract.dimensions) == expected["dimensions"]
    assert tuple(field.name for field in contract.measures) == expected["measures"]


def test_mof_fiscal_contract_uses_backward_safe_schema_defaults() -> None:
    assert tuple(contract.schema_version for contract in MOF_FISCAL_CONTRACTS) == ("1.0.0",)
    assert all(
        contract.evolution_policy is SchemaEvolutionPolicy.ADDITIVE_WITHIN_MAJOR
        for contract in MOF_FISCAL_CONTRACTS
    )


def test_mof_fiscal_contract_makes_narrow_source_scope_explicit() -> None:
    contract = get_canonical_dataset_contract("mof-budget-balance-quarterly")

    assert contract.structure_note is not None
    assert "official 2025 Ministry of Finance budget performance page" in contract.structure_note
    assert "does not yet claim total revenue" in contract.structure_note


def test_mof_fiscal_enriched_sample_matches_declared_contract_direction() -> None:
    raw_payload = RawPayload(
        source="mof",
        dataset_id="/en/financialreport/2025/Pages/default.aspx",
        content={
            "url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
            "status_code": 200,
            "content_type": "application/json",
            "body": {
                "reports_page_url": "https://www.mof.gov.sa/en/financialreport/2025/Pages/default.aspx",
                "reports": [
                    {
                        "report_url": "https://www.mof.gov.sa/en/financialreport/2025/Documents/Q2E%202025-%20Final.pdf",
                        "report_text": (
                            "Results of Surplus/(Deficit) and financing sources in H1 of FY 2025 "
                            "Item Q1 2025 Q2 2025 Total Surplus/(Deficit) (58,701) (34,534) "
                            "(93,236) Financing Sources Government Reserves 0 0 0"
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
    contract = get_canonical_dataset_contract("mof-budget-balance-quarterly")

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    sample_fields = result.records[0].fields
    assert all(field_name in sample_fields for field_name in contract.primary_key)
    assert all(field.name in sample_fields for field in contract.measures)


def test_unknown_dataset_id_has_no_declared_mof_fiscal_contract() -> None:
    with pytest.raises(
        ValueError,
        match="No canonical contract is defined for dataset_id 'missing-mof-fiscal-dataset'",
    ):
        get_canonical_dataset_contract("missing-mof-fiscal-dataset")
