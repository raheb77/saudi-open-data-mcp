"""Unit tests for the dataset metadata tool."""

from __future__ import annotations

import ast
from pathlib import Path

from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.tools.metadata import (
    DatasetMetadataLookupResult,
    DatasetMetadataTool,
)


def _descriptor(dataset_id: str = "sama-money-supply") -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        title="Money Supply",
        description="Official monetary aggregate dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=("Publication timing may vary by release cycle.",),
        known_issues=("Historical revisions may occur.",),
    )


def test_get_dataset_metadata_returns_typed_metadata_for_valid_dataset_id(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor()
    tool = DatasetMetadataTool(repository)

    repository.upsert_dataset(descriptor)
    result = tool.get_dataset_metadata(descriptor.dataset_id)

    assert isinstance(result, DatasetMetadataLookupResult)
    assert result.status == "found"
    assert result.dataset_id == descriptor.dataset_id
    assert result.metadata == descriptor
    assert isinstance(result.metadata, DatasetDescriptor)


def test_get_dataset_metadata_returns_explicit_missing_result_for_unknown_dataset(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    tool = DatasetMetadataTool(repository)

    result = tool.get_dataset_metadata("missing-dataset")

    assert isinstance(result, DatasetMetadataLookupResult)
    assert result.status == "missing"
    assert result.dataset_id == "missing-dataset"
    assert result.metadata is None


def test_get_dataset_metadata_matches_repository_descriptor_without_transforming_it(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(dataset_id="sama-interest-rates")
    tool = DatasetMetadataTool(repository)

    repository.upsert_dataset(descriptor)
    stored_descriptor = repository.get_dataset(descriptor.dataset_id)
    result = tool.get_dataset_metadata(descriptor.dataset_id)

    assert stored_descriptor is not None
    assert result.status == "found"
    assert result.metadata == stored_descriptor


def test_metadata_tool_module_does_not_import_connectors() -> None:
    project_root = Path(__file__).resolve().parents[2]
    metadata_module = project_root / "src" / "saudi_open_data_mcp" / "tools" / "metadata.py"
    tree = ast.parse(metadata_module.read_text(), filename=str(metadata_module))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "connectors" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "connectors" not in alias.name
