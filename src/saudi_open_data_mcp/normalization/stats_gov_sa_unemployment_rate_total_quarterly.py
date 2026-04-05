"""Dataset-specific HTML extraction for a narrow stats.gov.sa labor contract."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .stats_gov_sa_release_cards import (
    StatsGovSaReleaseCard,
    StatsGovSaReleaseCardParser,
)

STATS_GOV_SA_UNEMPLOYMENT_RATE_TOTAL_QUARTERLY_HTML_LIMITATION = (
    "stats_gov_sa_unemployment_rate_total_quarterly_html_requires_supported_release_cards"
)

_TITLE_VALUE_PATTERNS = (
    re.compile(
        r"\bUnemployment rate (?:of|for) total population(?: in (?:the )?Kingdom)?\s+"
        r"(?:reaches|reached|records|recorded|stabilizes at|stabilized at|"
        r"decreases to|decreased to|declines to|declined to|falls to|fell to)\s+"
        r"([0-9]+(?:\.[0-9]+)?)%\s+in\s+Q([1-4])(?:\s+of)?\s+(\d{4})",
        flags=re.IGNORECASE,
    ),
)
_QUARTER_PATTERNS = (
    re.compile(
        r"\bLabor Market Statistics(?: Publication)?\s+for\s+Q([1-4])(?:\s+of)?\s+(\d{4})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bLabor Market Statistics(?: Publication)?\s+for\s+the\s+"
        r"(first|second|third|fourth)\s+quarter\s+of\s+(\d{4})",
        flags=re.IGNORECASE,
    ),
)
_SUMMARY_RATE_PATTERNS = (
    re.compile(
        r"\boverall unemployment rate\s+\((?:including|for)\s+Saudis\s+and\s+"
        r"non-Saudis\)\s+(?:stood at|reached|recorded|was|stabilized at|"
        r"decreased to|declined to|fell to)\s+([0-9]+(?:\.[0-9]+)?)%",
        flags=re.IGNORECASE,
    ),
)
_TITLE_NORMALIZATION_PATTERN = re.compile(r"\s+")
_RELEASE_DATE_FORMAT = "%d-%m-%Y"
_QUARTER_WORDS = {
    "first": "Q1",
    "second": "Q2",
    "third": "Q3",
    "fourth": "Q4",
}


def extract_stats_gov_sa_unemployment_rate_total_quarterly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract narrow quarterly unemployment observations from supported release cards."""

    parser = StatsGovSaReleaseCardParser()
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
    card: StatsGovSaReleaseCard,
    source_locator: str,
    source_url: str,
) -> dict[str, Any] | None:
    title = _normalize_text(card.title)
    summary_text = _normalize_text(card.summary_text)
    release_date_text = _normalize_text(card.release_date_text)
    release_url = card.release_url

    if not title or not summary_text or not release_date_text or not release_url:
        return None
    if not _looks_like_total_unemployment_release(title, summary_text):
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
        "labor_series_code": "unemployment_rate_total_population_15_plus",
        "labor_series_name": "Unemployment Rate of Total Population (15+)",
        "release_date": release_date.isoformat(),
        "value_percent": value_percent,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_release_url": release_url,
        "source_release_title": title,
        "source_release_date_text": release_date_text,
        "source_summary_text": summary_text,
    }


def _looks_like_total_unemployment_release(title: str, summary_text: str) -> bool:
    normalized_title = title.lower()
    normalized_summary = summary_text.lower()
    return (
        (
            "unemployment rate of total population" in normalized_title
            or "unemployment rate for total population" in normalized_title
            or "labor market statistics" in normalized_title
        )
        and "labor market statistics" in normalized_summary
        and "overall unemployment rate" in normalized_summary
        and "saudis and non-saudis" in normalized_summary
    )


def _extract_observation_quarter_and_value_percent(
    *,
    title: str,
    summary_text: str,
) -> tuple[str, float]:
    for pattern in _TITLE_VALUE_PATTERNS:
        match = pattern.search(title)
        if match is None:
            continue
        return (_format_quarter(match.group(3), match.group(2)), float(match.group(1)))

    return (
        _extract_observation_quarter(title, summary_text),
        _extract_value_percent(summary_text),
    )


def _extract_observation_quarter(title: str, summary_text: str) -> str:
    for candidate_text in (title, summary_text):
        for pattern in _QUARTER_PATTERNS:
            match = pattern.search(candidate_text)
            if match is None:
                continue
            quarter = match.group(1).lower()
            if quarter in _QUARTER_WORDS:
                return _format_quarter(match.group(2), _QUARTER_WORDS[quarter][-1])
            return _format_quarter(match.group(2), quarter[-1])
    raise ValueError("supported labor-market release card did not expose a parseable quarter")


def _extract_value_percent(summary_text: str) -> float:
    for pattern in _SUMMARY_RATE_PATTERNS:
        match = pattern.search(summary_text)
        if match is not None:
            return float(match.group(1))
    raise ValueError(
        "supported labor-market release card did not expose a parseable unemployment rate"
    )


def _parse_release_date(text: str) -> date:
    return datetime.strptime(text, _RELEASE_DATE_FORMAT).date()


def _normalize_text(value: str) -> str:
    normalized = value.replace("’", "'")
    return _TITLE_NORMALIZATION_PATTERN.sub(" ", normalized).strip()


def _format_quarter(year: str, quarter: str) -> str:
    return f"{year}-Q{quarter}"
