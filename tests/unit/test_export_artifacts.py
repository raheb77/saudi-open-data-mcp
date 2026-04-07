"""Unit tests for explicit governed query-result export artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from saudi_open_data_mcp.normalization.pipeline import CanonicalRecord
from saudi_open_data_mcp.tools.export_artifacts import (
    render_query_result_excel_artifact,
    render_query_result_pdf_artifact,
)
from saudi_open_data_mcp.tools.query import DatasetQueryResult
from saudi_open_data_mcp.tools.result_metadata import ResultDataOrigin


def _success_result() -> DatasetQueryResult:
    return DatasetQueryResult(
        dataset_id="mof-budget-balance-quarterly",
        status="success",
        source="mof",
        data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
        applied_filters={"observation_quarter": "2025-Q4"},
        limit=10,
        total_records_before_filter=2,
        matched_records=(
            CanonicalRecord(
                dataset_id="mof-budget-balance-quarterly",
                source="mof",
                record_index=0,
                fields={
                    "observation_quarter": "2025-Q4",
                    "fiscal_series_code": "headline_budget_balance",
                    "value_sar_bn": -28.4,
                },
            ),
            CanonicalRecord(
                dataset_id="mof-budget-balance-quarterly",
                source="mof",
                record_index=1,
                fields={
                    "observation_quarter": "2025-Q3",
                    "fiscal_series_code": "headline_budget_balance",
                    "value_sar_bn": -15.2,
                },
            ),
        ),
    )


def test_render_query_result_excel_artifact_includes_metadata_and_records() -> None:
    artifact = render_query_result_excel_artifact(
        _success_result(),
        freshness_status="fresh",
        exported_at=datetime(2026, 4, 7, 8, 30, tzinfo=UTC),
    )

    rendered = artifact.decode("utf-8")

    assert "<?mso-application progid=\"Excel.Sheet\"?>" in rendered
    assert 'Worksheet ss:Name="Metadata"' in rendered
    assert 'Worksheet ss:Name="Records"' in rendered
    assert "mof-budget-balance-quarterly" in rendered
    assert "Ministry of Finance (MoF) [mof]" in rendered
    assert "headline_budget_balance" in rendered
    assert "fresh" in rendered


def test_render_query_result_excel_artifact_cleans_empty_filter_presentation() -> None:
    result = DatasetQueryResult(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        status="limited",
        source="stats-gov-sa",
        data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
        applied_filters={},
        limit=None,
        degradation_reason="normalization_limited",
        limitations=(
            "stats_gov_sa_cpi_headline_monthly_html_requires_supported_release_cards",
        ),
    )

    artifact = render_query_result_excel_artifact(
        result,
        freshness_status="stale",
        exported_at=datetime(2026, 4, 7, 8, 30, tzinfo=UTC),
    )
    rendered = artifact.decode("utf-8")

    assert "General Authority for Statistics (GASTAT) [stats-gov-sa]" in rendered
    assert "applied_filters_json" in rendered
    assert ">none<" in rendered


def test_render_query_result_pdf_artifact_keeps_degraded_status_visible() -> None:
    result = DatasetQueryResult(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        status="limited",
        source="stats-gov-sa",
        data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
        applied_filters={},
        limit=None,
        degradation_reason="normalization_limited",
        limitations=(
            "stats_gov_sa_cpi_headline_monthly_html_requires_supported_release_cards",
        ),
    )

    artifact = render_query_result_pdf_artifact(
        result,
        freshness_status="stale",
        exported_at=datetime(2026, 4, 7, 8, 30, tzinfo=UTC),
    )
    rendered = artifact.decode("latin-1")

    assert rendered.startswith("%PDF-1.4")
    assert "Dataset & Source" in rendered
    assert "Dataset ID: stats-gov-sa-cpi-headline-monthly" in rendered
    assert "Source: General Authority for Statistics" in rendered
    assert "GASTAT" in rendered
    assert "stats-gov-sa" in rendered
    assert "Result Status: limited" in rendered
    assert "Freshness Status: stale" in rendered
    assert "Applied Filters: none" in rendered
    assert "Notes / Limitations" in rendered
