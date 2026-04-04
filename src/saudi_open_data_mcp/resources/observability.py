"""Read-only observability resource over the in-process counter snapshot."""

from __future__ import annotations

from saudi_open_data_mcp.observability.summary import (
    ObservabilitySummary,
    build_observability_summary,
)


class ObservabilityResource:
    """Thin read-only resource layer for grouped process-local observability counters."""

    def read(self) -> ObservabilitySummary:
        """Return a current grouped counter snapshot for internal operators."""

        return build_observability_summary()
