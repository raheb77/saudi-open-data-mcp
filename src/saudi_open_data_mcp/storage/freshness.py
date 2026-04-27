"""Deterministic local snapshot freshness evaluation.

Freshness is evaluated from local artifact evidence only.

- ``fresh`` means a local snapshot exists and falls within a deterministic window.
- ``stale`` means a local snapshot exists but exceeds that window.
- ``missing`` means no local snapshot exists.
- ``unknown`` means a local snapshot exists but the registry does not declare a
  deterministic freshness window for that dataset yet.

For the current runtime contract, ``UpdateFrequency.AD_HOC`` and
``UpdateFrequency.UNSPECIFIED`` are treated as ``unknown`` rather than
implicitly fresh or stale.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.registry.models import UpdateFrequency

from .snapshots import SnapshotStore


class SnapshotFreshnessStatus(StrEnum):
    """Typed local freshness state for a snapshot artifact."""

    MISSING = "missing"
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class SnapshotFreshnessReason(StrEnum):
    """Explicit reason for the current freshness state."""

    NO_SNAPSHOT = "no_snapshot"
    WITHIN_EXPECTED_WINDOW = "within_expected_window"
    EXCEEDED_EXPECTED_WINDOW = "exceeded_expected_window"
    NO_FREQUENCY_EVIDENCE = "no_frequency_evidence"


class SnapshotFreshnessResult(BaseModel):
    """Typed local snapshot freshness result."""

    model_config = ConfigDict(extra="forbid")

    source: str
    dataset_id: str
    status: SnapshotFreshnessStatus
    reason: SnapshotFreshnessReason
    artifact_present: bool
    snapshot_id: str | None = None
    reference_time: datetime
    snapshot_modified_at: datetime | None = None
    snapshot_age: timedelta | None = None
    update_frequency: UpdateFrequency | None = None

    @model_validator(mode="after")
    def _validate_snapshot_id_consistency(self) -> Self:
        if not self.artifact_present and self.snapshot_id is not None:
            raise ValueError("snapshot freshness without an artifact must not include snapshot_id")
        return self


UNKNOWN_FRESHNESS_UPDATE_FREQUENCIES: frozenset[UpdateFrequency] = frozenset(
    {
        UpdateFrequency.AD_HOC,
        UpdateFrequency.UNSPECIFIED,
    }
)
RIYADH_TIMEZONE = ZoneInfo("Asia/Riyadh")
RIYADH_WEEKEND_DAYS = frozenset({4, 5})


def has_defined_freshness_window(update_frequency: UpdateFrequency | None) -> bool:
    """Return whether a dataset can be classified as fresh or stale deterministically."""

    return (
        update_frequency is not None
        and update_frequency not in UNKNOWN_FRESHNESS_UPDATE_FREQUENCIES
    )


def evaluate_snapshot_freshness(
    *,
    source: str,
    dataset_id: str,
    snapshot_store: SnapshotStore | Path,
    reference_time: datetime | None = None,
    update_frequency: UpdateFrequency | None = None,
) -> SnapshotFreshnessResult:
    """Evaluate snapshot freshness from local filesystem evidence only."""

    store = (
        snapshot_store
        if isinstance(snapshot_store, SnapshotStore)
        else SnapshotStore(snapshot_store)
    )
    snapshot_path = store.snapshot_path(source, dataset_id)
    evaluated_at = _normalize_reference_time(reference_time)

    if not snapshot_path.is_file():
        return SnapshotFreshnessResult(
            source=source,
            dataset_id=dataset_id,
            status=SnapshotFreshnessStatus.MISSING,
            reason=SnapshotFreshnessReason.NO_SNAPSHOT,
            artifact_present=False,
            reference_time=evaluated_at,
            update_frequency=update_frequency,
        )

    snapshot_id = store.snapshot_id(source, dataset_id)
    modified_at = datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=UTC)
    snapshot_age = max(evaluated_at - modified_at, timedelta(0))

    if not has_defined_freshness_window(update_frequency):
        return SnapshotFreshnessResult(
            source=source,
            dataset_id=dataset_id,
            status=SnapshotFreshnessStatus.UNKNOWN,
            reason=SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE,
            artifact_present=True,
            snapshot_id=snapshot_id,
            reference_time=evaluated_at,
            snapshot_modified_at=modified_at,
            snapshot_age=snapshot_age,
            update_frequency=update_frequency,
        )

    assert update_frequency is not None
    if _snapshot_is_within_freshness_window(
        modified_at=modified_at,
        reference_time=evaluated_at,
        update_frequency=update_frequency,
    ):
        status = SnapshotFreshnessStatus.FRESH
        reason = SnapshotFreshnessReason.WITHIN_EXPECTED_WINDOW
    else:
        status = SnapshotFreshnessStatus.STALE
        reason = SnapshotFreshnessReason.EXCEEDED_EXPECTED_WINDOW

    return SnapshotFreshnessResult(
        source=source,
        dataset_id=dataset_id,
        status=status,
        reason=reason,
        artifact_present=True,
        snapshot_id=snapshot_id,
        reference_time=evaluated_at,
        snapshot_modified_at=modified_at,
        snapshot_age=snapshot_age,
        update_frequency=update_frequency,
    )


def _normalize_reference_time(reference_time: datetime | None) -> datetime:
    """Normalize the evaluation reference time to an aware UTC datetime."""

    if reference_time is None:
        return datetime.now(tz=UTC)
    if reference_time.tzinfo is None:
        raise ValueError("reference_time must be timezone-aware")
    return reference_time.astimezone(UTC)


def _freshness_window(update_frequency: UpdateFrequency) -> timedelta:
    """Map a declared update frequency to a deterministic freshness window."""

    if update_frequency is UpdateFrequency.DAILY:
        return timedelta(days=1)
    if update_frequency is UpdateFrequency.WEEKLY:
        return timedelta(days=7)
    if update_frequency is UpdateFrequency.MONTHLY:
        return timedelta(days=31)
    if update_frequency is UpdateFrequency.QUARTERLY:
        return timedelta(days=92)
    if update_frequency is UpdateFrequency.ANNUAL:
        return timedelta(days=366)
    raise ValueError(
        f"freshness window is not defined for update frequency '{update_frequency.value}'"
    )


def _snapshot_is_within_freshness_window(
    *,
    modified_at: datetime,
    reference_time: datetime,
    update_frequency: UpdateFrequency,
) -> bool:
    if update_frequency is UpdateFrequency.DAILY:
        return _riyadh_business_days_elapsed(modified_at, reference_time) <= 1
    return max(reference_time - modified_at, timedelta(0)) <= _freshness_window(
        update_frequency
    )


def _riyadh_business_days_elapsed(start: datetime, end: datetime) -> int:
    start_date = start.astimezone(RIYADH_TIMEZONE).date()
    end_date = end.astimezone(RIYADH_TIMEZONE).date()
    if end_date <= start_date:
        return 0

    elapsed = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if _is_riyadh_business_day(current):
            elapsed += 1
        current += timedelta(days=1)
    return elapsed


def _is_riyadh_business_day(value: date) -> bool:
    return value.weekday() not in RIYADH_WEEKEND_DAYS
