"""Observation-recency assessment over normalized canonical records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from saudi_open_data_mcp.normalization.pipeline import CanonicalRecord
from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.tools.result_metadata import (
    ObservationRecencyAssessment,
    ObservationRecencyStatus,
)

_MONTH_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")
_QUARTER_PATTERN = re.compile(r"^(?P<year>\d{4})-Q(?P<quarter>[1-4])$")
_YEAR_PATTERN = re.compile(r"^(?P<year>\d{4})$")
_DATE_FIELD_PRIORITY = (
    "as_of_date",
    "week_end_date",
    "effective_date",
    "observation_date",
)
_PERIOD_FIELD_PRIORITY = (
    "observation_month",
    "observation_quarter",
    "observation_year",
)


@dataclass(frozen=True)
class _ObservationCandidate:
    latest_observation: str
    latest_observation_field: str
    kind: str
    sort_key: int


def assess_observation_recency(
    *,
    records: tuple[CanonicalRecord, ...],
    update_frequency: UpdateFrequency,
    reference_date: date | None = None,
) -> ObservationRecencyAssessment | None:
    """Assess whether the latest normalized observation is materially behind cadence."""

    if not records:
        return None

    candidate = _latest_observation_candidate(records)
    if candidate is None:
        return None

    if update_frequency in {UpdateFrequency.AD_HOC, UpdateFrequency.UNSPECIFIED}:
        return ObservationRecencyAssessment(
            latest_observation=candidate.latest_observation,
            latest_observation_field=candidate.latest_observation_field,
            status=ObservationRecencyStatus.NOT_APPLICABLE,
        )

    resolved_reference_date = reference_date or datetime.now(UTC).date()
    if _is_materially_stale(
        candidate=candidate,
        update_frequency=update_frequency,
        reference_date=resolved_reference_date,
    ):
        return ObservationRecencyAssessment(
            latest_observation=candidate.latest_observation,
            latest_observation_field=candidate.latest_observation_field,
            status=ObservationRecencyStatus.STALE,
            warning=(
                "latest observation "
                f"{candidate.latest_observation} is materially behind the expected "
                f"{update_frequency.value} recency window"
            ),
        )

    if _supports_frequency_assessment(candidate=candidate, update_frequency=update_frequency):
        return ObservationRecencyAssessment(
            latest_observation=candidate.latest_observation,
            latest_observation_field=candidate.latest_observation_field,
            status=ObservationRecencyStatus.CURRENT,
        )

    return None


def _latest_observation_candidate(
    records: tuple[CanonicalRecord, ...],
) -> _ObservationCandidate | None:
    for field_name in _DATE_FIELD_PRIORITY:
        candidate = _latest_candidate_for_field(records=records, field_name=field_name)
        if candidate is not None:
            return candidate
    for field_name in _PERIOD_FIELD_PRIORITY:
        candidate = _latest_candidate_for_field(records=records, field_name=field_name)
        if candidate is not None:
            return candidate
    return None


def _latest_candidate_for_field(
    *,
    records: tuple[CanonicalRecord, ...],
    field_name: str,
) -> _ObservationCandidate | None:
    candidates = [
        candidate
        for record in records
        if (candidate := _parse_candidate(field_name, record.fields.get(field_name))) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.sort_key)


def _parse_candidate(field_name: str, value: object) -> _ObservationCandidate | None:
    if not isinstance(value, str):
        return None

    if field_name in _DATE_FIELD_PRIORITY:
        return _parse_date_candidate(field_name, value)
    if field_name == "observation_month":
        return _parse_month_candidate(field_name, value)
    if field_name == "observation_quarter":
        return _parse_quarter_candidate(field_name, value)
    if field_name == "observation_year":
        return _parse_year_candidate(field_name, value)
    return None


def _parse_date_candidate(
    field_name: str,
    value: str,
) -> _ObservationCandidate | None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return _ObservationCandidate(
        latest_observation=value,
        latest_observation_field=field_name,
        kind="date",
        sort_key=parsed.toordinal(),
    )


def _parse_month_candidate(
    field_name: str,
    value: str,
) -> _ObservationCandidate | None:
    match = _MONTH_PATTERN.fullmatch(value)
    if match is None:
        return None

    year = int(match.group("year"))
    month = int(match.group("month"))
    if month < 1 or month > 12:
        return None

    return _ObservationCandidate(
        latest_observation=value,
        latest_observation_field=field_name,
        kind="month",
        sort_key=(year * 12) + month,
    )


def _parse_quarter_candidate(
    field_name: str,
    value: str,
) -> _ObservationCandidate | None:
    match = _QUARTER_PATTERN.fullmatch(value)
    if match is None:
        return None

    year = int(match.group("year"))
    quarter = int(match.group("quarter"))
    return _ObservationCandidate(
        latest_observation=value,
        latest_observation_field=field_name,
        kind="quarter",
        sort_key=(year * 4) + quarter,
    )


def _parse_year_candidate(
    field_name: str,
    value: str,
) -> _ObservationCandidate | None:
    match = _YEAR_PATTERN.fullmatch(value)
    if match is None:
        return None

    return _ObservationCandidate(
        latest_observation=value,
        latest_observation_field=field_name,
        kind="year",
        sort_key=int(match.group("year")),
    )


def _supports_frequency_assessment(
    *,
    candidate: _ObservationCandidate,
    update_frequency: UpdateFrequency,
) -> bool:
    return (candidate.kind, update_frequency) in {
        ("date", UpdateFrequency.DAILY),
        ("date", UpdateFrequency.WEEKLY),
        ("month", UpdateFrequency.MONTHLY),
        ("quarter", UpdateFrequency.QUARTERLY),
        ("year", UpdateFrequency.ANNUAL),
    }


def _is_materially_stale(
    *,
    candidate: _ObservationCandidate,
    update_frequency: UpdateFrequency,
    reference_date: date,
) -> bool:
    if not _supports_frequency_assessment(
        candidate=candidate,
        update_frequency=update_frequency,
    ):
        return False

    if update_frequency is UpdateFrequency.DAILY:
        return candidate.sort_key < reference_date.toordinal() - 7

    if update_frequency is UpdateFrequency.WEEKLY:
        return candidate.sort_key < reference_date.toordinal() - 21

    if update_frequency is UpdateFrequency.MONTHLY:
        return candidate.sort_key < _month_sort_key(reference_date) - 2

    if update_frequency is UpdateFrequency.QUARTERLY:
        return candidate.sort_key < _quarter_sort_key(reference_date) - 2

    if update_frequency is UpdateFrequency.ANNUAL:
        return candidate.sort_key < reference_date.year - 1

    return False


def _month_sort_key(reference_date: date) -> int:
    return (reference_date.year * 12) + reference_date.month


def _quarter_sort_key(reference_date: date) -> int:
    return (reference_date.year * 4) + ((reference_date.month - 1) // 3 + 1)
