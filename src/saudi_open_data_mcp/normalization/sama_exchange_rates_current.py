"""Dataset-specific extraction for the SAMA current exchange-rates surface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from typing import Any

SAMA_EXCHANGE_RATES_CURRENT_HTML_TABLE_LIMITATION = (
    "sama_exchange_rates_current_html_requires_supported_daily_quote_table"
)
SAMA_EXCHANGE_RATES_CURRENT_JSON_BUNDLE_LIMITATION = (
    "sama_exchange_rates_current_json_requires_supported_current_quote_bundle"
)

_HEADER_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_CURRENCY_KEY_NORMALIZATION_PATTERN = re.compile(r"[^A-Z0-9]+")
_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_TAG_PATTERN = re.compile(r"<[^>]+>")
_ATTR_PATTERN = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)
        (?:\s*=\s*
            (?:
                "([^"]*)"
                |'([^']*)'
                |([^\s>]+)
            )
        )?
    """,
    flags=re.VERBOSE,
)
_TABLE_PATTERN = re.compile(
    r"<table\b(?P<attrs>[^>]*)>(?P<body>.*?)</table>",
    flags=re.IGNORECASE | re.DOTALL,
)
_ROW_PATTERN = re.compile(
    r"<tr\b(?P<attrs>[^>]*)>(?P<body>.*?)</tr>",
    flags=re.IGNORECASE | re.DOTALL,
)
_CELL_PATTERN = re.compile(
    r"<t(?P<tag>[dh])\b(?P<attrs>[^>]*)>(?P<body>.*?)</t[dh]>",
    flags=re.IGNORECASE | re.DOTALL,
)
_SELECT_PATTERN = re.compile(
    r"<select\b(?P<attrs>[^>]*)>(?P<body>.*?)</select>",
    flags=re.IGNORECASE | re.DOTALL,
)
_OPTION_PATTERN = re.compile(
    r"<option\b(?P<attrs>[^>]*)>(?P<body>.*?)</option>",
    flags=re.IGNORECASE | re.DOTALL,
)
_RESULTS_COUNT_PATTERN = re.compile(
    r"Number of result is\s*(?P<count>\d+)",
    flags=re.IGNORECASE,
)
_DATE_FORMATS = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",
    "%d %B, %Y",
)
_EXPECTED_HEADER_CELLS = (
    "currency against s r",
    "closing price",
    "last updated date",
)


@dataclass(frozen=True, slots=True)
class _PageRecord:
    fields: dict[str, Any]
    as_of_date: date


@dataclass(frozen=True, slots=True)
class _ParsedPage:
    records: tuple[_PageRecord, ...]
    total_results_count: int | None
    has_pager: bool


def extract_sama_exchange_rates_current_rows_from_json(
    body: dict[str, Any],
    *,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical current quote rows from a connector-built page bundle."""

    pages = body.get("pages")
    if not isinstance(pages, list) or not pages:
        return None

    bundle_date = _resolve_bundle_date(body.get("current_date_text"))
    expected_total = _resolve_expected_total(body.get("total_results_count"))
    combined_rows: list[dict[str, Any]] = []
    seen_currency_codes: set[str] = set()
    seen_page_numbers: set[int] = set()

    for index, page_entry in enumerate(pages, start=1):
        if not isinstance(page_entry, dict):
            return None

        page_number = page_entry.get("page_number", index)
        if not isinstance(page_number, int) or page_number <= 0:
            return None
        if page_number in seen_page_numbers:
            return None
        seen_page_numbers.add(page_number)

        page_html = page_entry.get("body")
        if not isinstance(page_html, str):
            return None

        page_url = page_entry.get("page_url")
        if page_url is not None and not isinstance(page_url, str):
            return None

        parsed_page = _parse_supported_quote_page(
            html=page_html,
            source_locator=source_locator,
            source_url=source_url,
            page_url=page_url or source_url,
            page_number=page_number,
        )
        if parsed_page is None or not parsed_page.records:
            return None

        if expected_total is None:
            expected_total = parsed_page.total_results_count
        elif (
            parsed_page.total_results_count is not None
            and parsed_page.total_results_count != expected_total
        ):
            return None

        for record in parsed_page.records:
            if bundle_date is None:
                bundle_date = record.as_of_date
            elif record.as_of_date != bundle_date:
                return None

            currency_code = record.fields["currency_code"]
            if currency_code in seen_currency_codes:
                return None
            seen_currency_codes.add(currency_code)
            combined_rows.append(record.fields)

    if expected_total is None or expected_total != len(combined_rows):
        return None
    if bundle_date is None:
        return None

    return combined_rows


def extract_sama_exchange_rates_current_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical current quote rows from one complete supported HTML page."""

    parsed_page = _parse_supported_quote_page(
        html=html,
        source_locator=source_locator,
        source_url=source_url,
        page_url=source_url,
        page_number=None,
    )
    if parsed_page is None or not parsed_page.records:
        return None
    if parsed_page.has_pager:
        return None
    if (
        parsed_page.total_results_count is not None
        and parsed_page.total_results_count != len(parsed_page.records)
    ):
        return None

    expected_date = parsed_page.records[0].as_of_date
    if any(record.as_of_date != expected_date for record in parsed_page.records):
        return None

    return [record.fields for record in parsed_page.records]


def _parse_supported_quote_page(
    *,
    html: str,
    source_locator: str,
    source_url: str,
    page_url: str,
    page_number: int | None,
) -> _ParsedPage | None:
    option_mapping = _extract_currency_option_mapping(html)
    if not option_mapping:
        return None

    table_html = _resolve_results_table_html(html)
    if table_html is None:
        return None

    total_results_count = _extract_total_results_count(html)
    records: list[_PageRecord] = []
    has_pager = False
    header_seen = False

    for row_match in _ROW_PATTERN.finditer(table_html):
        row_attrs = _parse_html_attributes(row_match.group("attrs"))
        row_html = row_match.group("body")
        cells = _extract_row_cells(row_html)
        if not cells:
            continue

        normalized_header = tuple(_normalize_header(cell) for cell in cells[:3])
        if normalized_header == _EXPECTED_HEADER_CELLS:
            header_seen = True
            continue

        if _is_pager_row(row_attrs=row_attrs, row_html=row_html, cells=cells):
            has_pager = True
            continue

        if not header_seen or len(cells) < 3:
            continue

        source_currency_text = cells[0]
        closing_price_text = cells[1]
        source_last_updated_date_text = cells[2]
        currency_code = option_mapping.get(_normalize_currency_key(source_currency_text))
        if currency_code is None:
            return None

        try:
            as_of_date = _parse_date_text(source_last_updated_date_text)
            closing_rate_sar = _parse_decimal_text(closing_price_text)
        except ValueError:
            return None

        fields: dict[str, Any] = {
            "as_of_date": as_of_date.isoformat(),
            "currency_code": currency_code,
            "currency_name": source_currency_text,
            "quote_currency_code": "SAR",
            "quote_currency_name": "Saudi Riyal",
            "closing_rate_sar": closing_rate_sar,
            "source_locator": source_locator,
            "source_url": source_url,
            "source_currency_text": source_currency_text,
            "source_last_updated_date_text": source_last_updated_date_text,
        }
        if page_number is not None:
            fields["source_page_number"] = page_number
        if page_url != source_url:
            fields["source_page_url"] = page_url

        records.append(_PageRecord(fields=fields, as_of_date=as_of_date))

    if not header_seen or not records:
        return None

    return _ParsedPage(
        records=tuple(records),
        total_results_count=total_results_count,
        has_pager=has_pager,
    )


def _extract_currency_option_mapping(html: str) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for select_match in _SELECT_PATTERN.finditer(html):
        select_attrs = _parse_html_attributes(select_match.group("attrs"))
        select_name = str(select_attrs.get("name", "")).casefold()
        if "ddlcurrencies" not in select_name:
            continue

        for option_match in _OPTION_PATTERN.finditer(select_match.group("body")):
            option_attrs = _parse_html_attributes(option_match.group("attrs"))
            code = _parse_currency_code(str(option_attrs.get("value", "")))
            if code is None:
                continue

            display_name = _clean_html_text(option_match.group("body"))
            if not display_name:
                continue

            key = _normalize_currency_key(display_name)
            existing = mapping.get(key)
            if existing is not None and existing != code:
                return {}
            mapping[key] = code

        if mapping:
            return mapping

    return {}


def _resolve_results_table_html(html: str) -> str | None:
    for table_match in _TABLE_PATTERN.finditer(html):
        attrs = _parse_html_attributes(table_match.group("attrs"))
        table_id = str(attrs.get("id", ""))
        table_class = str(attrs.get("class", ""))
        if "dgResults" in table_id or "tableCurrency" in table_class:
            return table_match.group("body")
    return None


def _extract_row_cells(row_html: str) -> list[str]:
    cells: list[str] = []
    for cell_match in _CELL_PATTERN.finditer(row_html):
        cells.append(_clean_html_text(cell_match.group("body")))
    return cells


def _is_pager_row(
    *,
    row_attrs: dict[str, str | bool],
    row_html: str,
    cells: list[str],
) -> bool:
    row_class = str(row_attrs.get("class", "")).casefold()
    if "pagerstyle" in row_class:
        return True
    if "javascript:__doPostBack".casefold() in unescape(row_html).casefold():
        return True
    if len(cells) == 1:
        for cell_match in _CELL_PATTERN.finditer(row_html):
            cell_attrs = _parse_html_attributes(cell_match.group("attrs"))
            if "colspan" in cell_attrs:
                return True
    return False


def _extract_total_results_count(html: str) -> int | None:
    match = _RESULTS_COUNT_PATTERN.search(_clean_html_text(html))
    if match is None:
        return None
    return int(match.group("count"))


def _resolve_bundle_date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return _parse_date_text(value)
    except ValueError:
        return None


def _resolve_expected_total(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        return None
    return value


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


def _parse_currency_code(value: str) -> str | None:
    cleaned = re.sub(r"[^A-Z]", "", value.upper())
    if len(cleaned) != 3:
        return None
    return cleaned


def _clean_html_text(fragment: str) -> str:
    text = unescape(_TAG_PATTERN.sub(" ", fragment)).replace("\xa0", " ")
    return " ".join(text.split())


def _parse_html_attributes(fragment: str) -> dict[str, str | bool]:
    attributes: dict[str, str | bool] = {}
    for match in _ATTR_PATTERN.finditer(fragment):
        name = match.group(1).casefold()
        value = match.group(2) or match.group(3) or match.group(4)
        attributes[name] = value if value is not None else True
    return attributes


def _normalize_header(value: str) -> str:
    normalized = _HEADER_NORMALIZATION_PATTERN.sub(" ", value.strip().casefold()).strip()
    return normalized


def _normalize_currency_key(value: str) -> str:
    normalized = _CURRENCY_KEY_NORMALIZATION_PATTERN.sub(
        " ",
        value.upper().strip(),
    ).strip()
    return normalized
