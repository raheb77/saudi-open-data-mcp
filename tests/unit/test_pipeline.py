"""Unit tests for the normalization pipeline."""

from __future__ import annotations

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization import pipeline as pipeline_module
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
