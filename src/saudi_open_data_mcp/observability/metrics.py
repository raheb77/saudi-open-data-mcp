"""Metrics placeholders."""

from dataclasses import dataclass


@dataclass
class NoOpMetrics:
    """No-op metrics collector."""

    def increment(self, name: str, value: int = 1) -> None:
        """Ignore metrics until observability is implemented."""

        _ = (name, value)
