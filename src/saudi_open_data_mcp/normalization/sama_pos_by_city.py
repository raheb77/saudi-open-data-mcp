"""Dataset-specific extraction for the canonical SAMA POS by-city contract."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .errors import ExtractedValueValidationError

SAMA_POS_BY_CITY_JSON_REPORT_BUNDLE_LIMITATION = (
    "sama_pos_by_city_json_requires_supported_city_table_report_bundle"
)
SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION = (
    "sama_pos_by_city_extracted_values_failed_sanity_checks"
)

_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_PERIOD_SEPARATOR_PATTERN = re.compile(r"\s+(?:to|-|–|—)\s+")
_REPORT_NUMBER_PATTERN = re.compile(r"\(?[0-9][0-9,]*(?:\.\d+)?\)?")
_TABLE_PERIOD_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]{3},\d{2,4}\s*-\s*\d{1,2}\s+[A-Za-z]{3},\d{2,4}",
    re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TABLE_2_1_SECTION_PATTERN = re.compile(
    r"Table\s*2\.1\s*:\s*By\s*Cities(?P<section>.*?)(?:Table\s*2\.2\s*:|Note:|ملاحظة|$)",
    re.IGNORECASE | re.DOTALL,
)
_TABLE_2_2_SECTION_PATTERN = re.compile(
    r"Table\s*2\.2\s*:\s*By\s*Cities(?P<section>.*?)(?:Note:|ملاحظة|$)",
    re.IGNORECASE | re.DOTALL,
)
_VALUE_IN_THOUSAND_PATTERN = re.compile(
    r"Value\s+of\s+Transactions\s*:?\s*In\s*Thousand",
    re.IGNORECASE,
)
_COUNT_IN_THOUSAND_PATTERN = re.compile(
    r"Number\s+of\s+Transactions\s*:?\s*In\s*Thousand",
    re.IGNORECASE,
)
_ARABIC_TEXT_PATTERN = re.compile(r"[\u0600-\u06FF]")
_CITY_LABEL_PATTERN = re.compile(
    r"^(?P<city_name>[^\u0600-\u06FF]+?)(?P<city_name_ar>[\u0600-\u06FF][\u0600-\u06FF\s]+)$"
)
_TABLE_2_1_TITLE = "Table 2.1: By Cities"
_TABLE_2_2_TITLE = "Table 2.2: By Cities"
_POS_RELEASE_TITLE = "Weekly Points of Sale Transactions"
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b,%y",
    "%d %B,%y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",
    "%d %B, %Y",
)


def extract_sama_pos_by_city_rows_from_json(
    *,
    body: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract weekly city-level POS rows from a supported POS report text bundle."""

    reports = body.get("reports")
    if not isinstance(reports, list):
        return None

    extracted_rows: list[dict[str, Any]] = []
    seen_rows: dict[tuple[str, str, str, str], tuple[int, float, str]] = {}

    for report in reports:
        if not isinstance(report, dict):
            return None

        report_rows = _extract_records_from_report_bundle(
            report=report,
            source_locator=source_locator,
            source_url=source_url,
        )
        if report_rows is None:
            return None

        for record in report_rows:
            row_key = (
                record["week_start_date"],
                record["week_end_date"],
                record["city_name"],
                record["city_name_ar"],
            )
            row_signature = (
                int(record["transaction_count"]),
                float(record["transaction_value_sar"]),
                str(record["source_table_title"]),
            )
            existing_signature = seen_rows.get(row_key)
            if existing_signature is not None:
                if existing_signature != row_signature:
                    raise ExtractedValueValidationError(
                        limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
                        message=(
                            "duplicate POS city weekly rows must not produce "
                            "conflicting transaction values"
                        ),
                    )
                continue

            seen_rows[row_key] = row_signature
            extracted_rows.append(record)

    extracted_rows.sort(
        key=lambda row: (
            row["week_start_date"],
            row["week_end_date"],
            row["city_name"],
            row["city_name_ar"],
        )
    )
    return extracted_rows or None


def _extract_records_from_report_bundle(
    *,
    report: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    report_url = report.get("report_url")
    report_text = report.get("report_text")
    if not isinstance(report_url, str) or not isinstance(report_text, str):
        return None

    normalized_text = _normalize_text(report_text)
    if not normalized_text:
        return None

    if not _has_supported_thousand_units(normalized_text):
        return None

    table_2_1_section = _extract_table_section(
        pattern=_TABLE_2_1_SECTION_PATTERN,
        report_text=report_text,
    )
    table_2_2_section = _extract_table_section(
        pattern=_TABLE_2_2_SECTION_PATTERN,
        report_text=report_text,
    )
    if table_2_1_section is None or table_2_2_section is None:
        return None

    table_2_1_periods = _extract_table_periods(table_2_1_section)
    table_2_2_periods = _extract_table_periods(table_2_2_section)
    if not table_2_1_periods or table_2_1_periods != table_2_2_periods:
        return None

    table_records: list[dict[str, Any]] = []
    for table_title, section in (
        (_TABLE_2_1_TITLE, table_2_1_section),
        (_TABLE_2_2_TITLE, table_2_2_section),
    ):
        section_rows = _extract_rows_from_table_section(
            section=section,
            periods=table_2_1_periods,
            source_locator=source_locator,
            source_url=source_url,
            report_url=report_url,
            source_table_title=table_title,
        )
        if not section_rows:
            return None
        table_records.extend(section_rows)

    return table_records


def _extract_table_section(
    *,
    pattern: re.Pattern[str],
    report_text: str,
) -> str | None:
    match = pattern.search(report_text)
    if match is None:
        return None
    section = match.group("section").strip()
    return section or None


def _extract_table_periods(section: str) -> list[str]:
    periods: list[str] = []
    for match in _TABLE_PERIOD_PATTERN.finditer(_normalize_text(section)):
        period_text = _normalize_period_text(match.group(0))
        if period_text not in periods:
            periods.append(period_text)
    return periods


def _extract_rows_from_table_section(
    *,
    section: str,
    periods: list[str],
    source_locator: str,
    source_url: str,
    report_url: str,
    source_table_title: str,
) -> list[dict[str, Any]]:
    expected_measure_count = len(periods) * 2
    if expected_measure_count <= 0:
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in section.splitlines():
        line = _normalize_text(raw_line)
        if not _looks_like_city_row(line):
            continue

        first_digit_index = next(
            (index for index, character in enumerate(line) if character.isdigit()),
            None,
        )
        if first_digit_index is None or first_digit_index == 0:
            raise ExtractedValueValidationError(
                limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
                message="POS city table row must match the expected city metric layout",
            )

        label = line[:first_digit_index].strip()
        label_match = _CITY_LABEL_PATTERN.match(label)
        if label_match is None:
            raise ExtractedValueValidationError(
                limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
                message="POS city table row must expose both English and Arabic city labels",
            )

        city_name = _normalize_text(label_match.group("city_name"))
        city_name_ar = _normalize_text(label_match.group("city_name_ar"))
        metrics = _REPORT_NUMBER_PATTERN.findall(line[first_digit_index:])
        if len(metrics) != expected_measure_count + 2:
            raise ExtractedValueValidationError(
                limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
                message="POS city table row must expose count/value pairs for each period",
            )

        period_metrics = metrics[:expected_measure_count]
        for period_index, period_text in enumerate(periods):
            start_date, end_date = _parse_period_range(period_text)
            metric_index = period_index * 2
            transaction_count_thousand = _parse_decimal_text(period_metrics[metric_index])
            transaction_value_thousand = _parse_decimal_text(
                period_metrics[metric_index + 1]
            )
            if not _is_supported_metric_pair(
                transaction_count_thousand=transaction_count_thousand,
                transaction_value_thousand=transaction_value_thousand,
            ):
                raise ExtractedValueValidationError(
                    limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
                    message="POS city metrics must stay positive and internally consistent",
                )

            record = {
                "week_start_date": start_date.isoformat(),
                "week_end_date": end_date.isoformat(),
                "city_name": city_name,
                "city_name_ar": city_name_ar,
                "transaction_count": int(round(transaction_count_thousand * 1000)),
                "transaction_value_sar": round(transaction_value_thousand * 1000, 2),
                "source_locator": source_locator,
                "source_url": source_url,
                "source_report_url": report_url,
                "source_period_text": period_text,
                "source_table_title": source_table_title,
                "source_release_title": _POS_RELEASE_TITLE,
            }
            _validate_pos_by_city_record(record)
            rows.append(record)

    return rows


def _looks_like_city_row(line: str) -> bool:
    if not line or not _ARABIC_TEXT_PATTERN.search(line):
        return False
    if not (line[0].isascii() and line[0].isalpha()):
        return False
    if not any(character.isdigit() for character in line):
        return False
    return not line.casefold().startswith(("table ", "note:", "number of ", "value of "))


def _normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _normalize_period_text(value: str) -> str:
    return " ".join(value.split())


def _has_supported_thousand_units(normalized_text: str) -> bool:
    return bool(
        _VALUE_IN_THOUSAND_PATTERN.search(normalized_text)
        and _COUNT_IN_THOUSAND_PATTERN.search(normalized_text)
    )


def _parse_period_range(period_text: str) -> tuple[date, date]:
    normalized = " ".join(period_text.split())
    parts = _PERIOD_SEPARATOR_PATTERN.split(normalized, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("weekly period text must contain a supported range separator")
    return _parse_date_text(parts[0]), _parse_date_text(parts[1])


def _parse_date_text(value: str | None) -> date:
    if value is None:
        raise ValueError("date text must not be missing")

    normalized = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date value: {value}")


def _parse_decimal_text(value: str | None) -> float:
    if value is None:
        raise ValueError("decimal text must not be missing")

    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if not cleaned:
        raise ValueError(f"unsupported decimal value: {value}")
    return float(cleaned)


def _is_supported_metric_pair(
    *,
    transaction_count_thousand: float,
    transaction_value_thousand: float,
) -> bool:
    return (
        transaction_count_thousand > 0
        and transaction_value_thousand > 0
        and transaction_value_thousand > transaction_count_thousand
    )


def _validate_pos_by_city_record(record: dict[str, Any]) -> None:
    start_date = _parse_date_text(str(record["week_start_date"]))
    end_date = _parse_date_text(str(record["week_end_date"]))
    city_name = str(record["city_name"]).strip()
    city_name_ar = str(record["city_name_ar"]).strip()
    transaction_count = int(record["transaction_count"])
    transaction_value_sar = float(record["transaction_value_sar"])

    if start_date > end_date:
        raise ExtractedValueValidationError(
            limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
            message="weekly POS city period start date must not be after the end date",
        )
    if not city_name or not city_name_ar:
        raise ExtractedValueValidationError(
            limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
            message="weekly POS city rows must expose non-empty bilingual city labels",
        )
    if transaction_count <= 0:
        raise ExtractedValueValidationError(
            limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
            message="weekly POS city transaction count must be positive",
        )
    if transaction_value_sar <= 0:
        raise ExtractedValueValidationError(
            limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
            message="weekly POS city transaction value must be positive",
        )
    if transaction_value_sar <= transaction_count:
        raise ExtractedValueValidationError(
            limitation_code=SAMA_POS_BY_CITY_SANITY_VALIDATION_LIMITATION,
            message=(
                "weekly POS city transaction value must remain larger than the "
                "transaction count after unit normalization"
            ),
        )
