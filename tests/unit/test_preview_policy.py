"""Unit tests for explicit preview resolution policy semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from saudi_open_data_mcp.registry.models import UpdateFrequency
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessResult,
    SnapshotFreshnessStatus,
)
from saudi_open_data_mcp.tools.preview import (
    PreviewResolutionOutcome,
    PreviewResolutionPolicy,
)

REFERENCE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
SNAPSHOT_TIME = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


def _freshness(
    *,
    status: SnapshotFreshnessStatus,
    reason: SnapshotFreshnessReason,
    artifact_present: bool,
    update_frequency: UpdateFrequency | None,
) -> SnapshotFreshnessResult:
    return SnapshotFreshnessResult(
        source="sama",
        dataset_id="sama-money-supply",
        status=status,
        reason=reason,
        artifact_present=artifact_present,
        reference_time=REFERENCE_TIME,
        snapshot_modified_at=SNAPSHOT_TIME if artifact_present else None,
        snapshot_age=(
            REFERENCE_TIME - SNAPSHOT_TIME if artifact_present else None
        ),
        update_frequency=update_frequency,
    )


@pytest.mark.parametrize(
    ("update_frequency", "expected_outcome"),
    [
        (UpdateFrequency.UNSPECIFIED, PreviewResolutionOutcome.SERVE_LOCAL),
        (UpdateFrequency.AD_HOC, PreviewResolutionOutcome.SERVE_LOCAL),
    ],
)
def test_unknown_frequency_without_defined_window_uses_explicit_local_policy(
    update_frequency: UpdateFrequency,
    expected_outcome: PreviewResolutionOutcome,
) -> None:
    policy = PreviewResolutionPolicy()

    outcome = policy.initial_outcome(
        update_frequency=update_frequency,
        freshness=_freshness(
            status=SnapshotFreshnessStatus.UNKNOWN,
            reason=SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE,
            artifact_present=True,
            update_frequency=update_frequency,
        ),
    )

    assert outcome is expected_outcome


def test_refresh_failure_only_allows_stale_fallback_for_actual_stale_artifact() -> None:
    policy = PreviewResolutionPolicy()

    stale_outcome = policy.refresh_failure_outcome(
        freshness=_freshness(
            status=SnapshotFreshnessStatus.STALE,
            reason=SnapshotFreshnessReason.EXCEEDED_EXPECTED_WINDOW,
            artifact_present=True,
            update_frequency=UpdateFrequency.WEEKLY,
        ),
    )
    missing_outcome = policy.refresh_failure_outcome(
        freshness=_freshness(
            status=SnapshotFreshnessStatus.MISSING,
            reason=SnapshotFreshnessReason.NO_SNAPSHOT,
            artifact_present=False,
            update_frequency=UpdateFrequency.WEEKLY,
        ),
    )

    assert stale_outcome is PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE
    assert missing_outcome is PreviewResolutionOutcome.FAIL_CLOSED


@pytest.mark.parametrize(
    "initial_outcome",
    [
        PreviewResolutionOutcome.SERVE_LOCAL,
        PreviewResolutionOutcome.SERVE_STALE_WITH_NOTICE,
    ],
)
def test_local_artifact_miss_transitions_to_explicit_refresh_path(
    initial_outcome: PreviewResolutionOutcome,
) -> None:
    outcome = PreviewResolutionPolicy.local_artifact_unusable_outcome(
        initial_outcome=initial_outcome,
    )

    assert outcome is PreviewResolutionOutcome.REFRESH_THEN_SERVE
