"""Unit tests for the read-only data-facing policies resource."""

from __future__ import annotations

from saudi_open_data_mcp.normalization.contracts import (
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS,
)
from saudi_open_data_mcp.resources.policies import (
    DataSurfacePolicySummary,
    PoliciesResource,
)


def test_policies_resource_makes_wave_three_surface_decision_explicit() -> None:
    resource = PoliciesResource()

    summary = resource.read()

    assert isinstance(summary, DataSurfacePolicySummary)
    assert summary.decision == "keep_current_surface"
    assert "local-only query surface" in summary.summary
    assert summary.query_primary_dataset_ids == SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS
    assert tuple(policy.tool_name for policy in summary.tool_policies) == (
        "query_dataset",
        "preview_dataset",
        "download_dataset",
        "materialize_hot_set",
    )
    assert "repeatable analysis" in summary.notes[0]
