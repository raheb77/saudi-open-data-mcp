"""Normalization pipeline composition."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..connectors.base import RawPayload
from .field_mapping import FieldMappingResult, get_field_mapping
from .validators import (
    FieldMappingValidationResult,
    MappingValidationStatus,
    validate_dataset_id,
    validate_field_mapping,
)


class CanonicalRecord(BaseModel):
    """Canonical normalized record placeholder."""

    dataset_id: str
    source: str
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

    def normalize(self, raw_payload: RawPayload) -> NormalizationResult:
        """Run field mapping and validation for a raw payload."""

        dataset_id = validate_dataset_id(raw_payload.dataset_id)

        try:
            mapping_result = get_field_mapping(raw_payload)
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
        return NormalizationResult(
            dataset_id=dataset_id,
            status=status,
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
