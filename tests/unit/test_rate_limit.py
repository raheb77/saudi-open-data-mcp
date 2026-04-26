"""Unit tests for process-local rate limiting."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from saudi_open_data_mcp.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceededError,
    RateLimitPolicy,
)


def test_in_memory_rate_limiter_enforces_sliding_window() -> None:
    current_time = 100.0

    def clock() -> float:
        return current_time

    limiter = InMemoryRateLimiter(
        RateLimitPolicy(requests=2, window_seconds=10),
        clock=clock,
    )

    limiter.enforce()
    limiter.enforce()

    with pytest.raises(RateLimitExceededError):
        limiter.enforce()

    current_time = 110.0
    limiter.enforce()


def test_in_memory_rate_limiter_state_is_instance_local() -> None:
    policy = RateLimitPolicy(requests=1, window_seconds=60)
    first_limiter = InMemoryRateLimiter(policy, clock=lambda: 100.0)
    second_limiter = InMemoryRateLimiter(policy, clock=lambda: 100.0)

    first_limiter.enforce()

    with pytest.raises(RateLimitExceededError):
        first_limiter.enforce()

    second_limiter.enforce()


def test_rate_limit_policy_rejects_unexpected_state_and_mutation() -> None:
    policy = RateLimitPolicy(requests=1, window_seconds=60)

    with pytest.raises(ValidationError):
        RateLimitPolicy(requests=1, window_seconds=60, distributed=True)

    with pytest.raises(ValidationError):
        policy.requests = 2
