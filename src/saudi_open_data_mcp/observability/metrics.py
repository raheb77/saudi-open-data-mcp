"""Local in-process metrics helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class InMemoryMetrics:
    """Simple process-local counter collector."""

    _counts: Counter[str] = field(default_factory=Counter)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a named counter."""

        if not name:
            raise ValueError("metric name must not be empty")
        if value < 0:
            raise ValueError("metric increments must be greater than or equal to zero")

        with self._lock:
            self._counts[name] += value

    def get(self, name: str) -> int:
        """Return the current value for a named counter."""

        with self._lock:
            return self._counts.get(name, 0)

    def snapshot(self) -> dict[str, int]:
        """Return a deterministic copy of all counters."""

        with self._lock:
            return dict(sorted(self._counts.items()))

    def reset(self) -> None:
        """Reset all counters for the current process."""

        with self._lock:
            self._counts.clear()


_METRICS = InMemoryMetrics()

# Backward-compatible alias for the earlier placeholder export.
NoOpMetrics = InMemoryMetrics


def get_metrics() -> InMemoryMetrics:
    """Return the shared in-process metrics collector."""

    return _METRICS


def reset_metrics() -> None:
    """Reset the shared in-process metrics collector."""

    _METRICS.reset()
