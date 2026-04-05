"""Dataset-specific normalization for the first narrow Ministry of Finance fiscal dataset."""

from __future__ import annotations

import re
from typing import Any

MOF_BUDGET_BALANCE_QUARTERLY_JSON_LIMITATION = (
    "mof_budget_balance_quarterly_json_requires_supported_report_text_bundle"
)

_REPORT_QUARTER_PATTERN = re.compile(
    r"/Q(?P<quarter>[1-4])(?:E)?(?:%20|[\s_-])*?(?P<year>\d{4})",
    re.I,
)
_QUARTER_LABEL_PATTERN = re.compile(r"Q([1-4])\s+(\d{4})", re.I)
_LABELS_SECTION_PATTERN = re.compile(
    r"Item\s+(?P<labels>.*?)\s+Total\s+Surplus/\(Deficit\)",
    re.IGNORECASE,
)
_VALUES_SECTION_PATTERN = re.compile(
    r"Total\s+Surplus/\(Deficit\)\s+(?P<values>.*?)\s+Financing\s+Sources",
    re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def extract_mof_budget_balance_quarterly_rows_from_json(
    *,
    body: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract one narrow budget-balance time series from a supported MoF report bundle."""

    reports = body.get("reports")
    if not isinstance(reports, list):
        return None

    extracted_rows: list[dict[str, Any]] = []
    seen_quarters: set[str] = set()

    for report in reports:
        if not isinstance(report, dict):
            continue
        record = _extract_record(
            report=report,
            source_locator=source_locator,
            source_url=source_url,
        )
        if record is None:
            continue

        observation_quarter = record["observation_quarter"]
        if observation_quarter in seen_quarters:
            continue

        seen_quarters.add(observation_quarter)
        extracted_rows.append(record)

    return extracted_rows or None


def _extract_record(
    *,
    report: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> dict[str, Any] | None:
    report_url = report.get("report_url")
    report_text = report.get("report_text")
    if not isinstance(report_url, str) or not isinstance(report_text, str):
        return None

    normalized_text = _normalize_text(report_text)
    if not normalized_text:
        return None

    report_quarter = _extract_report_quarter(report_url)
    if report_quarter is None:
        return None

    try:
        value_sar_bn = _extract_budget_balance_value(normalized_text, report_quarter)
    except ValueError:
        return None

    return {
        "observation_quarter": report_quarter,
        "fiscal_series_code": "headline_budget_balance",
        "fiscal_series_name": "Headline Budget Balance",
        "value_sar_bn": value_sar_bn,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_report_url": report_url,
        "source_release_title": _release_title_for_quarter(report_quarter),
    }


def _extract_report_quarter(report_url: str) -> str | None:
    match = _REPORT_QUARTER_PATTERN.search(report_url)
    if match is None:
        return None
    return f"{match.group('year')}-Q{match.group('quarter')}"


def _extract_budget_balance_value(normalized_text: str, report_quarter: str) -> float:
    if "Results of Surplus/(Deficit)" not in normalized_text:
        raise ValueError("supported fiscal report text did not expose a parseable balance table")

    labels_match = _LABELS_SECTION_PATTERN.search(normalized_text)
    values_match = _VALUES_SECTION_PATTERN.search(normalized_text)
    if labels_match is None or values_match is None:
        raise ValueError("supported fiscal report text did not expose a parseable balance table")

    labels = [
        f"{year}-Q{quarter}"
        for quarter, year in _QUARTER_LABEL_PATTERN.findall(labels_match.group("labels"))
    ]
    values = [
        _parse_million_amount(value_text)
        for value_text in re.findall(r"\(?[0-9,،]+\)?", values_match.group("values"))
    ]

    if len(values) < len(labels):
        raise ValueError("supported fiscal report text did not expose enough balance values")

    quarter_to_value = dict(zip(labels, values, strict=False))
    try:
        return quarter_to_value[report_quarter]
    except KeyError as exc:
        raise ValueError(
            "supported fiscal report text did not expose the current report quarter value"
        ) from exc


def _parse_million_amount(value_text: str) -> float:
    normalized = value_text.replace("،", ",").strip()
    negative = normalized.startswith("(") and normalized.endswith(")")
    digits = normalized.strip("()").replace(",", "")
    value_million = float(digits)
    if negative:
        value_million *= -1.0
    return value_million / 1000.0


def _normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value.replace("’", "'")).strip()


def _release_title_for_quarter(observation_quarter: str) -> str:
    year, quarter = observation_quarter.split("-Q", maxsplit=1)
    return f"Quarterly Budget Performance Q{quarter} of FY {year}"
