"""Unit tests for normalization validators."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.normalization.field_mapping import (
    FieldMappingResult,
    MappingBodyKind,
    RawResponseMetadata,
)
from saudi_open_data_mcp.normalization.validators import (
    TEXT_HTML_LIMITATION,
    FieldMappingValidationResult,
    MappingValidationStatus,
    validate_field_mapping,
)


def test_valid_json_mapping_passes_as_record_derivable() -> None:
    mapping_result = FieldMappingResult(
        source="sama",
        dataset_locator="report.aspx?cid=55",
        response_metadata=RawResponseMetadata(
            url="https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            status_code=200,
            content_type="application/json",
        ),
        body_kind=MappingBodyKind.JSON,
        raw_body={"rows": [{"period": "2026-01", "value": 1}]},
        canonical_fields={
            "dataset_locator": "report.aspx?cid=55",
            "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "response_status_code": 200,
            "response_content_type": "application/json",
            "structured_body": {"rows": [{"period": "2026-01", "value": 1}]},
        },
        can_derive_records=True,
        limitations=(),
    )

    result = validate_field_mapping(mapping_result)

    assert isinstance(result, FieldMappingValidationResult)
    assert result.status is MappingValidationStatus.RECORD_DERIVABLE
    assert result.can_derive_records is True


def test_valid_html_mapping_passes_as_limited() -> None:
    mapping_result = FieldMappingResult(
        source="sama",
        dataset_locator="report.aspx?cid=55",
        response_metadata=RawResponseMetadata(
            url="https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            status_code=200,
            content_type="text/html",
        ),
        body_kind=MappingBodyKind.HTML,
        raw_body="<html><body>official sama page</body></html>",
        canonical_fields={
            "dataset_locator": "report.aspx?cid=55",
            "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "response_status_code": 200,
            "response_content_type": "text/html",
        },
        can_derive_records=False,
        limitations=(TEXT_HTML_LIMITATION,),
    )

    result = validate_field_mapping(mapping_result)

    assert result.status is MappingValidationStatus.LIMITED
    assert result.can_derive_records is False
    assert result.limitations == (TEXT_HTML_LIMITATION,)


def test_inconsistent_mapping_result_fails_validation() -> None:
    mapping_result = FieldMappingResult(
        source="sama",
        dataset_locator="report.aspx?cid=55",
        response_metadata=RawResponseMetadata(
            url="https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            status_code=200,
            content_type="application/json",
        ),
        body_kind=MappingBodyKind.JSON,
        raw_body={"rows": []},
        canonical_fields={
            "dataset_locator": "different-locator",
            "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "response_status_code": 200,
            "response_content_type": "application/json",
            "structured_body": {"rows": []},
        },
        can_derive_records=True,
        limitations=(),
    )

    with pytest.raises(ValueError, match="dataset locator is inconsistent"):
        validate_field_mapping(mapping_result)


def test_missing_required_canonical_fields_fail_validation() -> None:
    mapping_result = FieldMappingResult(
        source="sama",
        dataset_locator="report.aspx?cid=55",
        response_metadata=RawResponseMetadata(
            url="https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            status_code=200,
            content_type="application/json",
        ),
        body_kind=MappingBodyKind.JSON,
        raw_body={"rows": []},
        canonical_fields={
            "dataset_locator": "report.aspx?cid=55",
            "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "response_content_type": "application/json",
            "structured_body": {"rows": []},
        },
        can_derive_records=True,
        limitations=(),
    )

    with pytest.raises(ValueError, match="missing required canonical fields: response_status_code"):
        validate_field_mapping(mapping_result)


def test_invalid_limitation_combinations_fail_validation() -> None:
    mapping_result = FieldMappingResult(
        source="sama",
        dataset_locator="report.aspx?cid=55",
        response_metadata=RawResponseMetadata(
            url="https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            status_code=200,
            content_type="text/html",
        ),
        body_kind=MappingBodyKind.HTML,
        raw_body="<html><body>official sama page</body></html>",
        canonical_fields={
            "dataset_locator": "report.aspx?cid=55",
            "response_url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "response_status_code": 200,
            "response_content_type": "text/html",
        },
        can_derive_records=False,
        limitations=(),
    )

    with pytest.raises(ValueError, match="must declare at least one limitation"):
        validate_field_mapping(mapping_result)
