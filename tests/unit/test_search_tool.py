"""Unit tests for the dataset search tool."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.tools.search import (
    DatasetSearchMatch,
    DatasetSearchMode,
    DatasetSearchResult,
    DatasetSearchStatus,
    DatasetSearchTool,
)


def _descriptor(
    *,
    dataset_id: str,
    title: str,
    health_status: DatasetHealthStatus = DatasetHealthStatus.UNKNOWN,
) -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        source_locator=f"report.aspx?cid={sum(dataset_id.encode('utf-8'))}",
        title=title,
        description=f"{title} dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=health_status,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
        caveats=("Publication timing may vary by release cycle.",),
        known_issues=("Historical revisions may occur.",),
    )


def test_search_datasets_returns_typed_matches_for_known_query(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
        health_status=DatasetHealthStatus.HEALTHY,
    )
    repository.upsert_dataset(descriptor)
    tool = DatasetSearchTool(repository)

    result = tool.search_datasets("money")

    assert isinstance(result, DatasetSearchResult)
    assert result.status is DatasetSearchStatus.RESULTS
    assert result.mode is DatasetSearchMode.FILTERED
    assert result.query == "money"
    assert result.normalized_query == "money"
    assert result.match_count == 1
    assert result.matches == (
        DatasetSearchMatch(
            dataset_id="sama-money-supply",
            source="sama",
            title="Money Supply",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.HEALTHY,
            coverage_status=DatasetCoverageStatus.QUERYABLE,
        ),
    )


def test_search_datasets_preserves_repository_ordering(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor_b = _descriptor(
        dataset_id="sama-money-market-b",
        title="Money Market",
    )
    descriptor_a = _descriptor(
        dataset_id="sama-money-market-a",
        title="Money Market",
    )
    repository.upsert_dataset(descriptor_b)
    repository.upsert_dataset(descriptor_a)
    tool = DatasetSearchTool(repository)

    result = tool.search_datasets("money")

    assert [match.dataset_id for match in result.matches] == [
        "sama-money-market-a",
        "sama-money-market-b",
    ]


def test_search_datasets_empty_query_returns_all_datasets_explicitly(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor_a = _descriptor(
        dataset_id="sama-balance-of-payments",
        title="Balance of Payments",
    )
    descriptor_b = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
    )
    repository.upsert_dataset(descriptor_b)
    repository.upsert_dataset(descriptor_a)
    tool = DatasetSearchTool(repository)

    result = tool.search_datasets("   ")

    assert result.status is DatasetSearchStatus.RESULTS
    assert result.mode is DatasetSearchMode.ALL_DATASETS
    assert result.normalized_query == ""
    assert result.match_count == 2
    assert [match.dataset_id for match in result.matches] == [
        "sama-balance-of-payments",
        "sama-money-supply",
    ]


def test_search_datasets_returns_empty_result_for_no_matches(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    repository.upsert_dataset(
        _descriptor(
            dataset_id="sama-interest-rates",
            title="Interest Rates",
        )
    )
    tool = DatasetSearchTool(repository)

    result = tool.search_datasets("no-match-query")

    assert result.status is DatasetSearchStatus.NO_RESULTS
    assert result.mode is DatasetSearchMode.FILTERED
    assert result.normalized_query == "no-match-query"
    assert result.match_count == 0
    assert result.matches == ()


def test_search_result_rejects_no_results_status_with_non_empty_matches() -> None:
    with pytest.raises(ValueError, match="non-empty matches require results status"):
        DatasetSearchResult(
            query="money",
            normalized_query="money",
            status=DatasetSearchStatus.NO_RESULTS,
            mode=DatasetSearchMode.FILTERED,
            match_count=1,
            matches=(
                DatasetSearchMatch(
                    dataset_id="sama-money-supply",
                    source="sama",
                    title="Money Supply",
                    update_frequency=UpdateFrequency.MONTHLY,
                    health_status=DatasetHealthStatus.UNKNOWN,
                    coverage_status=DatasetCoverageStatus.QUERYABLE,
                ),
            ),
        )


def test_search_result_rejects_results_status_with_empty_matches() -> None:
    with pytest.raises(ValueError, match="empty matches require no_results status"):
        DatasetSearchResult(
            query="money",
            normalized_query="money",
            status=DatasetSearchStatus.RESULTS,
            mode=DatasetSearchMode.FILTERED,
            match_count=0,
            matches=(),
        )


def test_search_tool_module_does_not_import_connectors() -> None:
    project_root = Path(__file__).resolve().parents[2]
    search_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "search.py"
    tree = ast.parse(search_module.read_text(), filename=str(search_module))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "connectors" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "connectors" not in alias.name
