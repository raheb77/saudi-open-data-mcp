"""Input sanitization helpers."""

from __future__ import annotations

MAX_DATASET_ID_LENGTH = 256
MAX_SEARCH_QUERY_LENGTH = 512
MAX_QUERY_FILTER_KEY_LENGTH = 128
MAX_QUERY_FILTER_VALUE_LENGTH = 512


def sanitize_dataset_id(dataset_id: str) -> str:
    """Return a validated, trimmed dataset identifier."""

    return _sanitize_text_input(
        dataset_id,
        field_name="dataset_id",
        max_length=MAX_DATASET_ID_LENGTH,
        strip=True,
        allow_empty=False,
    )


def sanitize_search_query(query: str) -> str:
    """Return a validated search query."""

    return _sanitize_text_input(
        query,
        field_name="query",
        max_length=MAX_SEARCH_QUERY_LENGTH,
        strip=False,
        allow_empty=True,
    )


def sanitize_query_filter_key(key: str) -> str:
    """Return a validated, trimmed exact-match query filter key."""

    return _sanitize_text_input(
        key,
        field_name="query filter key",
        max_length=MAX_QUERY_FILTER_KEY_LENGTH,
        strip=True,
        allow_empty=False,
    )


def sanitize_query_filter_string_value(value: str) -> str:
    """Return a validated exact-match query filter string value."""

    return _sanitize_text_input(
        value,
        field_name="query filter value",
        max_length=MAX_QUERY_FILTER_VALUE_LENGTH,
        strip=False,
        allow_empty=True,
    )


def _sanitize_text_input(
    value: str,
    *,
    field_name: str,
    max_length: int,
    strip: bool,
    allow_empty: bool,
) -> str:
    """Validate a tool-facing text input with deterministic bounds checks."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if "\x00" in value:
        raise ValueError(f"{field_name} must not contain null bytes")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")

    normalized = value.strip() if strip else value
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized
