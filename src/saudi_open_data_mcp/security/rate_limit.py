"""Deterministic in-process rate limiting helpers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field


class RateLimitPolicy(BaseModel):
    """Bounded in-process rate limit policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requests: int = Field(default=60, ge=1)
    window_seconds: int = Field(default=60, ge=1)


class RateLimitExceededError(Exception):
    """Raised when a request exceeds the configured rate limit."""


class InMemoryRateLimiter:
    """Process-local sliding-window rate limiter.

    This limiter intentionally does not coordinate across worker processes,
    containers, or hosts.
    """

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._policy = policy
        self._clock = clock or monotonic
        self._request_times: deque[float] = deque()
        self._lock = Lock()

    def enforce(self) -> None:
        """Raise when the configured rate limit has been exceeded."""

        with self._lock:
            now = self._clock()
            window_start = now - self._policy.window_seconds

            while self._request_times and self._request_times[0] <= window_start:
                self._request_times.popleft()

            if len(self._request_times) >= self._policy.requests:
                raise RateLimitExceededError(
                    "preview_dataset rate limit exceeded: "
                    f"{self._policy.requests} requests per "
                    f"{self._policy.window_seconds} seconds"
                )

            self._request_times.append(now)
