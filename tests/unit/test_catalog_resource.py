"""Unit tests for the registry-backed catalog resource."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from saudi_open_data_mcp.registry.bootstrap import bootstrap_registry
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.resources.catalog import (
    CatalogDatasetSummary,
    CatalogResource,
    CatalogSummary,
)


def _descriptor(*, dataset_id: str, title: str) -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        source_locator=f"report.aspx?cid={sum(dataset_id.encode('utf-8'))}",
        title=title,
        description=f"{title} dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=("Official labeling may change.",),
        known_issues=(
            "The source locator is hand-curated for v0.1 and may need revision if "
            "SAMA changes the report route.",
        ),
    )


def test_catalog_resource_returns_typed_summaries_from_bootstrapped_registry(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    bootstrapped_descriptors = bootstrap_registry(repository)
    resource = CatalogResource(repository)

    catalog = resource.read()

    expected_datasets = tuple(
        CatalogDatasetSummary.from_descriptor(descriptor)
        for descriptor in bootstrapped_descriptors
    )

    assert catalog == CatalogSummary(
        dataset_count=len(expected_datasets),
        datasets=expected_datasets,
    )
    assert all(isinstance(item, CatalogDatasetSummary) for item in catalog.datasets)


def test_catalog_resource_preserves_repository_ordering(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    later = _descriptor(dataset_id="sama-zakat", title="Zakat Collections")
    earlier = _descriptor(
        dataset_id="sama-balance-payments",
        title="Balance of Payments",
    )
    resource = CatalogResource(repository)

    repository.upsert_dataset(later)
    repository.upsert_dataset(earlier)

    catalog = resource.read()
    repository_order = repository.list_datasets()

    assert catalog.datasets == tuple(
        CatalogDatasetSummary.from_descriptor(descriptor)
        for descriptor in repository_order
    )
    assert [item.dataset_id for item in catalog.datasets] == [
        descriptor.dataset_id for descriptor in repository_order
    ]


def test_catalog_resource_output_is_read_only(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
    )
    resource = CatalogResource(repository)
    repository.upsert_dataset(descriptor)

    catalog = resource.read()

    assert isinstance(catalog.datasets, tuple)
    with pytest.raises(ValidationError):
        catalog.datasets[0].title = "Changed title"

    assert repository.get_dataset("sama-money-supply") == descriptor


def test_catalog_resource_returns_explicit_empty_summary_for_empty_repository(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    resource = CatalogResource(repository)

    catalog = resource.read()

    assert catalog == CatalogSummary(dataset_count=0, datasets=())
