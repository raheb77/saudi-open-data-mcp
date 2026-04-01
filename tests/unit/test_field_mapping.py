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

    def _source_two_mapper(payload: RawPayload) -> FieldMappingResult:
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
