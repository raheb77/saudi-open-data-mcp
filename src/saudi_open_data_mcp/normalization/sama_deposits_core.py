"""Dataset-specific JSON extraction for the canonical SAMA deposits-core contract."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

SAMA_DEPOSITS_CORE_JSON_ROWS_LIMITATION = (
    "sama_deposits_core_json_requires_supported_monthly_deposit_component_rows"
)

_NUMBER_CLEANUP_PATTERN = re.compile(r"[^0-9.\-]+")
_TEXT_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")
_MONTH_FORMATS = (
    "%Y-%m",
    "%Y/%m",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%b %Y",
    "%B %Y",
    "%b-%Y",
    "%B-%Y",
)
_MONTH_KEYS = (
    "observation_month",
    "month",
    "period",
    "date",
    "reference_period",
    "month_end",
)
_CATEGORY_KEYS = (
    "deposit_category_code",
    "deposit_category_name",
    "deposit_category",
    "category",
    "series",
    "series_name",
    "name",
    "item",
)
_AMOUNT_KEYS = ("amount_sar", "amount", "value", "amount_value")


@dataclass(frozen=True, slots=True)
class _DepositCategory:
    code: str
    name: str
    related_monetary_aggregate_code: str
    related_monetary_aggregate_name: str


_DEPOSIT_CATEGORY_ALIASES = {
    "demand deposits": _DepositCategory(
        code="demand_deposits",
        name="Demand Deposits",
        related_monetary_aggregate_code="m1",
        related_monetary_aggregate_name="M1",
    ),
    "demand deposit": _DepositCategory(
        code="demand_deposits",
        name="Demand Deposits",
        related_monetary_aggregate_code="m1",
        related_monetary_aggregate_name="M1",
    ),
    "demand_deposits": _DepositCategory(
        code="demand_deposits",
        name="Demand Deposits",
        related_monetary_aggregate_code="m1",
        related_monetary_aggregate_name="M1",
    ),
    "time and savings deposits": _DepositCategory(
        code="time_and_savings_deposits",
        name="Time and Savings Deposits",
        related_monetary_aggregate_code="m2",
        related_monetary_aggregate_name="M2",
    ),
    "time savings deposits": _DepositCategory(
        code="time_and_savings_deposits",
        name="Time and Savings Deposits",
        related_monetary_aggregate_code="m2",
        related_monetary_aggregate_name="M2",
    ),
    "time savings deposit": _DepositCategory(
        code="time_and_savings_deposits",
        name="Time and Savings Deposits",
        related_monetary_aggregate_code="m2",
        related_monetary_aggregate_name="M2",
    ),
    "time and savings deposit": _DepositCategory(
        code="time_and_savings_deposits",
        name="Time and Savings Deposits",
        related_monetary_aggregate_code="m2",
        related_monetary_aggregate_name="M2",
    ),
    "time_and_savings_deposits": _DepositCategory(
        code="time_and_savings_deposits",
        name="Time and Savings Deposits",
        related_monetary_aggregate_code="m2",
        related_monetary_aggregate_name="M2",
    ),
    "other quasi money deposits": _DepositCategory(
        code="other_quasi_money_deposits",
        name="Other Quasi-Money Deposits",
        related_monetary_aggregate_code="m3",
        related_monetary_aggregate_name="M3",
    ),
    "other quasi-money deposits": _DepositCategory(
        code="other_quasi_money_deposits",
        name="Other Quasi-Money Deposits",
        related_monetary_aggregate_code="m3",
        related_monetary_aggregate_name="M3",
    ),
    "other quasi money deposit": _DepositCategory(
        code="other_quasi_money_deposits",
        name="Other Quasi-Money Deposits",
        related_monetary_aggregate_code="m3",
        related_monetary_aggregate_name="M3",
    ),
    "other quasi_money deposits": _DepositCategory(
        code="other_quasi_money_deposits",
        name="Other Quasi-Money Deposits",
        related_monetary_aggregate_code="m3",
        related_monetary_aggregate_name="M3",
    ),
    "other_quasi_money_deposits": _DepositCategory(
        code="other_quasi_money_deposits",
        name="Other Quasi-Money Deposits",
        related_monetary_aggregate_code="m3",
        related_monetary_aggregate_name="M3",
    ),
}


def extract_sama_deposits_core_rows_from_json(
    *,
    raw_json: dict[str, Any] | list[Any],
    source_locator: str,
    source_url: str,
) -> list[dict[str, Any]] | None:
    """Extract canonical bundled deposit-component rows from a supported JSON payload."""

    rows = _extract_rows(raw_json)
    if rows is None:
        return None

    extracted_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return None

        category = _resolve_category(row)
        if category is None:
            continue

        month_text = _first_present_text_value(row, _MONTH_KEYS)
        amount_value = _first_present_value(row, _AMOUNT_KEYS)
        if month_text is None or amount_value is None:
            return None

        try:
            observation_month = _parse_observation_month(month_text)
            amount_sar = _parse_decimal(amount_value)
        except ValueError:
            return None

        extracted_rows.append(
            {
                "observation_month": observation_month,
                "deposit_category_code": category.code,
                "deposit_category_name": category.name,
                "related_monetary_aggregate_code": category.related_monetary_aggregate_code,
                "related_monetary_aggregate_name": category.related_monetary_aggregate_name,
                "amount_sar": amount_sar,
                "source_locator": source_locator,
                "source_url": source_url,
                "source_series_name": _first_present_text_value(row, _CATEGORY_KEYS),
                "source_observation_month_text": month_text,
            }
        )

    return extracted_rows or None


def _extract_rows(raw_json: dict[str, Any] | list[Any]) -> list[Any] | None:
    if isinstance(raw_json, list):
        return raw_json
    if isinstance(raw_json, dict):
        rows = raw_json.get("rows")
        if isinstance(rows, list):
            return rows
    return None


def _resolve_category(row: dict[str, Any]) -> _DepositCategory | None:
    for key in _CATEGORY_KEYS:
        value = row.get(key)
        if not isinstance(value, str):
            continue
        normalized = _normalize_text(value)
        category = _DEPOSIT_CATEGORY_ALIASES.get(normalized)
        if category is not None:
            return category
    return None


def _first_present_text_value(
    row: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    value = _first_present_value(row, keys)
    if value is None:
        return None
    return str(value).strip() or None


def _first_present_value(
    row: dict[str, Any],
    keys: tuple[str, ...],
) -> Any | None:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _parse_observation_month(value: Any) -> str:
    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}"
    if not isinstance(value, str):
        raise ValueError("observation month must be a string or date-like value")

    text = value.strip()
    if not text:
        raise ValueError("observation month cannot be empty")

    for format_string in _MONTH_FORMATS:
        try:
            parsed = datetime.strptime(text, format_string)
        except ValueError:
            continue
        return f"{parsed.year:04d}-{parsed.month:02d}"

    raise ValueError(f"unsupported observation month format: {value}")


def _parse_decimal(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a supported numeric value")
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        raise ValueError("value must be numeric or numeric-like text")

    cleaned = _NUMBER_CLEANUP_PATTERN.sub("", value)
    if cleaned in {"", "-", ".", "-."}:
        raise ValueError(f"unsupported numeric value: {value}")
    return float(cleaned)


def _normalize_text(value: str) -> str:
    return _TEXT_NORMALIZATION_PATTERN.sub(" ", value.strip().casefold()).strip()
