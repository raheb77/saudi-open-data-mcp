"""Boundary validation tests for tool-facing user inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.download import DatasetDownloadTool
from saudi_open_data_mcp.tools.health import DatasetHealthTool
from saudi_open_data_mcp.tools.metadata import DatasetMetadataTool
from saudi_open_data_mcp.tools.preview import (
    DatasetPreviewTool,
    PreviewFailureStage,
    PreviewStatus,
)
from saudi_open_data_mcp.tools.query import DatasetQueryTool
from saudi_open_data_mcp.tools.search import DatasetSearchTool


def _repository(tmp_path: Path) -> RegistryRepository:
    return RegistryRepository(tmp_path / "registry.sqlite")


def _query_tool(tmp_path: Path) -> DatasetQueryTool:
    return DatasetQueryTool(
        _repository(tmp_path),
        SnapshotStore(tmp_path / "snapshots"),
    )


@pytest.mark.parametrize(
    ("tool_factory", "method_name"),
    [
        (lambda tmp_path: DatasetMetadataTool(_repository(tmp_path)), "get_dataset_metadata"),
        (lambda tmp_path: DatasetHealthTool(_repository(tmp_path)), "get_dataset_health"),
        (
            lambda tmp_path: DatasetDownloadTool(
                _repository(tmp_path),
                SnapshotStore(tmp_path / "snapshots"),
            ),
            "get_dataset_download",
        ),
        (lambda tmp_path: _query_tool(tmp_path), "query_dataset"),
    ],
)
@pytest.mark.parametrize(
    ("dataset_id", "expected_message"),
    [
        ("bad\x00dataset", "dataset_id must not contain null bytes"),
        ("x" * 257, "dataset_id must not exceed 256 characters"),
    ],
)
def test_tools_reject_invalid_dataset_id_inputs(
    tmp_path: Path,
    tool_factory,
    method_name: str,
    dataset_id: str,
    expected_message: str,
) -> None:
    tool = tool_factory(tmp_path)
    method = getattr(tool, method_name)

    with pytest.raises(ValueError, match=expected_message):
        method(dataset_id)


def test_search_tool_rejects_invalid_query_inputs(tmp_path: Path) -> None:
    tool = DatasetSearchTool(_repository(tmp_path))

    with pytest.raises(ValueError, match="query must not contain null bytes"):
        tool.search_datasets("money\x00")

    with pytest.raises(ValueError, match="query must not exceed 512 characters"):
        tool.search_datasets("q" * 513)


def test_query_tool_rejects_invalid_filter_inputs(tmp_path: Path) -> None:
    tool = _query_tool(tmp_path)

    with pytest.raises(ValueError, match="query filter key must not contain null bytes"):
        tool.query_dataset("sama-money-supply", filters={"period\x00": "2026-01"})

    with pytest.raises(ValueError, match="query filter value must not exceed 512 characters"):
        tool.query_dataset("sama-money-supply", filters={"period": "x" * 513})


def test_query_tool_rejects_excessive_limit(tmp_path: Path) -> None:
    tool = _query_tool(tmp_path)

    with pytest.raises(ValueError, match="limit must be less than or equal to 1000"):
        tool.query_dataset("sama-money-supply", limit=1001)


@pytest.mark.asyncio
async def test_preview_tool_returns_lookup_failure_for_invalid_dataset_id(
    tmp_path: Path,
) -> None:
    tool = DatasetPreviewTool(_repository(tmp_path), connector_resolver={})  # type: ignore[arg-type]

    null_byte_result = await tool.preview_dataset("bad\x00dataset")
    overlong_result = await tool.preview_dataset("x" * 257)

    assert null_byte_result.status is PreviewStatus.FAILED
    assert null_byte_result.failure is not None
    assert null_byte_result.failure.stage is PreviewFailureStage.LOOKUP
    assert null_byte_result.failure.message == "dataset_id must not contain null bytes"

    assert overlong_result.status is PreviewStatus.FAILED
    assert overlong_result.failure is not None
    assert overlong_result.failure.stage is PreviewFailureStage.LOOKUP
    assert overlong_result.failure.message == "dataset_id must not exceed 256 characters"
