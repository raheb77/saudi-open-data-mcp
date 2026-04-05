"""Dataset-specific HTML extraction for a narrow stats.gov.sa GDP contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

STATS_GOV_SA_REAL_GDP_GROWTH_QUARTERLY_HTML_LIMITATION = (
    "stats_gov_sa_real_gdp_growth_quarterly_html_requires_supported_release_cards"
)

_TITLE_VALUE_PATTERNS = (
    re.compile(
        r"\b(?:GASTAT\s+)?Real GDP grows by\s+([0-9]+(?:\.[0-9]+)?)%\s+"
        r"in\s+Q([1-4])(?:\s+of|/)?\s*(\d{4})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:GASTAT\s+)?Real GDP (?:decreases|decreased|declines|declined|"
        r"falls|fell|contracts|contracted) by\s+([0-9]+(?:\.[0-9]+)?)%\s+"
        r"in\s+Q([1-4])(?:\s+of|/)?\s*(\d{4})",
        flags=re.IGNORECASE,
    ),
)
_QUARTER_PATTERNS = (
    re.compile(
        r"\bGross Domestic Product\s+\(GDP\)\s+for\s+Q([1-4])(?:\s+of|/)?\s*(\d{4})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bQ([1-4])(?:\s+of|/)?\s*(\d{4})",
        flags=re.IGNORECASE,
    ),
)
_SUMMARY_RATE_PATTERNS = (
    (
        re.compile(
            r"\breal GDP\s+(?:grew|increased|rose)\s+by\s+([0-9]+(?:\.[0-9]+)?)%\s+"
            r"compared to the same (?:period|quarter) in \d{4}",
            flags=re.IGNORECASE,
        ),
        1.0,
    ),
    (
        re.compile(
            r"\breal GDP\s+(?:decreased|declined|fell|contracted)\s+by\s+"
            r"([0-9]+(?:\.[0-9]+)?)%\s+compared to the same (?:period|quarter) in \d{4}",
            flags=re.IGNORECASE,
        ),
        -1.0,
    ),
    (
        re.compile(
            r"\breal GDP achieved a growth rate of\s+([0-9]+(?:\.[0-9]+)?)%",
            flags=re.IGNORECASE,
        ),
        1.0,
    ),
)
_TITLE_NORMALIZATION_PATTERN = re.compile(r"\s+")
_RELEASE_DATE_FORMAT = "%d-%m-%Y"


@dataclass(slots=True)
class _ParsedCard:
    title_chunks: list[str] = field(default_factory=list)
    date_chunks: list[str] = field(default_factory=list)
    summary_chunks: list[str] = field(default_factory=list)
    release_url: str | None = None

    @property
    def title(self) -> str:
        return " ".join(self.title_chunks).strip()

    @property
    def release_date_text(self) -> str:
        return " ".join(self.date_chunks).strip()

    @property
    def summary_text(self) -> str:
        return " ".join(self.summary_chunks).strip()


class _GDPNewsCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[_ParsedCard] = []
        self._current_card: _ParsedCard | None = None
        self._card_div_depth = 0
        self._capture_title = False
        self._capture_date = False
        self._summary_div_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        class_names = _class_names(attributes.get("class"))

        if tag == "div" and {"card", "card-box", "media-card"}.issubset(class_names):
            if self._current_card is None:
                self._current_card = _ParsedCard()
                self._card_div_depth = 1
            else:
                self._card_div_depth += 1
            return

        if self._current_card is None:
            return

        if tag == "div":
            self._card_div_depth += 1
            if "card-text" in class_names:
                self._summary_div_depth += 1
            return

        if tag == "h3" and "card-title" in class_names:
            self._capture_title = True
            return

        if tag == "p" and "card-date" in class_names:
            self._capture_date = True
            return

        if tag == "a":
            href = attributes.get("href", "").strip()
            if href.startswith("http") and "/en/w/" in href:
                self._current_card.release_url = href

    def handle_data(self, data: str) -> None:
        if self._current_card is None:
            return

        text = " ".join(data.split())
        if not text:
            return

        if self._capture_title:
            self._current_card.title_chunks.append(text)
        elif self._capture_date:
            self._current_card.date_chunks.append(text)
        elif self._summary_div_depth > 0:
            self._current_card.summary_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current_card is None:
            return

        if tag == "h3":
            self._capture_title = False
            return

        if tag == "p":
            self._capture_date = False
            return

        if tag == "div":
            if self._summary_div_depth > 0:
                self._summary_div_depth -= 1
            self._card_div_depth -= 1
            if self._card_div_depth == 0:
                self.cards.append(self._current_card)
                self._current_card = None


def extract_stats_gov_sa_real_gdp_growth_quarterly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract narrow quarterly headline GDP observations from supported release cards."""

    parser = _GDPNewsCardParser()
    parser.feed(html)

    extracted_rows: list[dict[str, Any]] = []
    seen_release_urls: set[str] = set()

    for card in parser.cards:
        record = _extract_record(
            card=card,
            source_locator=source_locator,
            source_url=source_url,
        )
        if record is None:
            continue

        release_url = record["source_release_url"]
        if release_url in seen_release_urls:
            continue

        seen_release_urls.add(release_url)
        extracted_rows.append(record)

    return extracted_rows or None


def _extract_record(
    *,
    card: _ParsedCard,
    source_locator: str,
    source_url: str,
) -> dict[str, Any] | None:
    title = _normalize_text(card.title)
    summary_text = _normalize_text(card.summary_text)
    release_date_text = _normalize_text(card.release_date_text)
    release_url = card.release_url

    if not title or not summary_text or not release_date_text or not release_url:
        return None
    if not _looks_like_headline_real_gdp_release(title, summary_text):
        return None

    try:
        observation_quarter, value_percent = _extract_observation_quarter_and_value_percent(
            title=title,
            summary_text=summary_text,
        )
    except ValueError:
        return None
    try:
        release_date = _parse_release_date(release_date_text)
    except ValueError:
        return None

    return {
        "observation_quarter": observation_quarter,
        "gdp_series_code": "real_gdp_growth_rate_yoy",
        "gdp_series_name": "Real GDP Growth Rate (Year-on-Year)",
        "release_date": release_date.isoformat(),
        "value_percent": value_percent,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_release_url": release_url,
        "source_release_title": title,
        "source_release_date_text": release_date_text,
        "source_summary_text": summary_text,
    }


def _looks_like_headline_real_gdp_release(title: str, summary_text: str) -> bool:
    normalized_title = title.lower()
    normalized_summary = summary_text.lower()
    return (
        ("real gdp" in normalized_title or "gross domestic product" in normalized_summary)
        and "real gdp" in normalized_summary
        and (
            "compared to the same period" in normalized_summary
            or "compared to the same quarter" in normalized_summary
            or "growth rate" in normalized_summary
        )
    )


def _extract_observation_quarter_and_value_percent(
    *,
    title: str,
    summary_text: str,
) -> tuple[str, float]:
    for index, pattern in enumerate(_TITLE_VALUE_PATTERNS):
        match = pattern.search(title)
        if match is None:
            continue
        multiplier = -1.0 if index == 1 else 1.0
        return (_format_quarter(match.group(3), match.group(2)), multiplier * float(match.group(1)))

    return (
        _extract_observation_quarter(title, summary_text),
        _extract_value_percent(summary_text),
    )


def _extract_observation_quarter(title: str, summary_text: str) -> str:
    for candidate_text in (summary_text, title):
        for pattern in _QUARTER_PATTERNS:
            match = pattern.search(candidate_text)
            if match is not None:
                return _format_quarter(match.group(2), match.group(1))
    raise ValueError("supported gdp release card did not expose a parseable quarter")


def _extract_value_percent(summary_text: str) -> float:
    for pattern, multiplier in _SUMMARY_RATE_PATTERNS:
        match = pattern.search(summary_text)
        if match is not None:
            return multiplier * float(match.group(1))
    raise ValueError("supported gdp release card did not expose a parseable growth rate")


def _parse_release_date(text: str) -> date:
    return datetime.strptime(text, _RELEASE_DATE_FORMAT).date()


def _normalize_text(value: str) -> str:
    normalized = value.replace("’", "'")
    return _TITLE_NORMALIZATION_PATTERN.sub(" ", normalized).strip()


def _class_names(class_value: str | None) -> set[str]:
    if not class_value:
        return set()
    return {name for name in class_value.split() if name}


def _format_quarter(year: str, quarter: str) -> str:
    return f"{year}-Q{quarter}"
