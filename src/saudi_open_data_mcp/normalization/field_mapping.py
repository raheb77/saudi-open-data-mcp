"""Field mapping for source-specific raw payloads."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..connectors.base import RawPayload


class MappingBodyKind(StrEnum):
    """Supported raw response body kinds for v0.1 mapping."""

    JSON = "json"
    HTML = "html"
    TEXT = "text"


class RawResponseMetadata(BaseModel):
    """Typed raw response metadata extracted from connector payload content."""

    model_config = ConfigDict(extra="forbid")

    url: str
    status_code: int
    content_type: str


class FieldMappingResult(BaseModel):
    """Intermediate mapping result for later validation and pipeline steps."""

    model_config = ConfigDict(extra="forbid")

    source: str
    dataset_locator: str
    response_metadata: RawResponseMetadata
    body_kind: MappingBodyKind
    raw_body: dict[str, Any] | list[Any] | str
    canonical_fields: dict[str, Any] = Field(default_factory=dict)
    can_derive_records: bool
    limitations: tuple[str, ...] = Field(default_factory=tuple)


def get_field_mapping(raw_payload: RawPayload) -> FieldMappingResult:
    """Map a raw SAMA payload into a typed normalization-ready field structure.

    This layer does not invent canonical business records. It separates:
    - connector response metadata
    - raw response body
    - canonical fields that later validation and pipeline steps can inspect
    """

    if raw_payload.source != "sama":
        raise ValueError(
            f"field mapping currently supports source 'sama' only, got '{raw_payload.source}'"
        )

    response_metadata = _build_response_metadata(raw_payload)
    raw_body = _extract_raw_body(raw_payload)
    body_kind = _classify_body_kind(response_metadata.content_type, raw_body)

    if body_kind is MappingBodyKind.JSON:
        canonical_fields = {
            "dataset_locator": raw_payload.dataset_id,
            "response_url": response_metadata.url,
            "response_status_code": response_metadata.status_code,
            "response_content_type": response_metadata.content_type,
            "structured_body": raw_body,
        }
        limitations: tuple[str, ...] = ()
        can_derive_records = True
    else:
        canonical_fields = {
            "dataset_locator": raw_payload.dataset_id,
            "response_url": response_metadata.url,
            "response_status_code": response_metadata.status_code,
            "response_content_type": response_metadata.content_type,
        }
        limitations = (
            "text_or_html_body_requires_source_specific_extraction_before_record_normalization",
        )
        can_derive_records = False

    return FieldMappingResult(
        source=raw_payload.source,
        dataset_locator=raw_payload.dataset_id,
        response_metadata=response_metadata,
        body_kind=body_kind,
        raw_body=raw_body,
        canonical_fields=canonical_fields,
        can_derive_records=can_derive_records,
        limitations=limitations,
    )


def _build_response_metadata(raw_payload: RawPayload) -> RawResponseMetadata:
    """Build typed response metadata from raw connector content."""

    content = raw_payload.content
    missing_keys = tuple(
        key for key in ("url", "status_code", "content_type", "body") if key not in content
    )
    if missing_keys:
        formatted = ", ".join(missing_keys)
        raise ValueError(f"raw payload content is missing required keys: {formatted}")

    content_type = str(content["content_type"]).strip()
    if not content_type:
        raise ValueError("raw payload content_type must not be empty")

    try:
        status_code = int(content["status_code"])
    except (TypeError, ValueError) as exc:
        raise ValueError("raw payload status_code must be an integer") from exc

    return RawResponseMetadata(
        url=str(content["url"]),
        status_code=status_code,
        content_type=content_type,
    )


def _extract_raw_body(raw_payload: RawPayload) -> dict[str, Any] | list[Any] | str:
    """Extract the raw response body from connector content."""

    body = raw_payload.content["body"]
    if isinstance(body, (dict, list, str)):
        return body
    raise ValueError("raw payload body must be a dict, list, or string")


def _classify_body_kind(
    content_type: str,
    raw_body: dict[str, Any] | list[Any] | str,
) -> MappingBodyKind:
    """Classify the raw body kind using connector metadata."""

    normalized = content_type.lower()
    if "json" in normalized:
        if not isinstance(raw_body, (dict, list)):
            raise ValueError("json content_type requires a dict or list body")
        return MappingBodyKind.JSON
    if "html" in normalized:
        if not isinstance(raw_body, str):
            raise ValueError("html content_type requires a string body")
        return MappingBodyKind.HTML
    if normalized.startswith("text/"):
        if not isinstance(raw_body, str):
            raise ValueError("text content_type requires a string body")
        return MappingBodyKind.TEXT
    raise ValueError(f"unsupported raw payload content_type: {content_type}")
