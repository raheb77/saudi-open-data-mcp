"""Unit tests for the SQLite-backed registry repository."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
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
        source_locator=f"report.aspx?cid={sum(dataset_id.encode('utf-8'))}",
        title=title,
        description=f"{title} dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=health_status,
        coverage_status=DatasetCoverageStatus.QUERYABLE,
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

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(dataset_descriptors)").fetchall()
        }

    assert "source_locator" in columns
    assert "coverage_status" in columns


def test_repository_initialization_adds_new_descriptor_columns_to_existing_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "registry.sqlite"

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE dataset_descriptors (
                dataset_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                update_frequency TEXT NOT NULL,
                health_status TEXT NOT NULL,
                caveats_json TEXT NOT NULL,
                known_issues_json TEXT NOT NULL
            );

            CREATE TABLE dataset_health (
                dataset_id TEXT PRIMARY KEY,
                health_status TEXT NOT NULL
            );
            """
        )

    repository = RegistryRepository(database_path)
    descriptor = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
    )
    repository.upsert_dataset(descriptor)

    stored = repository.get_dataset(descriptor.dataset_id)

    assert stored == descriptor


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


def test_seed_dataset_reconciles_descriptor_fields_without_overwriting_health(
    tmp_path: Path,
) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    current_seed = _descriptor(
        dataset_id="sama-money-supply",
        title="Money Supply",
        health_status=DatasetHealthStatus.UNKNOWN,
    )
    stale_descriptor = current_seed.model_copy(
        update={
            "source_locator": "report.aspx?cid=999",
            "title": "Stale Title",
            "description": "Stale description",
            "schema_version": "0.2.0",
            "coverage_status": DatasetCoverageStatus.CATALOG_ONLY,
            "known_issues": ("Stale issue",),
        }
    )

    repository.upsert_dataset(stale_descriptor)
    repository.upsert_health(
        HealthMetadata(
            dataset_id=current_seed.dataset_id,
            health_status=DatasetHealthStatus.DEGRADED,
        )
    )

    result = repository.seed_dataset(current_seed)
    stored = repository.get_dataset(current_seed.dataset_id)

    assert result.action == "updated"
    assert result.changed_fields == (
        "source_locator",
        "title",
        "description",
        "schema_version",
        "coverage_status",
        "known_issues",
    )
    assert stored is not None
    assert stored.source_locator == current_seed.source_locator
    assert stored.title == current_seed.title
    assert stored.description == current_seed.description
    assert stored.schema_version == current_seed.schema_version
    assert stored.coverage_status is current_seed.coverage_status
    assert stored.known_issues == current_seed.known_issues
    assert stored.health_status is DatasetHealthStatus.DEGRADED
