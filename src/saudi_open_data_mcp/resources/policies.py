"""Read-only data-facing policy summary for internal MCP operators and clients."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from saudi_open_data_mcp.normalization.contracts import (
    QUERY_PRIMARY_CANONICAL_DATASET_IDS,
)


class ToolPolicySummary(BaseModel):
    """Concise operator-facing semantics for one exposed data-related MCP tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    role: str
    network_behavior: str
    semantics: str


class DataSurfacePolicySummary(BaseModel):
    """Read-only summary of the current data-facing MCP surface decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: str
    summary: str
    query_primary_dataset_ids: tuple[str, ...] = Field(default_factory=tuple)
    tool_policies: tuple[ToolPolicySummary, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)


class PoliciesResource:
    """Thin read-only resource layer for current data-facing policy decisions."""

    def read(self) -> DataSurfacePolicySummary:
        """Return the current narrow decision on query vs preview semantics."""

        return DataSurfacePolicySummary(
            decision="keep_current_surface",
            summary=(
                "Wave 3A enrichment makes the current local-only query surface "
                "materially useful for the enriched SAMA high-frequency core, so "
                "stable tool semantics remain unchanged."
            ),
            query_primary_dataset_ids=QUERY_PRIMARY_CANONICAL_DATASET_IDS,
            tool_policies=(
                ToolPolicySummary(
                    tool_name="query_dataset",
                    role="primary_local_analysis",
                    network_behavior="local_only",
                    semantics=(
                        "Deterministic exact-match querying over canonical records "
                        "derived from local snapshots."
                    ),
                ),
                ToolPolicySummary(
                    tool_name="preview_dataset",
                    role="freshness_aware_inspection",
                    network_behavior="hybrid_local_live",
                    semantics=(
                        "Hybrid preview that may serve local data, refresh live, "
                        "or degrade explicitly based on freshness policy."
                    ),
                ),
                ToolPolicySummary(
                    tool_name="download_dataset",
                    role="artifact_availability",
                    network_behavior="local_only",
                    semantics=(
                        "Reports local raw snapshot availability only and never "
                        "triggers remote fetch."
                    ),
                ),
                ToolPolicySummary(
                    tool_name="materialize_hot_set",
                    role="explicit_local_materialization",
                    network_behavior="live_fetch",
                    semantics=(
                        "Operator-triggered fetch and persistence path for the "
                        "supported SAMA hot set."
                    ),
                ),
            ),
            notes=(
                "query_dataset remains the primary interface for repeatable analysis "
                "over local canonical records.",
                "preview_dataset remains the right surface for freshness-aware "
                "inspection rather than stable analytical reads.",
                "No new data-serving tool is introduced in this phase because the "
                "enriched Wave 3A datasets are now materially queryable through the "
                "existing local-only query path.",
            ),
        )
