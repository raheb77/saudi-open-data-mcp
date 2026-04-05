"""Dataset-specific HTML extraction for a narrow stats.gov.sa GDP contract."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .stats_gov_sa_release_cards import (
    StatsGovSaReleaseCard,
    StatsGovSaReleaseCardParser,
)

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


def extract_stats_gov_sa_real_gdp_growth_quarterly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract narrow quarterly headline GDP observations from supported release cards."""

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


def _format_quarter(year: str, quarter: str) -> str:
    return f"{year}-Q{quarter}"
