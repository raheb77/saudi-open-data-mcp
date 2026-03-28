"""Freshness helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


class FreshnessPolicy(BaseModel):
    """Freshness policy for cached or snapshotted data."""

    max_age_hours: int = 24


def is_fresh(
    updated_at: datetime,
    policy: FreshnessPolicy,
    reference: datetime | None = None,
) -> bool:
    """Check whether data is fresh for the given policy."""

    if reference is None:
        reference = datetime.now(tz=UTC)
    return reference - updated_at <= timedelta(hours=policy.max_age_hours)
