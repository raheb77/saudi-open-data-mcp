"""Normalization pipeline composition."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..connectors.base import RawPayload
from .field_mapping import (
    FieldMappingResult,
    RecordExtractionShape,
    get_field_mapping,
)
from .validators import (
    FieldMappingValidationResult,
    MappingValidationStatus,
    validate_dataset_id,
    validate_field_mapping,
)


class CanonicalRecord(BaseModel):
    """Minimal canonical normalized record for supported simple JSON shapes."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    source: str
    record_index: int
    fields: dict[str, Any] = Field(default_factory=dict)


class NormalizationPipelineStatus(StrEnum):
    """Pipeline result status."""

    RECORD_DERIVABLE = "record_derivable"
    LIMITED = "limited"
    FAILED = "failed"


class NormalizationFailureStage(StrEnum):
    """Pipeline failure stage."""

    MAPPING = "mapping"
    VALIDATION = "validation"
    RECORD_EXTRACTION = "record_extraction"


class NormalizationFailure(BaseModel):
    """Explicit failure details for pipeline work."""

    model_config = ConfigDict(extra="forbid")

    stage: NormalizationFailureStage
    error_type: str
    message: str


class NormalizationResult(BaseModel):
    """Typed normalization pipeline result."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    status: NormalizationPipelineStatus
    records: tuple[CanonicalRecord, ...] = Field(default_factory=tuple)
    mapping_result: FieldMappingResult | None = None
    validation_result: FieldMappingValidationResult | None = None
    failure: NormalizationFailure | None = None


class NormalizationPipeline:
    """Compose field mapping and validation without adding orchestration layers."""

    def normalize(
        self,
        raw_payload: RawPayload,
        *,
        canonical_dataset_id: str | None = None,
    ) -> NormalizationResult:
        """Run field mapping and validation for a raw payload."""

        dataset_id = validate_dataset_id(raw_payload.dataset_id)

        try:
            mapping_result = get_field_mapping(
                raw_payload,
                canonical_dataset_id=canonical_dataset_id,
            )
        except ValueError as exc:
            return NormalizationResult(
                dataset_id=dataset_id,
                status=NormalizationPipelineStatus.FAILED,
                failure=NormalizationFailure(
                    stage=NormalizationFailureStage.MAPPING,
                    error_type=type(exc).__name__,
                    message=str(exc),
                ),
            )

        try:
            validation_result = validate_field_mapping(mapping_result)
        except ValueError as exc:
            return NormalizationResult(
                dataset_id=dataset_id,
                status=NormalizationPipelineStatus.FAILED,
                mapping_result=mapping_result,
                failure=NormalizationFailure(
                    stage=NormalizationFailureStage.VALIDATION,
                    error_type=type(exc).__name__,
                    message=str(exc),
                ),
            )

        status = _status_from_validation(validation_result.status)
        try:
            records = _build_canonical_records(validation_result)
        except ValueError as exc:
            return NormalizationResult(
                dataset_id=dataset_id,
                status=NormalizationPipelineStatus.FAILED,
                mapping_result=mapping_result,
                validation_result=validation_result,
                failure=NormalizationFailure(
                    stage=NormalizationFailureStage.RECORD_EXTRACTION,
                    error_type=type(exc).__name__,
                    message=str(exc),
                ),
            )

        return NormalizationResult(
            dataset_id=dataset_id,
            status=status,
            records=records,
            mapping_result=mapping_result,
            validation_result=validation_result,
        )


def _status_from_validation(
    validation_status: MappingValidationStatus,
) -> NormalizationPipelineStatus:
    """Map validation status to pipeline status."""

    if validation_status is MappingValidationStatus.RECORD_DERIVABLE:
        return NormalizationPipelineStatus.RECORD_DERIVABLE
    return NormalizationPipelineStatus.LIMITED


def _build_canonical_records(
    validation_result: FieldMappingValidationResult,
) -> tuple[CanonicalRecord, ...]:
    """Build canonical records for the supported validated JSON shapes only."""

    if validation_result.status is not MappingValidationStatus.RECORD_DERIVABLE:
        return ()

    structured_body = validation_result.canonical_fields["structured_body"]
    rows: list[Any]
    if validation_result.record_extraction_shape is RecordExtractionShape.TOP_LEVEL_OBJECT_LIST:
        if not isinstance(structured_body, list):
            raise ValueError("top-level object list extraction requires a list structured_body")
        rows = structured_body
    elif (
        validation_result.record_extraction_shape
        is RecordExtractionShape.ROWS_OBJECT_LIST
    ):
        if not isinstance(structured_body, dict):
            raise ValueError("rows object list extraction requires a dict structured_body")
        candidate_rows = structured_body.get("rows")
        if not isinstance(candidate_rows, list):
            raise ValueError("rows object list extraction requires a rows list")
        rows = candidate_rows
    else:
        raise ValueError(
            "record-derivable validation result must declare a supported extraction shape"
        )

    return tuple(
        CanonicalRecord(
            dataset_id=validation_result.dataset_locator,
            source=validation_result.source,
            record_index=index,
            fields=_copy_record_fields(record),
        )
        for index, record in enumerate(rows)
    )


def _copy_record_fields(record: Any) -> dict[str, Any]:
    """Copy a raw object record into canonical fields without inventing semantics."""

    if not isinstance(record, dict):
        raise ValueError("canonical record extraction requires object records")

    copied: dict[str, Any] = {}
    for key, value in record.items():
        if not isinstance(key, str):
            raise ValueError("canonical record fields must use string keys")
        copied[key] = value
    return copied
