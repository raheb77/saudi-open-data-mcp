"""Unit tests for the SQLite-backed registry repository."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    HealthMetadata,
    UpdateFrequency,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository


def _descriptor(
    *,
    dataset_id: str,
    title: str,
    health_status: DatasetHealthStatus = DatasetHealthStatus.HEALTHY,
) -> DatasetDescriptor:
    return DatasetDescriptor(
        dataset_id=dataset_id,
        source="sama",
        title=title,
        description=f"{title} dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=health_status,
        caveats=("Official source formatting may change.",),
        known_issues=("Historical revisions may occur.",),
    )


def test_repository_initialization_creates_required_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "registry.sqlite"
    RegistryRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert "dataset_descriptors" in table_names
    assert "dataset_health" in table_names


def test_upsert_and_get_dataset_round_trip_returns_typed_descriptor(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
    )

    repository.upsert_dataset(descriptor)
    stored = repository.get_dataset("sama-money-supply")

    assert stored == descriptor
    assert isinstance(stored, DatasetDescriptor)


def test_list_datasets_returns_typed_descriptors_in_deterministic_order(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    second = _descriptor(
        dataset_id="sama-zakat",
        title="Zakat Collections",
    )
    first = _descriptor(
        dataset_id="sama-balance-payments",
        title="Balance of Payments",
    )

    repository.upsert_dataset(second)
    repository.upsert_dataset(first)

    descriptors = repository.list_datasets()

    assert descriptors == [first, second]
    assert all(isinstance(item, DatasetDescriptor) for item in descriptors)


def test_search_datasets_matches_title_and_dataset_id_deterministically(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor_a = _descriptor(
        dataset_id="sama-money-market-a",
        title="Money Market",
    )
    descriptor_b = _descriptor(
        dataset_id="sama-money-market-b",
        title="Money Market",
    )
    descriptor_c = _descriptor(
        dataset_id="sama-interest-rates",
        title="Interest Rates",
    )

    repository.upsert_dataset(descriptor_b)
    repository.upsert_dataset(descriptor_c)
    repository.upsert_dataset(descriptor_a)

    title_matches = repository.search_datasets("money")
    id_matches = repository.search_datasets("interest-rates")

    assert title_matches == [descriptor_a, descriptor_b]
    assert id_matches == [descriptor_c]


def test_health_metadata_round_trip_and_descriptor_status_sync(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    descriptor = _descriptor(
        dataset_id="sama-credit",
        title="Credit",
        health_status=DatasetHealthStatus.UNKNOWN,
    )
    updated_health = HealthMetadata(
        dataset_id="sama-credit",
        health_status=DatasetHealthStatus.DEGRADED,
    )

    repository.upsert_dataset(descriptor)
    repository.upsert_health(updated_health)

    assert repository.get_health("sama-credit") == updated_health
    assert repository.list_health() == [updated_health]
    assert repository.get_dataset("sama-credit") is not None
    assert repository.get_dataset("sama-credit").health_status is DatasetHealthStatus.DEGRADED


def test_missing_dataset_and_health_lookups_return_none(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")

    assert repository.get_dataset("missing-dataset") is None
    assert repository.get_health("missing-dataset") is None
