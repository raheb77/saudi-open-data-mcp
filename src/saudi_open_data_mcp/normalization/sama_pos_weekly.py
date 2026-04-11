"""Dataset-specific extraction for the canonical SAMA POS weekly contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION = (
    "sama_pos_weekly_html_requires_supported_weekly_summary_table"
)
SAMA_POS_WEEKLY_JSON_REPORT_BUNDLE_LIMITATION = (
    "sama_pos_weekly_json_requires_supported_report_text_bundle"
)

_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_INTEGER_CLEANUP_PATTERN = re.compile(r"[^0-9\-]+")
_PERIOD_SEPARATOR_PATTERN = re.compile(r"\s+(?:to|-|–|—)\s+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TABLE_1_SECTION_PATTERN = re.compile(
    r"Table\s*1\s*:\s*By\s*Activities(?P<section>.*?)(?:Table\s*2(?:\.1)?\s*:|Note:|ملاحظة|$)",
    re.IGNORECASE,
)
_TABLE_1_PERIOD_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]{3},\d{2,4}\s*-\s*\d{1,2}\s+[A-Za-z]{3},\d{2,4}",
    re.IGNORECASE,
)
_TOTAL_ROW_PATTERN = re.compile(r"(?:\bTotal\b|الإجمالي)\s+(?P<metrics>.*)$", re.IGNORECASE)
_REPORT_NUMBER_PATTERN = re.compile(r"\(?[0-9][0-9,]*(?:\.\d+)?\)?")
_VALUE_IN_THOUSAND_PATTERN = re.compile(
    r"Value\s+of\s+Transactions\s*:?\s*In\s*Thousand",
    re.IGNORECASE,
)
_COUNT_IN_THOUSAND_PATTERN = re.compile(
    r"Number\s+of\s+Transactions\s*:?\s*In\s*Thousand",
    re.IGNORECASE,
)
_TABLE_1_TITLE = "Table 1: By Activities"
_POS_RELEASE_TITLE = "Weekly Points of Sale Transactions"

_WEEK_START_HEADER_ALIASES = frozenset(
    {
        "week start",
        "week from",
        "start date",
        "from",
        "from date",
    }
)
_WEEK_END_HEADER_ALIASES = frozenset(
    {
        "week end",
        "week to",
        "end date",
        "to",
        "to date",
    }
)
_WEEK_PERIOD_HEADER_ALIASES = frozenset(
    {
        "week",
        "week range",
        "week period",
        "period",
    }
)
_TRANSACTION_COUNT_HEADER_ALIASES = frozenset(
    {
        "transactions",
        "transaction count",
        "number of transactions",
        "total transactions",
    }
)
_TRANSACTION_VALUE_HEADER_ALIASES = frozenset(
    {
        "value",
        "value sar",
        "value in sar",
        "transaction value",
        "transaction value sar",
        "amount sar",
        "total value",
    }
)
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


@dataclass(slots=True)
class _ParsedRow:
    cells: list[str] = field(default_factory=list)
    has_header_cells: bool = False


@dataclass(slots=True)
class _ParsedTable:
    caption: str | None = None
    rows: list[_ParsedRow] = field(default_factory=list)


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_ParsedTable] = []
        self._current_table: _ParsedTable | None = None
        self._current_row: _ParsedRow | None = None
        self._current_cell_chunks: list[str] | None = None
        self._current_caption_chunks: list[str] | None = None
        self._in_cell = False
        self._in_caption = False
        self._cell_is_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table":
            self._current_table = _ParsedTable()
            return

        if self._current_table is None:
            return

        if tag == "caption":
            self._in_caption = True
            self._current_caption_chunks = []
        elif tag == "tr":
            self._current_row = _ParsedRow()
        elif tag in {"th", "td"} and self._current_row is not None:
            self._in_cell = True
            self._cell_is_header = tag == "th"
            self._current_cell_chunks = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return

        if self._in_caption and self._current_caption_chunks is not None:
            self._current_caption_chunks.append(text)
        elif self._in_cell and self._current_cell_chunks is not None:
            self._current_cell_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._current_table is not None and self._current_table.rows:
                self.tables.append(self._current_table)
            self._current_table = None
            return

        if self._current_table is None:
            return

        if tag == "caption":
            if self._current_caption_chunks:
                self._current_table.caption = " ".join(self._current_caption_chunks).strip()
            self._current_caption_chunks = None
            self._in_caption = False
        elif tag in {"th", "td"} and self._current_row is not None:
            value = ""
            if self._current_cell_chunks:
                value = " ".join(self._current_cell_chunks).strip()
            self._current_row.cells.append(value)
            if self._cell_is_header:
                self._current_row.has_header_cells = True
            self._current_cell_chunks = None
            self._cell_is_header = False
            self._in_cell = False
        elif tag == "tr":
            if self._current_row is not None and any(
                cell.strip() for cell in self._current_row.cells
            ):
                self._current_table.rows.append(self._current_row)
            self._current_row = None


def extract_sama_pos_weekly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract weekly POS rows from a supported HTML table."""

    parser = _HTMLTableParser()
    parser.feed(html)

    for table in parser.tables:
        extracted_rows = _extract_table_rows(
            table=table,
            source_locator=source_locator,
            source_url=source_url,
        )
        if extracted_rows:
            return extracted_rows

    return None


def extract_sama_pos_weekly_rows_from_json(
    *,
    body: dict[str, Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract weekly POS rows from a supported POS report text bundle."""

    reports = body.get("reports")
    if not isinstance(reports, list):
        return None

    extracted_rows: list[dict[str, Any]] = []
    seen_periods: set[tuple[str, str]] = set()

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
            period_key = (record["week_start_date"], record["week_end_date"])
            if period_key in seen_periods:
                continue

            seen_periods.add(period_key)
            extracted_rows.append(record)

    extracted_rows.sort(key=lambda row: (row["week_start_date"], row["week_end_date"]))
    return extracted_rows or None


def _extract_table_rows(
    *,
    table: _ParsedTable,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]]:
    header_row_index = next(
        (index for index, row in enumerate(table.rows) if row.has_header_cells),
        None,
    )
    if header_row_index is None:
        return []

    header_mapping = _resolve_header_mapping(table.rows[header_row_index].cells)
    if header_mapping is None:
        return []

    extracted_rows: list[dict[str, Any]] = []
    for row in table.rows[header_row_index + 1 :]:
        if not any(cell.strip() for cell in row.cells):
            continue
        record = _extract_record(
            row_cells=row.cells,
            header_mapping=header_mapping,
            source_locator=source_locator,
            source_url=source_url,
            source_table_title=table.caption,
        )
        if record is None:
            return []
        extracted_rows.append(record)

    return extracted_rows


def _resolve_header_mapping(headers: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}

    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if normalized in _WEEK_START_HEADER_ALIASES and "week_start_date" not in mapping:
            mapping["week_start_date"] = index
        elif normalized in _WEEK_END_HEADER_ALIASES and "week_end_date" not in mapping:
            mapping["week_end_date"] = index
        elif normalized in _WEEK_PERIOD_HEADER_ALIASES and "week_period" not in mapping:
            mapping["week_period"] = index
        elif (
            normalized in _TRANSACTION_COUNT_HEADER_ALIASES
            and "transaction_count" not in mapping
        ):
            mapping["transaction_count"] = index
        elif (
            normalized in _TRANSACTION_VALUE_HEADER_ALIASES
            and "transaction_value_sar" not in mapping
        ):
            mapping["transaction_value_sar"] = index

    if "transaction_count" not in mapping or "transaction_value_sar" not in mapping:
        return None

    if not {"week_start_date", "week_end_date"}.issubset(mapping) and "week_period" not in mapping:
        return None

    return mapping


def _extract_record(
    *,
    row_cells: list[str],
    header_mapping: dict[str, int],
    source_locator: str,
    source_url: str,
    source_table_title: str | None,
) -> dict[str, Any] | None:
    try:
        period_text = _row_value(row_cells, header_mapping, "week_period")
        if period_text is None:
            start_date = _parse_date_text(_row_value(row_cells, header_mapping, "week_start_date"))
            end_date = _parse_date_text(_row_value(row_cells, header_mapping, "week_end_date"))
            source_period_text = f"{start_date.isoformat()} to {end_date.isoformat()}"
        else:
            start_date, end_date = _parse_period_range(period_text)
            source_period_text = period_text

        transaction_count = _parse_integer_text(
            _row_value(row_cells, header_mapping, "transaction_count")
        )
        transaction_value_sar = _parse_decimal_text(
            _row_value(row_cells, header_mapping, "transaction_value_sar")
        )
    except ValueError:
        return None

    record: dict[str, Any] = {
        "week_start_date": start_date.isoformat(),
        "week_end_date": end_date.isoformat(),
        "transaction_count": transaction_count,
        "transaction_value_sar": transaction_value_sar,
        "average_ticket_sar": round(
            transaction_value_sar / transaction_count,
            2,
        )
        if transaction_count
        else 0.0,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_period_text": source_period_text,
    }
    if source_table_title:
        record["source_table_title"] = source_table_title
    return record


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

    table_1_section = _extract_table_1_section(normalized_text)
    if table_1_section is None:
        return None

    periods = _extract_table_1_periods(table_1_section)
    if not periods:
        return None

    numbers = _extract_total_row_numbers(table_1_section)
    expected_measure_count = len(periods) * 2
    if len(numbers) < expected_measure_count:
        return None

    numbers = numbers[:expected_measure_count]
    records: list[dict[str, Any]] = []
    for period_index, period_text in enumerate(periods):
        start_date, end_date = _parse_period_range(period_text)
        metric_index = period_index * 2
        transaction_count_thousand = _parse_decimal_text(numbers[metric_index])
        transaction_value_thousand = _parse_decimal_text(numbers[metric_index + 1])
        if not _is_supported_metric_pair(
            transaction_count_thousand=transaction_count_thousand,
            transaction_value_thousand=transaction_value_thousand,
        ):
            return None
        transaction_count = int(round(transaction_count_thousand * 1000))
        transaction_value_sar = round(transaction_value_thousand * 1000, 2)
        records.append(
            {
                "week_start_date": start_date.isoformat(),
                "week_end_date": end_date.isoformat(),
                "transaction_count": transaction_count,
                "transaction_value_sar": transaction_value_sar,
                "average_ticket_sar": round(
                    transaction_value_sar / transaction_count,
                    2,
                )
                if transaction_count
                else 0.0,
                "source_locator": source_locator,
                "source_url": source_url,
                "source_period_text": period_text,
                "source_table_title": _TABLE_1_TITLE,
                "source_report_url": report_url,
                "source_release_title": _POS_RELEASE_TITLE,
            }
        )

    return records


def _row_value(
    row_cells: list[str],
    header_mapping: dict[str, int],
    field_name: str,
) -> str | None:
    index = header_mapping.get(field_name)
    if index is None:
        return None
    if index >= len(row_cells):
        raise ValueError(f"row is missing expected cell for {field_name}")
    return row_cells[index].strip()


def _normalize_header(text: str) -> str:
    normalized = _HEADER_NORMALIZATION_PATTERN.sub(" ", text.lower()).strip()
    return " ".join(normalized.split())


def _normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _extract_table_1_section(normalized_text: str) -> str | None:
    match = _TABLE_1_SECTION_PATTERN.search(normalized_text)
    if match is None:
        return None
    return match.group("section").strip()


def _extract_table_1_periods(table_1_section: str) -> list[str]:
    periods: list[str] = []
    for match in _TABLE_1_PERIOD_PATTERN.finditer(table_1_section):
        normalized_period = _normalize_period_text(match.group(0))
        if normalized_period not in periods:
            periods.append(normalized_period)
    return periods


def _extract_total_row_numbers(table_1_section: str) -> list[str]:
    match = _TOTAL_ROW_PATTERN.search(table_1_section)
    if match is None:
        return []
    return _REPORT_NUMBER_PATTERN.findall(match.group("metrics"))


def _has_supported_thousand_units(normalized_text: str) -> bool:
    return bool(
        _VALUE_IN_THOUSAND_PATTERN.search(normalized_text)
        and _COUNT_IN_THOUSAND_PATTERN.search(normalized_text)
    )


def _is_supported_metric_pair(
    *,
    transaction_count_thousand: float,
    transaction_value_thousand: float,
) -> bool:
    return (
        transaction_count_thousand >= 1000
        and transaction_value_thousand >= 1000
        and transaction_value_thousand > transaction_count_thousand
    )


def _normalize_period_text(value: str) -> str:
    return " ".join(value.split())


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


def _parse_integer_text(value: str | None) -> int:
    if value is None:
        raise ValueError("integer text must not be missing")

    cleaned = _INTEGER_CLEANUP_PATTERN.sub("", value)
    if not cleaned:
        raise ValueError(f"unsupported integer value: {value}")
    return int(cleaned)


def _parse_decimal_text(value: str | None) -> float:
    if value is None:
        raise ValueError("decimal text must not be missing")

    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if not cleaned:
        raise ValueError(f"unsupported decimal value: {value}")
    return float(cleaned)
