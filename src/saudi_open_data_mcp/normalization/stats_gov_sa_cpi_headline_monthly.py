"""Dataset-specific HTML extraction for the canonical stats.gov.sa CPI headline contract."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .stats_gov_sa_release_cards import (
    StatsGovSaReleaseCard,
    StatsGovSaReleaseCardParser,
)

STATS_GOV_SA_CPI_HEADLINE_MONTHLY_HTML_LIMITATION = (
    "stats_gov_sa_cpi_headline_monthly_html_requires_supported_release_cards"
)

_TITLE_OBSERVATION_PATTERNS = (
    re.compile(
        r"\bSaudi Arabia[’']?s inflation(?: rate)?\s+"
        r"(?:records|reaches|hits|remains stable at)\s+"
        r"([0-9]+(?:\.[0-9]+)?)%\s+in\s+([A-Za-z]+\s+\d{4})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bInflation in Saudi Arabia\s+reaches\s+([0-9]+(?:\.[0-9]+)?)%\s+"
        r"in\s+([A-Za-z]+\s+\d{4})",
        flags=re.IGNORECASE,
    ),
)
_SUMMARY_OBSERVATION_PATTERNS = (
    re.compile(
        r"\bannual inflation rate(?: of the Consumer Price Index \(CPI\))?"
        r"(?: in (?:Saudi Arabia|the Kingdom of Saudi Arabia))?\s+"
        r"(?:reached|recorded|remained stable at)\s+([0-9]+(?:\.[0-9]+)?)%\s+"
        r"in\s+([A-Za-z]+\s+\d{4})",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bConsumer Price Index \(CPI\)\s+for\s+([A-Za-z]+\s+\d{4}),?\s+"
        r"recording an increase of\s+([0-9]+(?:\.[0-9]+)?)%",
        flags=re.IGNORECASE,
    ),
)
_MONTHLY_RATE_PATTERNS = (
    (
        re.compile(
            r"\bmonthly increase of\s+([0-9]+(?:\.[0-9]+)?)%\s+compared\s+to\s+"
            r"[A-Za-z]+\s+\d{4}",
            flags=re.IGNORECASE,
        ),
        1.0,
    ),
    (
        re.compile(
            r"\bmonthly (?:decrease|decline) of\s+([0-9]+(?:\.[0-9]+)?)%\s+"
            r"compared\s+to\s+[A-Za-z]+\s+\d{4}",
            flags=re.IGNORECASE,
        ),
        -1.0,
    ),
    (
        re.compile(
            r"\bmonthly basis at\s+([0-9]+(?:\.[0-9]+)?)%\s+compared\s+with\s+"
            r"[A-Za-z]+\s+\d{4}",
            flags=re.IGNORECASE,
        ),
        1.0,
    ),
    (
        re.compile(
            r"\bmonthly inflation rate recorded\s+([0-9]+(?:\.[0-9]+)?)%\s+"
            r"compared\s+to\s+[A-Za-z]+\s+\d{4}",
            flags=re.IGNORECASE,
        ),
        1.0,
    ),
)
_TITLE_NORMALIZATION_PATTERN = re.compile(r"\s+")
_RELEASE_DATE_FORMAT = "%d-%m-%Y"
_OBSERVATION_MONTH_FORMATS = ("%B %Y", "%b %Y")


def extract_stats_gov_sa_cpi_headline_monthly_rows_from_html(
    *,
    html: str,
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract headline CPI monthly observations from supported stats.gov.sa release cards."""

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
    if not _looks_like_headline_cpi_release(title, summary_text):
        return None

    try:
        observation_month, yoy_rate_percent = _extract_observation_month_and_yoy_rate(
            title=title,
            summary_text=summary_text,
        )
    except ValueError:
        return None
    try:
        mom_rate_percent = _extract_monthly_rate_percent(summary_text)
    except ValueError:
        return None
    release_date = _parse_release_date(release_date_text)

    return {
        "observation_month": observation_month,
        "inflation_series_code": "headline_cpi_all_items",
        "inflation_series_name": "Headline CPI",
        "release_date": release_date.isoformat(),
        "yoy_rate_percent": yoy_rate_percent,
        "mom_rate_percent": mom_rate_percent,
        "source_locator": source_locator,
        "source_url": source_url,
        "source_release_url": release_url,
        "source_release_title": title,
        "source_release_date_text": release_date_text,
        "source_summary_text": summary_text,
    }


def _looks_like_headline_cpi_release(title: str, summary_text: str) -> bool:
    normalized_title = title.lower()
    normalized_summary = summary_text.lower()
    return (
        "inflation" in normalized_title
        and "consumer price index" in normalized_summary
        and "annual inflation rate" in normalized_summary
    )


def _extract_observation_month_and_yoy_rate(
    *,
    title: str,
    summary_text: str,
) -> tuple[str, float]:
    for pattern in _TITLE_OBSERVATION_PATTERNS:
        match = pattern.search(title)
        if match is None:
            continue
        return (
            _parse_observation_month(match.group(2)).strftime("%Y-%m"),
            float(match.group(1)),
        )

    for pattern in _SUMMARY_OBSERVATION_PATTERNS:
        match = pattern.search(summary_text)
        if match is None:
            continue
        if "Consumer Price Index (CPI) for" in match.group(0):
            return (
                _parse_observation_month(match.group(1)).strftime("%Y-%m"),
                float(match.group(2)),
            )
        return (
            _parse_observation_month(match.group(2)).strftime("%Y-%m"),
            float(match.group(1)),
        )

    raise ValueError("supported inflation release card must include observation month and yoy")


def _extract_monthly_rate_percent(summary_text: str) -> float:
    for pattern, multiplier in _MONTHLY_RATE_PATTERNS:
        match = pattern.search(summary_text)
        if match is not None:
            return float(match.group(1)) * multiplier

    raise ValueError("supported inflation release card must include monthly inflation rate")


def _parse_release_date(text: str) -> date:
    return datetime.strptime(text, _RELEASE_DATE_FORMAT).date()


def _parse_observation_month(text: str) -> datetime:
    normalized = _normalize_text(text)
    for date_format in _OBSERVATION_MONTH_FORMATS:
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    raise ValueError(f"unsupported observation month text: {text}")


def _normalize_text(text: str) -> str:
    normalized = text.replace("\xa0", " ").replace("’", "'").strip()
    return _TITLE_NORMALIZATION_PATTERN.sub(" ", normalized)

