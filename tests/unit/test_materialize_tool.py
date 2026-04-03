"""Unit tests for Wave 1 hot-set materialization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.resolver import SourceConnectorResolver
from saudi_open_data_mcp.normalization.pipeline import NormalizationPipelineStatus
from saudi_open_data_mcp.normalization.validators import TEXT_HTML_LIMITATION
from saudi_open_data_mcp.registry.bootstrap import (
    WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessReason,
    SnapshotFreshnessStatus,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.materialize import HotSetMaterializationTool, HotSetTier


class _SAMAConnectorSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        self.calls.append(dataset_id)
        if dataset_id == "report.aspx?cid=55":
            body: object = {"rows": [{"series": "deposits", "value": 1}]}
            content_type = "application/json"
        else:
            body = "<html><body>official sama page</body></html>"
            content_type = "text/html"

        return RawPayload(
            source="sama",
            dataset_id=dataset_id,
            content={
                "url": _source_url(dataset_id),
                "status_code": 200,
                "content_type": content_type,
                "body": body,
            },
        )


def _source_url(locator: str) -> str:
    if locator.startswith("/"):
        return f"https://www.sama.gov.sa{locator}"
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{locator}"


def _bootstrapped_repository(tmp_path: Path) -> RegistryRepository:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrap_registry(repository)
    return repository


@pytest.mark.asyncio
async def test_materialize_hot_set_persists_wave_one_tier_a_snapshots(tmp_path: Path) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    result = await tool.materialize_hot_set(
        reference_time=datetime.now(tz=UTC),
    )

    assert result.include_optional is False
    assert result.requested_dataset_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert result.materialized_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS)
    assert result.failed_count == 0
    assert [item.dataset_id for item in result.results] == list(
        WAVE_1_HOT_SET_TIER_A_DATASET_IDS
    )
    assert connector.calls == [
        "/en-US/Indices/Pages/POS.aspx",
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "report.aspx?cid=55",
    ]

    for dataset_id in WAVE_1_HOT_SET_TIER_A_DATASET_IDS:
        descriptor = repository.get_dataset(dataset_id)
        assert descriptor is not None
        assert snapshot_store.snapshot_exists(descriptor.source, descriptor.source_locator)

    results_by_id = {result.dataset_id: result for result in result.results}
    assert (
        results_by_id["sama-pos-weekly"].normalization_status
        is NormalizationPipelineStatus.LIMITED
    )
    assert results_by_id["sama-pos-weekly"].limitations == (TEXT_HTML_LIMITATION,)
    assert (
        results_by_id["sama-deposits-core"].normalization_status
        is NormalizationPipelineStatus.RECORD_DERIVABLE
    )
    assert results_by_id["sama-deposits-core"].limitations == ()
    assert results_by_id["sama-deposits-core"].freshness is not None
    assert (
        results_by_id["sama-deposits-core"].freshness.status
        is SnapshotFreshnessStatus.FRESH
    )
    assert results_by_id["sama-repo-rate"].freshness is not None
    assert results_by_id["sama-repo-rate"].freshness.status is SnapshotFreshnessStatus.UNKNOWN
    assert (
        results_by_id["sama-repo-rate"].freshness.reason
        is SnapshotFreshnessReason.NO_FREQUENCY_EVIDENCE
    )


@pytest.mark.asyncio
async def test_materialize_hot_set_can_include_optional_pos_by_city_without_refetching(
    tmp_path: Path,
) -> None:
    repository = _bootstrapped_repository(tmp_path)
    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    connector = _SAMAConnectorSpy()
    tool = HotSetMaterializationTool(
        repository,
        SourceConnectorResolver({"sama": connector}),
        snapshot_store,
    )

    result = await tool.materialize_hot_set(include_optional=True)

    assert result.requested_dataset_count == len(WAVE_1_HOT_SET_TIER_A_DATASET_IDS) + len(
        WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS
    )
    assert result.materialized_count == result.requested_dataset_count
    assert result.failed_count == 0
    assert connector.calls.count("/en-US/Indices/Pages/POS.aspx") == 1
    assert set(connector.calls) == {
        "/en-US/Indices/Pages/POS.aspx",
        "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        "report.aspx?cid=55",
    }

    results_by_id = {result.dataset_id: result for result in result.results}
    assert results_by_id["sama-pos-by-city"].tier is HotSetTier.TIER_B_OPTIONAL
    assert results_by_id["sama-pos-by-city"].local_snapshot_exists is True
    assert (
        results_by_id["sama-pos-by-city"].normalization_status
        is NormalizationPipelineStatus.LIMITED
    )
    assert results_by_id["sama-pos-by-city"].limitations == (TEXT_HTML_LIMITATION,)
