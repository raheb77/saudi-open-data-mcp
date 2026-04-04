"""Dataset-specific HTML extraction for the canonical SAMA POS weekly contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SAMA_POS_WEEKLY_HTML_TABLE_LIMITATION = (
    "sama_pos_weekly_html_requires_supported_weekly_summary_table"
)

_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_INTEGER_CLEANUP_PATTERN = re.compile(r"[^0-9\-]+")
_PERIOD_SEPARATOR_PATTERN = re.compile(r"\s+(?:to|-|–|—)\s+")

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
