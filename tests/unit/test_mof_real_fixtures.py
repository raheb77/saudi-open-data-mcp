"""Regression tests backed by real recorded Ministry of Finance fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)

MOF_PAGE_LOCATOR = "/en/financialreport/2025/Pages/default.aspx"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "mof"
MOF_BUDGET_BALANCE_FIXTURES_DIR = FIXTURES_DIR / "budget_balance_quarterly"


def _fixture_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _page_url(locator: str) -> str:
    return f"https://www.mof.gov.sa{locator}"


def _records_by_field(records, field_name: str) -> dict[str, dict[str, object]]:
    return {record.fields[field_name]: record.fields for record in records}


def test_real_mof_budget_balance_bundle_fixture_normalizes_to_known_good_rows() -> None:
    raw_payload = RawPayload(
        source="mof",
        dataset_id=MOF_PAGE_LOCATOR,
        content={
            "url": _page_url(MOF_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "application/json",
            "body": _fixture_json(
                MOF_BUDGET_BALANCE_FIXTURES_DIR
                / "quarterly-budget-performance-2025-report-bundle.json"
            ),
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="mof-budget-balance-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 2
    records_by_quarter = _records_by_field(result.records, "observation_quarter")

    # Manually verified against the recorded Q2 report snippet:
    # "Item Q1 2025 Q2 2025 Total Surplus/(Deficit) (58,701) (34,534) (93,236)"
    assert records_by_quarter["2025-Q2"] == {
        "observation_quarter": "2025-Q2",
        "fiscal_series_code": "headline_budget_balance",
        "fiscal_series_name": "Headline Budget Balance",
        "value_sar_bn": -34.534,
        "source_locator": MOF_PAGE_LOCATOR,
        "source_url": _page_url(MOF_PAGE_LOCATOR),
        "source_report_url": (
            "https://www.mof.gov.sa/en/financialreport/2025/Documents/"
            "Q2E%202025-%20Final.pdf"
        ),
        "source_release_title": "Quarterly Budget Performance Q2 of FY 2025",
    }
    # Manually verified against the recorded Q4 report snippet:
    # "Item Q1 2025 Q2 2025 Q3 2025 Q4 2025 Total Surplus/(Deficit) ... (94,847)"
    assert records_by_quarter["2025-Q4"] == {
        "observation_quarter": "2025-Q4",
        "fiscal_series_code": "headline_budget_balance",
        "fiscal_series_name": "Headline Budget Balance",
        "value_sar_bn": -94.847,
        "source_locator": MOF_PAGE_LOCATOR,
        "source_url": _page_url(MOF_PAGE_LOCATOR),
        "source_report_url": (
            "https://www.mof.gov.sa/en/financialreport/2025/Documents/Q4%202025-%20En.pdf"
        ),
        "source_release_title": "Quarterly Budget Performance Q4 of FY 2025",
    }

    # The recorded bundle includes Q1 and Q3 reports, but the current supported
    # extraction path correctly fails closed on those shapes instead of inventing rows.
    assert set(records_by_quarter) == {"2025-Q2", "2025-Q4"}
    assert all("release_date" not in fields for fields in records_by_quarter.values())
