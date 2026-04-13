"""Unit tests for explicit governed query-result export artifacts."""

from __future__ import annotations

import io
import re
import shutil
import unicodedata
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from saudi_open_data_mcp.normalization.pipeline import CanonicalRecord
from saudi_open_data_mcp.registry.models import DatasetCoverageStatus
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
        coverage_status=DatasetCoverageStatus.QUERYABLE,
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


def _normalized_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized = unicodedata.normalize("NFKC", extracted)
    normalized = normalized.translate(
        str.maketrans(
            {
                "ی": "ي",
                "ک": "ك",
                "ھ": "ه",
                "ہ": "ه",
                "ۀ": "ة",
            }
        )
    )
    return re.sub(r"[ \t]+", " ", normalized)


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
    assert "coverage_status" in rendered
    assert "queryable" in rendered
    assert "fresh" in rendered


def test_render_query_result_excel_artifact_cleans_empty_filter_presentation() -> None:
    result = DatasetQueryResult(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        status="limited",
        coverage_status=DatasetCoverageStatus.LIMITED,
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
        coverage_status=DatasetCoverageStatus.LIMITED,
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
    rendered = _normalized_pdf_text(artifact)

    assert artifact.startswith(b"%PDF-")
    assert "Dataset & Source" in rendered
    assert "stats-gov-sa-cpi-headline-monthly" in rendered
    assert "General Authority for Statistics" in rendered
    assert "GASTAT" in rendered
    assert "stats-gov-sa" in rendered
    assert "limited" in rendered
    assert "none" in rendered
    if shutil.which("cupsfilter") is not None:
        assert "البيانات" in rendered
        assert "والمصدر" in rendered
        assert "التغطية" in rendered
        assert "اللقطة" in rendered
        assert "ملاحظات" in rendered
        assert "قيود" in rendered
        assert "?" not in rendered


@pytest.mark.skipif(
    shutil.which("cupsfilter") is None,
    reason="system PDF renderer not available",
)
def test_render_query_result_pdf_artifact_preserves_arabic_record_content() -> None:
    result = DatasetQueryResult(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        status="success",
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        source="stats-gov-sa",
        data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
        applied_filters={"series_name": "الرقم القياسي العام"},
        limit=10,
        total_records_before_filter=1,
        matched_records=(
            CanonicalRecord(
                dataset_id="stats-gov-sa-cpi-headline-monthly",
                source="stats-gov-sa",
                record_index=0,
                fields={
                    "observation_month": "2025-12",
                    "inflation_series_name": "الرقم القياسي العام لأسعار المستهلك",
                    "yoy_rate_percent": 2.1,
                    "source_release_title": "ارتفاع التضخم السنوي في ديسمبر 2025",
                    "source_summary_text": (
                        "ارتفع التضخم السنوي إلى 2.1% مقارنة بالشهر المماثل من العام السابق."
                    ),
                },
            ),
        ),
    )

    artifact = render_query_result_pdf_artifact(
        result,
        freshness_status="fresh",
        exported_at=datetime(2026, 4, 7, 8, 30, tzinfo=UTC),
    )
    rendered = _normalized_pdf_text(artifact)
    compact_rendered = rendered.replace("\n", "")

    assert "استعلام" in rendered
    assert "تصدير" in rendered
    assert "ارتفاع" in rendered
    assert "التضخم" in rendered
    assert "القياسي" in rendered
    assert "مستهلك" in compact_rendered
    assert "series_name" in rendered
    assert "?" not in rendered


@pytest.mark.skipif(
    shutil.which("cupsfilter") is None,
    reason="system PDF renderer not available",
)
def test_render_query_result_pdf_artifact_preserves_arabic_limited_notes() -> None:
    result = DatasetQueryResult(
        dataset_id="sama-pos-by-city",
        status="limited",
        coverage_status=DatasetCoverageStatus.LIMITED,
        source="sama",
        data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
        applied_filters={},
        limit=None,
        degradation_reason="normalization_limited",
        limitations=(
            "شرح عربي قصير: هذه المجموعة لا تدعم سجلات قابلة للاستعلام بالكامل بعد.",
            "dataset_registry_declares_no_current_queryable_support",
        ),
    )

    artifact = render_query_result_pdf_artifact(
        result,
        freshness_status="stale",
        exported_at=datetime(2026, 4, 7, 8, 30, tzinfo=UTC),
    )
    rendered = _normalized_pdf_text(artifact)

    assert "ملاحظات" in rendered
    assert "قيود" in rendered
    assert "شرح" in rendered
    assert "عربي" in rendered
    assert "قصير" in rendered
    assert "سجلات" in rendered
    assert "dataset_registry_declares_no_current_queryable_support" in rendered
    assert "?" not in rendered
