"""Field mapping for source-specific raw payloads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..connectors.base import RawPayload
from .errors import UnknownNormalizationSourceError
from .mof_budget_balance_quarterly import (
    MOF_BUDGET_BALANCE_QUARTERLY_JSON_LIMITATION,
    extract_mof_budget_balance_quarterly_rows_from_json,
)
from .sama_deposits_core import (
    SAMA_DEPOSITS_CORE_JSON_ROWS_LIMITATION,
    extract_sama_deposits_core_rows_from_json,
)
from .sama_exchange_rates_current import (
    SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION,
    extract_sama_exchange_rates_current_rows_from_html,
)
from .sama_money_supply_weekly import (
    SAMA_MONEY_SUPPLY_WEEKLY_HTML_TABLE_LIMITATION,
    extract_sama_money_supply_weekly_rows_from_html,
)
from .sama_policy_rates import (
    SAMA_POLICY_RATE_HTML_LIMITATION,
    extract_sama_policy_rate_rows_from_html,
)
from .sama_pos_weekly import (
    SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION,
    extract_sama_pos_weekly_rows_from_html,
)
from .stats_gov_sa_cpi_headline_monthly import (
    STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
    extract_stats_gov_sa_cpi_headline_monthly_rows_from_html,
)
from .stats_gov_sa_real_gdp_growth_quarterly import (
    STATS_GOV_SA_REAL_GDP_GROWTH_QUARTERLY_HTML_LIMITATION,
    extract_stats_gov_sa_real_gdp_growth_quarterly_rows_from_html,
)
from .stats_gov_sa_unemployment_rate_total_quarterly import (
    STATS_GOV_SA_UNEMPLOYMENT_RATE_TOTAL_QUARTERLY_HTML_LIMITATION,
    extract_stats_gov_sa_unemployment_rate_total_quarterly_rows_from_html,
)


class MappingBodyKind(StrEnum):
    """Supported raw response body kinds for v0.1 mapping."""

    JSON = "json"
    HTML = "html"
    TEXT = "text"


class RecordExtractionShape(StrEnum):
    """Supported canonical record extraction shapes for v0.1."""

    NONE = "none"
    TOP_LEVEL_OBJECT_LIST = "top_level_object_list"
    ROWS_OBJECT_LIST = "rows_object_list"


TEXT_HTML_EXTRACTION_LIMITATION = (
    "text_or_html_body_requires_source_specific_extraction_before_record_normalization"
)

JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION = (
    "json_body_requires_supported_object_list_shape_for_record_normalization"
)


class RawResponseMetadata(BaseModel):
    """Typed raw response metadata extracted from connector payload content."""

    model_config = ConfigDict(extra="forbid")

    url: str
    status_code: int
    content_type: str


class FieldMappingResult(BaseModel):
    """Intermediate mapping result for later validation and pipeline steps.

    JSON payloads may still be limited here when they are structured but do not
    match a supported object-list shape for safe canonical record extraction.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    dataset_locator: str
    response_metadata: RawResponseMetadata
    body_kind: MappingBodyKind
    raw_body: dict[str, Any] | list[Any] | str
    canonical_fields: dict[str, Any] = Field(default_factory=dict)
    record_extraction_shape: RecordExtractionShape
    can_derive_records: bool
    limitations: tuple[str, ...] = Field(default_factory=tuple)


ExtractedRows = list[dict[str, Any]]
StructuredExtractor = Callable[[Any, str, str], ExtractedRows | None]
StructuredExtractorKey = tuple[str, str, MappingBodyKind]


@dataclass(frozen=True)
class _StructuredExtractorRegistration:
    """Static extractor registration keyed by source, dataset id, and body kind."""

    extractor: StructuredExtractor
    accepted_body_types: tuple[type[Any], ...]
    limitations: tuple[str, ...]

    def accepts_raw_body(self, raw_body: Any) -> bool:
        return isinstance(raw_body, self.accepted_body_types)


def get_field_mapping(
    raw_payload: RawPayload,
    *,
    canonical_dataset_id: str | None = None,
) -> FieldMappingResult:
    """Map a raw payload into a typed normalization-ready field structure.

    Dispatch stays inside the normalization layer and selects the registered
    source-specific mapper by `raw_payload.source`.
    """

    mapper = _resolve_field_mapper(raw_payload.source)
    return mapper(raw_payload, canonical_dataset_id)


def _run_html_rows_extractor(
    raw_body: str,
    source_locator: str,
    source_url: str,
    *,
    extractor: Callable[..., ExtractedRows | None],
) -> ExtractedRows | None:
    return extractor(
        html=raw_body,
        source_locator=source_locator,
        source_url=source_url,
    )


def _run_json_body_rows_extractor(
    raw_body: dict[str, Any],
    source_locator: str,
    source_url: str,
    *,
    extractor: Callable[..., ExtractedRows | None],
) -> ExtractedRows | None:
    return extractor(
        body=raw_body,
        source_locator=source_locator,
        source_url=source_url,
    )


def _run_json_raw_rows_extractor(
    raw_body: dict[str, Any] | list[Any],
    source_locator: str,
    source_url: str,
    *,
    extractor: Callable[..., ExtractedRows | None],
) -> ExtractedRows | None:
    return extractor(
        raw_json=raw_body,
        source_locator=source_locator,
        source_url=source_url,
    )


def _run_policy_rate_rows_extractor(
    raw_body: str,
    source_locator: str,
    source_url: str,
    *,
    policy_rate_code: str,
    policy_rate_name: str,
) -> ExtractedRows | None:
    return extract_sama_policy_rate_rows_from_html(
        html=raw_body,
        source_locator=source_locator,
        source_url=source_url,
        policy_rate_code=policy_rate_code,
        policy_rate_name=policy_rate_name,
    )


_STRUCTURED_EXTRACTOR_REGISTRY: dict[
    StructuredExtractorKey,
    _StructuredExtractorRegistration,
] = {
    (
        "stats-gov-sa",
        "stats-gov-sa-cpi-headline-monthly",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_stats_gov_sa_cpi_headline_monthly_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION,
        ),
    ),
    (
        "stats-gov-sa",
        "stats-gov-sa-unemployment-rate-total-quarterly",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_stats_gov_sa_unemployment_rate_total_quarterly_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            STATS_GOV_SA_UNEMPLOYMENT_RATE_TOTAL_QUARTERLY_HTML_LIMITATION,
        ),
    ),
    (
        "stats-gov-sa",
        "stats-gov-sa-real-gdp-growth-quarterly",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_stats_gov_sa_real_gdp_growth_quarterly_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            STATS_GOV_SA_REAL_GDP_GROWTH_QUARTERLY_HTML_LIMITATION,
        ),
    ),
    (
        "mof",
        "mof-budget-balance-quarterly",
        MappingBodyKind.JSON,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_json_body_rows_extractor,
            extractor=extract_mof_budget_balance_quarterly_rows_from_json,
        ),
        accepted_body_types=(dict,),
        limitations=(
            JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION,
            MOF_BUDGET_BALANCE_QUARTERLY_JSON_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-pos-weekly",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_sama_pos_weekly_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-repo-rate",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_policy_rate_rows_extractor,
            policy_rate_code="repo_rate",
            policy_rate_name="Official Repo Rate",
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            SAMA_POLICY_RATE_HTML_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-reverse-repo-rate",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_policy_rate_rows_extractor,
            policy_rate_code="reverse_repo_rate",
            policy_rate_name="Reverse Repo Rate",
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            SAMA_POLICY_RATE_HTML_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-exchange-rates-current",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_sama_exchange_rates_current_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-deposits-core",
        MappingBodyKind.JSON,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_json_raw_rows_extractor,
            extractor=extract_sama_deposits_core_rows_from_json,
        ),
        accepted_body_types=(dict, list),
        limitations=(
            JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION,
            SAMA_DEPOSITS_CORE_JSON_ROWS_LIMITATION,
        ),
    ),
    (
        "sama",
        "sama-money-supply-weekly",
        MappingBodyKind.HTML,
    ): _StructuredExtractorRegistration(
        extractor=partial(
            _run_html_rows_extractor,
            extractor=extract_sama_money_supply_weekly_rows_from_html,
        ),
        accepted_body_types=(str,),
        limitations=(
            TEXT_HTML_EXTRACTION_LIMITATION,
            SAMA_MONEY_SUPPLY_WEEKLY_HTML_TABLE_LIMITATION,
        ),
    ),
}


def _resolve_structured_extractor(
    *,
    source: str,
    canonical_dataset_id: str | None,
    body_kind: MappingBodyKind,
) -> _StructuredExtractorRegistration | None:
    if canonical_dataset_id is None:
        return None

    return _STRUCTURED_EXTRACTOR_REGISTRY.get(
        (source, canonical_dataset_id, body_kind)
    )


def _build_rows_field_mapping_result(
    *,
    raw_payload: RawPayload,
    response_metadata: RawResponseMetadata,
    body_kind: MappingBodyKind,
    raw_body: dict[str, Any] | list[Any] | str,
    base_canonical_fields: dict[str, Any],
    extracted_rows: ExtractedRows,
) -> FieldMappingResult:
    return FieldMappingResult(
        source=raw_payload.source,
        dataset_locator=raw_payload.dataset_id,
        response_metadata=response_metadata,
        body_kind=body_kind,
        raw_body=raw_body,
        canonical_fields={
            **base_canonical_fields,
            "structured_body": {"rows": extracted_rows},
        },
        record_extraction_shape=RecordExtractionShape.ROWS_OBJECT_LIST,
        can_derive_records=True,
        limitations=(),
    )


def _build_limited_extractor_field_mapping_result(
    *,
    raw_payload: RawPayload,
    response_metadata: RawResponseMetadata,
    body_kind: MappingBodyKind,
    raw_body: dict[str, Any] | list[Any] | str,
    base_canonical_fields: dict[str, Any],
    limitations: tuple[str, ...],
) -> FieldMappingResult:
    return FieldMappingResult(
        source=raw_payload.source,
        dataset_locator=raw_payload.dataset_id,
        response_metadata=response_metadata,
        body_kind=body_kind,
        raw_body=raw_body,
        canonical_fields=base_canonical_fields,
        record_extraction_shape=RecordExtractionShape.NONE,
        can_derive_records=False,
        limitations=limitations,
    )


def _map_tabular_source_payload(
    raw_payload: RawPayload,
    canonical_dataset_id: str | None = None,
) -> FieldMappingResult:
    """Map a supported raw payload into a typed normalization-ready field structure.

    This layer does not invent canonical business records. It separates:
    - connector response metadata
    - raw response body
    - canonical fields that later validation and pipeline steps can inspect
    - explicit structured extractor dispatch keyed by source, dataset id, and body kind
    """

    response_metadata = _build_response_metadata(raw_payload)
    raw_body = _extract_raw_body(raw_payload)
    body_kind = _classify_body_kind(response_metadata.content_type, raw_body)
    base_canonical_fields = {
        "dataset_locator": raw_payload.dataset_id,
        "response_url": response_metadata.url,
        "response_status_code": response_metadata.status_code,
        "response_content_type": response_metadata.content_type,
    }

    structured_extractor = _resolve_structured_extractor(
        source=raw_payload.source,
        canonical_dataset_id=canonical_dataset_id,
        body_kind=body_kind,
    )
    if structured_extractor is not None and structured_extractor.accepts_raw_body(raw_body):
        extracted_rows = structured_extractor.extractor(
            raw_body,
            raw_payload.dataset_id,
            response_metadata.url,
        )
        if extracted_rows:
            return _build_rows_field_mapping_result(
                raw_payload=raw_payload,
                response_metadata=response_metadata,
                body_kind=body_kind,
                raw_body=raw_body,
                base_canonical_fields=base_canonical_fields,
                extracted_rows=extracted_rows,
            )

        return _build_limited_extractor_field_mapping_result(
            raw_payload=raw_payload,
            response_metadata=response_metadata,
            body_kind=body_kind,
            raw_body=raw_body,
            base_canonical_fields=base_canonical_fields,
            limitations=structured_extractor.limitations,
        )

    if body_kind is MappingBodyKind.JSON:
        record_extraction_shape = _detect_record_extraction_shape(raw_body)
        canonical_fields = {
            **base_canonical_fields,
            "structured_body": raw_body,
        }
        can_derive_records = record_extraction_shape is not RecordExtractionShape.NONE
        limitations = (
            ()
            if can_derive_records
            else (JSON_UNSUPPORTED_RECORD_SHAPE_LIMITATION,)
        )
    else:
        record_extraction_shape = RecordExtractionShape.NONE
        canonical_fields = base_canonical_fields
        limitations = (TEXT_HTML_EXTRACTION_LIMITATION,)
        can_derive_records = False

    return FieldMappingResult(
        source=raw_payload.source,
        dataset_locator=raw_payload.dataset_id,
        response_metadata=response_metadata,
        body_kind=body_kind,
        raw_body=raw_body,
        canonical_fields=canonical_fields,
        record_extraction_shape=record_extraction_shape,
        can_derive_records=can_derive_records,
        limitations=limitations,
    )


FieldMapper = Callable[[RawPayload, str | None], FieldMappingResult]

_FIELD_MAPPERS: dict[str, FieldMapper] = {
    "sama": _map_tabular_source_payload,
    "data-gov-sa": _map_tabular_source_payload,
    "mof": _map_tabular_source_payload,
    "stats-gov-sa": _map_tabular_source_payload,
}


def _resolve_field_mapper(source: str) -> FieldMapper:
    """Resolve the field mapper registered for a source."""

    normalized_source = source.strip()
    mapper = _FIELD_MAPPERS.get(normalized_source)
    if mapper is None:
        raise UnknownNormalizationSourceError(
            f"No field mapping registered for source '{source}'"
        )
    return mapper


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


def _detect_record_extraction_shape(
    raw_body: dict[str, Any] | list[Any],
) -> RecordExtractionShape:
    """Detect whether the current JSON body supports safe canonical record extraction."""

    if isinstance(raw_body, list):
        if all(isinstance(item, dict) for item in raw_body):
            return RecordExtractionShape.TOP_LEVEL_OBJECT_LIST
        return RecordExtractionShape.NONE

    rows = raw_body.get("rows")
    if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
        return RecordExtractionShape.ROWS_OBJECT_LIST

    return RecordExtractionShape.NONE
