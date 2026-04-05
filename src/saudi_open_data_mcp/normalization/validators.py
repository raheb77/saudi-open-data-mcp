"""Validation helpers for normalization."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .errors import UnknownNormalizationSourceError
from .field_mapping import (
    JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION,
    TEXT_HTML_EXTRACTION_LIMITATION,
    FieldMappingResult,
    MappingBodyKind,
    RecordExtractionShape,
)

TEXT_HTML_LIMITATION = TEXT_HTML_EXTRACTION_LIMITATION


class MappingValidationStatus(StrEnum):
    """Validated readiness state for a mapped result."""

    RECORD_DERIVABLE = "record_derivable"
    LIMITED = "limited"


class FieldMappingValidationResult(BaseModel):
    """Typed validation result for a mapped payload."""

    model_config = ConfigDict(extra="forbid")

    source: str
    dataset_locator: str
    body_kind: MappingBodyKind
    status: MappingValidationStatus
    record_extraction_shape: RecordExtractionShape
    can_derive_records: bool
    canonical_fields: dict[str, Any] = Field(default_factory=dict)
    limitations: tuple[str, ...] = Field(default_factory=tuple)


def validate_dataset_id(dataset_id: str) -> str:
    """Validate and normalize a dataset identifier."""

    value = dataset_id.strip()
    if not value:
        raise ValueError("dataset_id must not be empty")
    return value


def validate_field_mapping(mapping_result: FieldMappingResult) -> FieldMappingValidationResult:
    """Validate a field mapping result for later pipeline use.

    This validator distinguishes between:
    - record-derivable mappings that can move toward normalization
    - limited mappings that are still valid but require source-specific extraction
    - invalid mappings that fail explicitly
    """

    validator = _resolve_field_mapping_validator(mapping_result.source)
    return validator(mapping_result)


def _validate_tabular_source_field_mapping(
    mapping_result: FieldMappingResult,
) -> FieldMappingValidationResult:
    """Validate the current tabular-source field mapping contract."""

    dataset_locator = validate_dataset_id(mapping_result.dataset_locator)
    _validate_common_fields(mapping_result, dataset_locator)

    if mapping_result.body_kind is MappingBodyKind.JSON:
        status = _validate_json_mapping(mapping_result)
    else:
        status = _validate_non_json_mapping(mapping_result)

    return FieldMappingValidationResult(
        source=mapping_result.source,
        dataset_locator=dataset_locator,
        body_kind=mapping_result.body_kind,
        status=status,
        record_extraction_shape=mapping_result.record_extraction_shape,
        can_derive_records=mapping_result.can_derive_records,
        canonical_fields=dict(mapping_result.canonical_fields),
        limitations=mapping_result.limitations,
    )


def _validate_non_json_mapping(
    mapping_result: FieldMappingResult,
) -> MappingValidationStatus:
    """Validate an HTML/text mapping that is either limited or source-specifically extracted."""

    if (
        mapping_result.can_derive_records
        or mapping_result.record_extraction_shape is not RecordExtractionShape.NONE
        or "structured_body" in mapping_result.canonical_fields
    ):
        _validate_extracted_non_json_mapping(mapping_result)
        return MappingValidationStatus.RECORD_DERIVABLE

    _validate_limited_mapping(mapping_result)
    return MappingValidationStatus.LIMITED

FieldMappingValidator = Callable[[FieldMappingResult], FieldMappingValidationResult]

_FIELD_MAPPING_VALIDATORS: dict[str, FieldMappingValidator] = {
    "sama": _validate_tabular_source_field_mapping,
    "data-gov-sa": _validate_tabular_source_field_mapping,
    "mof": _validate_tabular_source_field_mapping,
    "stats-gov-sa": _validate_tabular_source_field_mapping,
}


def _resolve_field_mapping_validator(source: str) -> FieldMappingValidator:
    """Resolve the field-mapping validator registered for a source."""

    normalized_source = source.strip()
    validator = _FIELD_MAPPING_VALIDATORS.get(normalized_source)
    if validator is None:
        raise UnknownNormalizationSourceError(
            f"No field mapping validator registered for source '{source}'"
        )
    return validator


def _validate_common_fields(mapping_result: FieldMappingResult, dataset_locator: str) -> None:
    """Validate required common canonical fields and metadata consistency."""

    required_fields = (
        "dataset_locator",
        "response_url",
        "response_status_code",
        "response_content_type",
    )
    missing_fields = tuple(
        field_name
        for field_name in required_fields
        if field_name not in mapping_result.canonical_fields
    )
    if missing_fields:
        formatted = ", ".join(missing_fields)
        raise ValueError(f"mapping result is missing required canonical fields: {formatted}")

    canonical_fields = mapping_result.canonical_fields
    if canonical_fields["dataset_locator"] != dataset_locator:
        raise ValueError("mapping result dataset locator is inconsistent with canonical fields")
    if canonical_fields["response_url"] != mapping_result.response_metadata.url:
        raise ValueError("mapping result response URL is inconsistent with response metadata")
    if canonical_fields["response_status_code"] != mapping_result.response_metadata.status_code:
        raise ValueError("mapping result status code is inconsistent with response metadata")
    if canonical_fields["response_content_type"] != mapping_result.response_metadata.content_type:
        raise ValueError("mapping result content type is inconsistent with response metadata")


def _validate_json_mapping(
    mapping_result: FieldMappingResult,
) -> MappingValidationStatus:
    """Validate a JSON mapping that may be record-derivable or explicitly limited."""

    if not isinstance(mapping_result.raw_body, (dict, list)):
        raise ValueError("json mapping raw_body must be a dict or list")
    if "structured_body" not in mapping_result.canonical_fields:
        raise ValueError("json mapping must include 'structured_body' in canonical_fields")
    if mapping_result.canonical_fields["structured_body"] != mapping_result.raw_body:
        _validate_extracted_json_mapping(mapping_result)
        return MappingValidationStatus.RECORD_DERIVABLE
    _validate_record_shape_against_body(
        record_extraction_shape=mapping_result.record_extraction_shape,
        structured_body=mapping_result.raw_body,
    )

    if mapping_result.record_extraction_shape is RecordExtractionShape.NONE:
        if mapping_result.can_derive_records:
            raise ValueError("unsupported json mapping must not be marked as record-derivable")
        if JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION not in mapping_result.limitations:
            raise ValueError(
                "unsupported json mapping must declare the expected record-shape limitation"
            )
        return MappingValidationStatus.LIMITED

    if not mapping_result.can_derive_records:
        raise ValueError("supported json mapping must be marked as record-derivable")
    if mapping_result.limitations:
        raise ValueError("record-derivable json mapping must not declare limitations")
    return MappingValidationStatus.RECORD_DERIVABLE


def _validate_extracted_json_mapping(mapping_result: FieldMappingResult) -> None:
    """Validate a JSON mapping that extracted a narrower canonical structured body."""

    if mapping_result.record_extraction_shape is RecordExtractionShape.NONE:
        raise ValueError(
            "extracted json mapping must declare a supported record extraction shape"
        )
    if not mapping_result.can_derive_records:
        raise ValueError("extracted json mapping must be marked as record-derivable")
    if mapping_result.limitations:
        raise ValueError("record-derivable extracted json mapping must not declare limitations")

    _validate_record_shape_against_body(
        record_extraction_shape=mapping_result.record_extraction_shape,
        structured_body=mapping_result.canonical_fields["structured_body"],
    )


def _validate_extracted_non_json_mapping(mapping_result: FieldMappingResult) -> None:
    """Validate a non-JSON mapping that extracted structured rows from source text/html."""

    if mapping_result.body_kind not in {MappingBodyKind.HTML, MappingBodyKind.TEXT}:
        raise ValueError("extracted non-json mapping must use an HTML or text body kind")
    if not isinstance(mapping_result.raw_body, str):
        raise ValueError("extracted non-json mapping raw_body must remain a string")
    if "structured_body" not in mapping_result.canonical_fields:
        raise ValueError(
            "extracted non-json mapping must include 'structured_body' in canonical_fields"
        )
    if mapping_result.limitations:
        raise ValueError("record-derivable non-json mapping must not declare limitations")
    if not mapping_result.can_derive_records:
        raise ValueError("record-derivable non-json mapping must declare can_derive_records")

    _validate_record_shape_against_body(
        record_extraction_shape=mapping_result.record_extraction_shape,
        structured_body=mapping_result.canonical_fields["structured_body"],
    )


def _validate_limited_mapping(mapping_result: FieldMappingResult) -> None:
    """Validate a limited HTML or text mapping result."""

    if mapping_result.body_kind not in {MappingBodyKind.HTML, MappingBodyKind.TEXT}:
        raise ValueError("limited mapping must use an HTML or text body kind")
    if mapping_result.record_extraction_shape is not RecordExtractionShape.NONE:
        raise ValueError("html/text mapping must not declare a record extraction shape")
    if not isinstance(mapping_result.raw_body, str):
        raise ValueError("html/text mapping raw_body must be a string")
    if mapping_result.can_derive_records:
        raise ValueError("html/text mapping must not be marked as record-derivable")
    if "structured_body" in mapping_result.canonical_fields:
        raise ValueError("html/text mapping must not include 'structured_body'")
    if not mapping_result.limitations:
        raise ValueError("html/text mapping must declare at least one limitation")
    if TEXT_HTML_LIMITATION not in mapping_result.limitations:
        raise ValueError(
            "html/text mapping must declare the expected extraction limitation message"
        )


def _validate_record_shape_against_body(
    *,
    record_extraction_shape: RecordExtractionShape,
    structured_body: Any,
) -> None:
    """Validate consistency between a structured body and the declared extraction shape."""

    if record_extraction_shape is RecordExtractionShape.NONE:
        return

    if record_extraction_shape is RecordExtractionShape.TOP_LEVEL_OBJECT_LIST:
        if not isinstance(structured_body, list):
            raise ValueError("top-level object list mapping must use a list raw_body")
        if not all(isinstance(item, dict) for item in structured_body):
            raise ValueError("top-level object list mapping requires object entries only")
        return

    if record_extraction_shape is RecordExtractionShape.ROWS_OBJECT_LIST:
        if not isinstance(structured_body, dict):
            raise ValueError("rows object list mapping must use a dict raw_body")
        rows = structured_body.get("rows")
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            raise ValueError("rows object list mapping requires a rows list of objects")
        return

    raise ValueError(
        f"unsupported record extraction shape: {record_extraction_shape.value}"
    )
