"""Dataset-specific HTML extraction for the canonical SAMA current exchange-rates contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION = (
    "sama_exchange_rates_current_html_requires_supported_daily_quote_table"
)

_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_AS_OF_TEXT_PATTERN = re.compile(
    r"\b(?:as of|updated on|date)\s*:?\s*([A-Za-z0-9,\-\/ ]+)",
    flags=re.IGNORECASE,
)
_COMBINED_CURRENCY_PATTERN = re.compile(
    r"^\s*([A-Z]{3})\s*(?:-|–|—|\(|:)?\s*([A-Za-z][A-Za-z .\-()]+?)\s*\)?\s*$"
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
_CURRENCY_HEADER_ALIASES = frozenset(
    {
        "currency",
        "quoted currency",
        "foreign currency",
    }
)
_CURRENCY_CODE_HEADER_ALIASES = frozenset(
    {
        "currency code",
        "code",
        "ccy code",
    }
)
_CURRENCY_NAME_HEADER_ALIASES = frozenset(
    {
        "currency name",
        "name",
        "currency description",
    }
)
_BUY_RATE_HEADER_ALIASES = frozenset(
    {
        "buy",
        "buy rate",
        "buy rate sar",
        "buy sar",
    }
)
_SELL_RATE_HEADER_ALIASES = frozenset(
    {
        "sell",
        "sell rate",
        "sell rate sar",
        "sell sar",
    }
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
        self.visible_text: list[str] = []
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

        self.visible_text.append(text)
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


@dataclass(frozen=True, slots=True)
class _CurrencyRow:
    currency_code: str
    currency_name: str
    source_currency_text: str


def extract_sama_exchange_rates_current_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical current exchange-rate rows from a supported HTML table."""

    parser = _HTMLTableParser()
    parser.feed(html)
    as_of = _resolve_as_of_date(parser.visible_text)
    if as_of is None:
        return None

    as_of_date, source_as_of_text = as_of
    for table in parser.tables:
        extracted_rows = _extract_table_rows(
            table=table,
            as_of_date=as_of_date,
            source_as_of_text=source_as_of_text,
            source_locator=source_locator,
            source_url=source_url,
        )
        if extracted_rows:
            return extracted_rows

    return None


def _extract_table_rows(
    *,
    table: _ParsedTable,
    as_of_date: date,
    source_as_of_text: str,
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
            as_of_date=as_of_date,
            source_as_of_text=source_as_of_text,
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
        if normalized in _CURRENCY_HEADER_ALIASES and "currency" not in mapping:
            mapping["currency"] = index
        elif normalized in _CURRENCY_CODE_HEADER_ALIASES and "currency_code" not in mapping:
            mapping["currency_code"] = index
        elif normalized in _CURRENCY_NAME_HEADER_ALIASES and "currency_name" not in mapping:
            mapping["currency_name"] = index
        elif normalized in _BUY_RATE_HEADER_ALIASES and "buy_rate_sar" not in mapping:
            mapping["buy_rate_sar"] = index
        elif normalized in _SELL_RATE_HEADER_ALIASES and "sell_rate_sar" not in mapping:
            mapping["sell_rate_sar"] = index

    has_currency_identity = "currency" in mapping or {
        "currency_code",
        "currency_name",
    }.issubset(mapping)
    if not has_currency_identity:
        return None
    if "buy_rate_sar" not in mapping or "sell_rate_sar" not in mapping:
        return None

    return mapping


def _extract_record(
    *,
    row_cells: list[str],
    header_mapping: dict[str, int],
    as_of_date: date,
    source_as_of_text: str,
    source_locator: str,
    source_url: str,
    source_table_title: str | None,
) -> dict[str, Any] | None:
    currency = _extract_currency_identity(row_cells, header_mapping)
    if currency is None:
        return None

    try:
        buy_rate_sar = _parse_decimal_text(_row_value(row_cells, header_mapping["buy_rate_sar"]))
        sell_rate_sar = _parse_decimal_text(_row_value(row_cells, header_mapping["sell_rate_sar"]))
    except ValueError:
        return None

    record: dict[str, Any] = {
        "as_of_date": as_of_date.isoformat(),
        "currency_code": currency.currency_code,
        "currency_name": currency.currency_name,
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "buy_rate_sar": buy_rate_sar,
        "sell_rate_sar": sell_rate_sar,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_currency_text": currency.source_currency_text,
        "source_as_of_text": source_as_of_text,
    }
    if source_table_title:
        record["source_table_title"] = source_table_title
    return record


def _extract_currency_identity(
    row_cells: list[str],
    header_mapping: dict[str, int],
) -> _CurrencyRow | None:
    if "currency" in header_mapping:
        source_text = _row_value(row_cells, header_mapping["currency"])
        return _parse_combined_currency_text(source_text)

    try:
        code = _row_value(row_cells, header_mapping["currency_code"]).strip().upper()
        name = _row_value(row_cells, header_mapping["currency_name"]).strip()
    except (IndexError, KeyError):
        return None

    if not re.fullmatch(r"[A-Z]{3}", code) or not name:
        return None
    return _CurrencyRow(
        currency_code=code,
        currency_name=name,
        source_currency_text=f"{code} - {name}",
    )


def _parse_combined_currency_text(value: str) -> _CurrencyRow | None:
    match = _COMBINED_CURRENCY_PATTERN.match(value.strip())
    if match is None:
        return None

    code = match.group(1).upper()
    name = match.group(2).strip(" -()")
    if not name:
        return None
    return _CurrencyRow(
        currency_code=code,
        currency_name=name,
        source_currency_text=value.strip(),
    )


def _resolve_as_of_date(visible_text: list[str]) -> tuple[date, str] | None:
    for text in visible_text:
        match = _AS_OF_TEXT_PATTERN.search(text)
        if match is None:
            continue
        candidate = match.group(1).strip()
        try:
            return _parse_date_text(candidate), text.strip()
        except ValueError:
            continue
    return None


def _parse_date_text(value: str) -> date:
    for format_string in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), format_string).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {value}")


def _parse_decimal_text(value: str) -> float:
    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if cleaned in {"", "-", ".", "-."}:
        raise ValueError(f"unsupported numeric value: {value}")
    return float(cleaned)


def _row_value(row_cells: list[str], index: int) -> str:
    if index >= len(row_cells):
        raise ValueError("row does not include the expected column")
    value = row_cells[index].strip()
    if not value:
        raise ValueError("row cell is empty")
    return value


def _normalize_header(value: str) -> str:
    normalized = _HEADER_NORMALIZATION_PATTERN.sub(" ", value.strip().casefold()).strip()
    return normalized
