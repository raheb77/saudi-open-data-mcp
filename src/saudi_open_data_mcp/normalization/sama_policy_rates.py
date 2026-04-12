"""Dataset-specific HTML extraction for SAMA repo and reverse-repo policy-rate contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SAMA_POLICY_RATE_HTML_LIMITATION = (
    "sama_policy_rate_html_requires_supported_effective_date_and_rate_text"
)

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
_EFFECTIVE_DATE_PATTERNS = (
    re.compile(r"\beffective date\b\s*:?\s*([A-Za-z0-9,\-\/ ]+)", re.IGNORECASE),
    re.compile(r"\beffective from\b\s*:?\s*([A-Za-z0-9,\-\/ ]+)", re.IGNORECASE),
    re.compile(r"\bas of\b\s*:?\s*([A-Za-z0-9,\-\/ ]+)", re.IGNORECASE),
)
_RATE_PATTERNS = (
    re.compile(r"\brate\b\s*:?\s*([0-9][0-9,.\s]*%?)", re.IGNORECASE),
    re.compile(r"([0-9][0-9,.\s]*%)", re.IGNORECASE),
)
_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_EFFECTIVE_DATE_HEADER_ALIASES = frozenset(
    {
        "effective date",
        "effective from",
        "date",
    }
)
_RATE_HEADER_ALIASES = frozenset(
    {
        "rate",
        "repo rate",
        "reverse repo rate",
        "official repo rate",
    }
)
_PUBLISH_DATE_HEADER_ALIASES = frozenset({"publish date"})
_CHANGE_POINTS_HEADER_ALIASES = frozenset({"change points", "change points bps"})
_REPO_RATE_PAGE_MARKERS = frozenset({"repo rate", "official repo rate"})
_REVERSE_REPO_RATE_PAGE_MARKERS = frozenset(
    {"reverse repo rate", "official reverse repo rate"}
)


@dataclass(slots=True)
class _ParsedRow:
    cells: list[str] = field(default_factory=list)
    has_header_cells: bool = False


@dataclass(slots=True)
class _ParsedTable:
    caption: str | None = None
    rows: list[_ParsedRow] = field(default_factory=list)


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_text: list[str] = []
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


def extract_sama_policy_rate_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
    policy_rate_code: str,
    policy_rate_name: str,
) -> list[dict[str, Any]] | None:
    """Extract one canonical policy-rate observation from a supported HTML page."""

    parser = _HTMLTextParser()
    parser.feed(html)

    extracted_from_table = _extract_from_tables(
        tables=parser.tables,
        source_locator=source_locator,
        source_url=source_url,
        policy_rate_code=policy_rate_code,
        policy_rate_name=policy_rate_name,
    )
    if extracted_from_table is not None:
        return extracted_from_table

    effective_date = _extract_effective_date(parser.visible_text)
    rate = _extract_rate_percent(parser.visible_text)
    if effective_date is None or rate is None:
        return None

    return [
        _build_record(
            effective_date=effective_date[0],
            source_date_text=effective_date[1],
            rate_percent=rate[0],
            source_rate_text=rate[1],
            source_locator=source_locator,
            source_url=source_url,
            policy_rate_code=policy_rate_code,
            policy_rate_name=policy_rate_name,
            source_table_title=None,
        )
    ]


def extract_sama_repo_rate_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical repo-rate observations from the official historical table."""

    parser = _HTMLTextParser()
    parser.feed(html)

    if not _page_mentions_repo_rate(visible_text=parser.visible_text):
        return None

    extracted_from_table = _extract_repo_rate_history_from_tables(
        tables=parser.tables,
        source_locator=source_locator,
        source_url=source_url,
    )
    if extracted_from_table is not None:
        return extracted_from_table

    return extract_sama_policy_rate_rows_from_html(
        html=html,
        source_locator=source_locator,
        source_url=source_url,
        policy_rate_code="repo_rate",
        policy_rate_name="Official Repo Rate",
    )


def _extract_from_tables(
    *,
    tables: list[_ParsedTable],
    source_locator: str,
    source_url: str,
    policy_rate_code: str,
    policy_rate_name: str,
) -> list[dict[str, Any]] | None:
    for table in tables:
        header_row_index = next(
            (index for index, row in enumerate(table.rows) if row.has_header_cells),
            None,
        )
        if header_row_index is None:
            continue

        header_mapping = _resolve_header_mapping(table.rows[header_row_index].cells)
        if header_mapping is None:
            continue

        for row in table.rows[header_row_index + 1 :]:
            if not any(cell.strip() for cell in row.cells):
                continue
            try:
                effective_date_text = _row_value(row.cells, header_mapping["effective_date"])
                rate_text = _row_value(row.cells, header_mapping["rate_percent"])
                effective_date = _parse_date_text(effective_date_text)
                rate_percent = _parse_percent_text(rate_text)
            except ValueError:
                return None

            return [
                _build_record(
                    effective_date=effective_date,
                    source_date_text=effective_date_text,
                    rate_percent=rate_percent,
                    source_rate_text=rate_text,
                    source_locator=source_locator,
                    source_url=source_url,
                    policy_rate_code=policy_rate_code,
                    policy_rate_name=policy_rate_name,
                    source_table_title=table.caption,
                )
            ]

    return None


def _extract_repo_rate_history_from_tables(
    *,
    tables: list[_ParsedTable],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    for table in tables:
        header_row_index = next(
            (index for index, row in enumerate(table.rows) if row.has_header_cells),
            None,
        )
        if header_row_index is None:
            continue

        header_mapping = _resolve_repo_rate_history_header_mapping(
            table.rows[header_row_index].cells
        )
        if header_mapping is None:
            continue

        records: list[dict[str, Any]] = []
        seen_effective_dates: set[str] = set()
        for row in table.rows[header_row_index + 1 :]:
            if not any(cell.strip() for cell in row.cells):
                continue
            try:
                publish_date_text = _row_value(row.cells, header_mapping["publish_date"])
                rate_text = _row_value(row.cells, header_mapping["rate_percent"])
                effective_date = _parse_date_text(publish_date_text)
                rate_percent = _parse_percent_text(rate_text)
            except ValueError:
                return None

            effective_date_key = effective_date.isoformat()
            if effective_date_key in seen_effective_dates:
                return None
            seen_effective_dates.add(effective_date_key)

            record = _build_record(
                effective_date=effective_date,
                source_date_text=publish_date_text,
                source_date_field_name="source_publish_date_text",
                rate_percent=rate_percent,
                source_rate_text=rate_text,
                source_locator=source_locator,
                source_url=source_url,
                policy_rate_code="repo_rate",
                policy_rate_name="Official Repo Rate",
                source_table_title=table.caption,
            )
            change_points_index = header_mapping.get("change_points_text")
            if change_points_index is not None:
                record["source_change_points_text"] = _row_value(
                    row.cells,
                    change_points_index,
                )
            records.append(record)

        if records:
            return records
        return None

    return None


def _resolve_header_mapping(headers: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}

    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if normalized in _EFFECTIVE_DATE_HEADER_ALIASES and "effective_date" not in mapping:
            mapping["effective_date"] = index
        elif normalized in _RATE_HEADER_ALIASES and "rate_percent" not in mapping:
            mapping["rate_percent"] = index

    if {"effective_date", "rate_percent"}.issubset(mapping):
        return mapping
    return None


def _resolve_repo_rate_history_header_mapping(headers: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}

    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if normalized in _PUBLISH_DATE_HEADER_ALIASES and "publish_date" not in mapping:
            mapping["publish_date"] = index
        elif normalized in _RATE_HEADER_ALIASES and "rate_percent" not in mapping:
            mapping["rate_percent"] = index
        elif normalized in _CHANGE_POINTS_HEADER_ALIASES and "change_points_text" not in mapping:
            mapping["change_points_text"] = index

    if {"publish_date", "rate_percent"}.issubset(mapping):
        return mapping
    return None


def _extract_effective_date(visible_text: list[str]) -> tuple[date, str] | None:
    for text in visible_text:
        for pattern in _EFFECTIVE_DATE_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            candidate = match.group(1).strip()
            try:
                return _parse_date_text(candidate), text.strip()
            except ValueError:
                continue
    return None


def _extract_rate_percent(visible_text: list[str]) -> tuple[float, str] | None:
    for text in visible_text:
        for pattern in _RATE_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            candidate = match.group(1).strip()
            try:
                return _parse_percent_text(candidate), text.strip()
            except ValueError:
                continue
    return None


def _build_record(
    *,
    effective_date: date,
    source_date_text: str,
    rate_percent: float,
    source_rate_text: str,
    source_locator: str,
    source_url: str,
    policy_rate_code: str,
    policy_rate_name: str,
    source_table_title: str | None,
    source_date_field_name: str = "source_effective_date_text",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "effective_date": effective_date.isoformat(),
        "policy_rate_code": policy_rate_code,
        "policy_rate_name": policy_rate_name,
        "rate_percent": rate_percent,
        "source_locator": source_locator,
        "source_url": source_url,
        source_date_field_name: source_date_text,
        "source_rate_text": source_rate_text,
    }
    if source_table_title:
        record["source_table_title"] = source_table_title
    return record


def _parse_date_text(value: str) -> date:
    for format_string in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), format_string).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {value}")


def _parse_percent_text(value: str) -> float:
    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if cleaned in {"", "-", ".", "-."}:
        raise ValueError(f"unsupported rate value: {value}")
    return float(cleaned)


def _row_value(row_cells: list[str], index: int) -> str:
    if index >= len(row_cells):
        raise ValueError("row does not include the expected column")
    value = row_cells[index].strip()
    if not value:
        raise ValueError("row cell is empty")
    return value


def _normalize_header(value: str) -> str:
    return _HEADER_NORMALIZATION_PATTERN.sub(" ", value.strip().casefold()).strip()


def _page_mentions_repo_rate(*, visible_text: list[str]) -> bool:
    for text in visible_text:
        normalized = _normalize_header(text)
        if not normalized:
            continue
        return normalized in _REPO_RATE_PAGE_MARKERS
    return False
