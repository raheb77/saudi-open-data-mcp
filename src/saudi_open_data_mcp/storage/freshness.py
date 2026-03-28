"""Deterministic local snapshot freshness evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from saudi_open_data_mcp.registry.models import UpdateFrequency

from .snapshots import SnapshotStore


class SnapshotFreshnessStatus(StrEnum):
    """Typed local freshness state for a snapshot."""

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
    snapshot_path: Path
    reference_time: datetime
    snapshot_modified_at: datetime | None = None
    snapshot_age: timedelta | None = None
    update_frequency: UpdateFrequency | None = None


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
            snapshot_path=snapshot_path,
            reference_time=evaluated_at,
            update_frequency=update_frequency,
        )

    modified_at = datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=UTC)
    snapshot_age = max(evaluated_at - modified_at, timedelta(0))

    if update_frequency is None or update_frequency in {
        UpdateFrequency.AD_HOC,
        UpdateFrequency.UNSPECIFIED,
    }:
        return SnapshotFreshnessResult(
            source=source,
            dataset_id=dataset_id,
            status=SnapshotFreshnessStatus.UNKNOWN,
            reason=SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE,
            snapshot_path=snapshot_path,
            reference_time=evaluated_at,
            snapshot_modified_at=modified_at,
            snapshot_age=snapshot_age,
            update_frequency=update_frequency,
        )

    freshness_window = _freshness_window(update_frequency)
    if snapshot_age <= freshness_window:
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
        snapshot_path=snapshot_path,
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
