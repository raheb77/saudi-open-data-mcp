"""Dataset-specific HTML extraction for the canonical SAMA weekly money-supply contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SAMA_MONEY_SUPPLY_WEEKLY_HTML_TABLE_LIMITATION = (
    "sama_money_supply_weekly_html_requires_supported_weekly_aggregate_table"
)

_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",
    "%d %B, %Y",
)
_WEEK_END_HEADER_ALIASES = frozenset(
    {
        "week end",
        "week ending",
        "week ending date",
        "date",
        "week end date",
    }
)
_AGGREGATE_HEADER_ALIASES = {
    "m0": ("m0", "M0"),
    "m0 reserve money": ("m0", "M0"),
    "reserve money": ("m0", "M0"),
    "m1": ("m1", "M1"),
    "m1 narrow money": ("m1", "M1"),
    "narrow money": ("m1", "M1"),
    "m2": ("m2", "M2"),
    "m2 broad money": ("m2", "M2"),
    "broad money": ("m2", "M2"),
    "m3": ("m3", "M3"),
    "m3 broadest money": ("m3", "M3"),
}


@dataclass(slots=True)
class _ParsedRow:
    cells: list[str] = field(default_factory=list)
    has_header_cells: bool = False


@dataclass(slots=True)
class _ParsedTable:
    caption: str | None = None
    rows: list[_ParsedRow] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _AggregateColumn:
    index: int
    code: str
    name: str
    source_header: str


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


def extract_sama_money_supply_weekly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical weekly money-supply observations from a supported HTML table."""

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

    week_end_index, aggregate_columns = _resolve_header_mapping(
        table.rows[header_row_index].cells
    )
    if week_end_index is None or not aggregate_columns:
        return []

    extracted_rows: list[dict[str, Any]] = []
    for row in table.rows[header_row_index + 1 :]:
        if not any(cell.strip() for cell in row.cells):
            continue
        records = _extract_records_for_row(
            row_cells=row.cells,
            week_end_index=week_end_index,
            aggregate_columns=aggregate_columns,
            source_locator=source_locator,
            source_url=source_url,
            source_table_title=table.caption,
        )
        if records is None:
            return []
        extracted_rows.extend(records)

    return extracted_rows


def _resolve_header_mapping(
    headers: list[str],
) -> tuple[int | None, tuple[_AggregateColumn, ...]]:
    week_end_index: int | None = None
    aggregate_columns: list[_AggregateColumn] = []

    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if normalized in _WEEK_END_HEADER_ALIASES and week_end_index is None:
            week_end_index = index
            continue

        aggregate = _AGGREGATE_HEADER_ALIASES.get(normalized)
        if aggregate is None:
            continue

        aggregate_columns.append(
            _AggregateColumn(
                index=index,
                code=aggregate[0],
                name=aggregate[1],
                source_header=header.strip(),
            )
        )

    return week_end_index, tuple(aggregate_columns)


def _extract_records_for_row(
    *,
    row_cells: list[str],
    week_end_index: int,
    aggregate_columns: tuple[_AggregateColumn, ...],
    source_locator: str,
    source_url: str,
    source_table_title: str | None,
) -> list[dict[str, Any]] | None:
    try:
        week_end_date = _parse_date_text(_row_value(row_cells, week_end_index))
    except ValueError:
        return None

    records: list[dict[str, Any]] = []
    for aggregate in aggregate_columns:
        try:
            amount_sar = _parse_decimal_text(_row_value(row_cells, aggregate.index))
        except ValueError:
            return None

        record: dict[str, Any] = {
            "week_end_date": week_end_date.isoformat(),
            "monetary_aggregate_code": aggregate.code,
            "monetary_aggregate_name": aggregate.name,
            "amount_sar": amount_sar,
            "source_locator": source_locator,
            "source_url": source_url,
            "source_series_name": aggregate.source_header or aggregate.name,
            "source_week_end_text": _row_value(row_cells, week_end_index),
        }
        if source_table_title:
            record["source_table_title"] = source_table_title
        records.append(record)

    return records


def _normalize_header(text: str) -> str:
    normalized = _HEADER_NORMALIZATION_PATTERN.sub(" ", text.lower()).strip()
    return " ".join(normalized.split())


def _row_value(row_cells: list[str], index: int) -> str:
    if index >= len(row_cells):
        raise ValueError(f"row is missing expected cell at index {index}")
    return row_cells[index].strip()


def _parse_date_text(value: str) -> date:
    normalized = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date value: {value}")


def _parse_decimal_text(value: str) -> float:
    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if not cleaned:
        raise ValueError(f"unsupported decimal value: {value}")
    return float(cleaned)
