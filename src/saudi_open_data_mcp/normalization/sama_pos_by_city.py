"""Dataset-specific limitation handling for the canonical SAMA POS by-city contract."""

from __future__ import annotations

from typing import Any

SAMA_POS_BY_CITY_JSON_REPORT_BUNDLE_LIMITATION = (
    "sama_pos_by_city_json_requires_supported_city_table_report_bundle"
)


def extract_sama_pos_by_city_rows_from_json(
    *,
    body: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Recognize the shared POS report bundle while keeping city extraction limited."""

    del source_locator, source_url

    reports = body.get("reports")
    if not isinstance(reports, list):
        return None

    return None
