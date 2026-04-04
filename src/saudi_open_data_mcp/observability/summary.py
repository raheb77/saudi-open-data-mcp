"""Readable grouped summaries over the existing process-local counters."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .metrics import InMemoryMetrics, get_metrics


class ObservabilityCounter(BaseModel):
    """Single named counter value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: int = Field(ge=0)


class ObservabilityCounterGroup(BaseModel):
    """Human-readable group of related counters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    summary: str
    counters: tuple[ObservabilityCounter, ...] = Field(default_factory=tuple)
    detail_counters: tuple[ObservabilityCounter, ...] = Field(default_factory=tuple)


class ObservabilitySummary(BaseModel):
    """Process-local grouped counter snapshot for internal operator use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    process_local: bool = True
    groups: tuple[ObservabilityCounterGroup, ...] = Field(default_factory=tuple)
    raw_counters: dict[str, int] = Field(default_factory=dict)
    notes: tuple[str, ...] = Field(default_factory=tuple)


@dataclass(frozen=True)
class _CounterGroupSpec:
    name: str
    summary: str
    counter_names: tuple[str, ...]
    detail_prefixes: tuple[str, ...] = ()


_COUNTER_GROUP_SPECS = (
    _CounterGroupSpec(
        name="startup",
        summary=(
            "Process-local server construction counters. Attempts, ready, and failures "
            "count startup lifecycle outcomes, not request traffic."
        ),
        counter_names=(
            "server.startup.attempts",
            "server.startup.ready",
            "server.startup.failures",
        ),
    ),
    _CounterGroupSpec(
        name="preview",
        summary=(
            "Preview request counters. preview.requests counts tool calls; outcome "
            "counters reflect the final returned preview path or failure."
        ),
        counter_names=(
            "preview.requests",
            "preview.local_snapshot",
            "preview.live_refresh",
            "preview.stale_fallback",
            "preview.failures",
            "preview.rate_limited",
        ),
    ),
    _CounterGroupSpec(
        name="auth",
        summary=(
            "HTTP auth counters for the run-http serving path only. Accepted and "
            "rejected counts are outcomes within http.auth.requests."
        ),
        counter_names=(
            "http.auth.requests",
            "http.auth.accepted",
            "http.auth.rejected",
            "http.auth.rejected.missing",
            "http.auth.rejected.invalid",
        ),
    ),
    _CounterGroupSpec(
        name="connectors",
        summary=(
            "Top-level connector retry/failure totals. Per-source connector.request_* "
            "detail counters remain available below for source-specific inspection."
        ),
        counter_names=(
            "connector.retries",
            "connector.failures",
        ),
        detail_prefixes=("connector.request_",),
    ),
    _CounterGroupSpec(
        name="materialization",
        summary=(
            "Hot-set materialization counters. materialize.requests counts top-level "
            "runs; successes and failures count per-dataset outcomes, including Tier A "
            "background refresh runs."
        ),
        counter_names=(
            "materialize.requests",
            "materialize.successes",
            "materialize.failures",
        ),
    ),
)


def build_observability_summary(
    metrics: InMemoryMetrics | None = None,
) -> ObservabilitySummary:
    """Return a grouped, operator-readable snapshot of the current counters."""

    snapshot = (metrics or get_metrics()).snapshot()
    return ObservabilitySummary(
        groups=tuple(_build_counter_group(snapshot, spec) for spec in _COUNTER_GROUP_SPECS),
        raw_counters=snapshot,
        notes=(
            "Counters are process-local and reset on process restart.",
            (
                "Request counters and outcome counters are not interchangeable; "
                "see each group summary."
            ),
            (
                "Tier A background refresh emits tier_a_refresh.* structured log "
                "events and reuses materialize.* counters."
            ),
        ),
    )


def _build_counter_group(
    snapshot: dict[str, int],
    spec: _CounterGroupSpec,
) -> ObservabilityCounterGroup:
    counters = tuple(
        ObservabilityCounter(name=name, value=snapshot.get(name, 0))
        for name in spec.counter_names
    )
    detail_names = sorted(
        name
        for name in snapshot
        if name not in spec.counter_names
        and any(name.startswith(prefix) for prefix in spec.detail_prefixes)
    )
    return ObservabilityCounterGroup(
        name=spec.name,
        summary=spec.summary,
        counters=counters,
        detail_counters=tuple(
            ObservabilityCounter(name=name, value=snapshot[name]) for name in detail_names
        ),
    )
