"""Unit tests for the deterministic registry bootstrap."""

from __future__ import annotations

from pathlib import Path

from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS,
    WAVE_1_HOT_SET_TIER_A_DATASET_IDS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import (
    DatasetDescriptor,
    DatasetHealthStatus,
    HealthMetadata,
)
from saudi_open_data_mcp.registry.repository import RegistryRepository


def test_bootstrap_inserts_expected_initial_descriptors(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")

    bootstrapped_descriptors = bootstrap_registry(repository)

    assert bootstrapped_descriptors == list(INITIAL_DATASET_DESCRIPTORS)
    assert repository.list_datasets() == bootstrapped_descriptors
    assert all(isinstance(item, DatasetDescriptor) for item in bootstrapped_descriptors)
    descriptors_by_id = {
        descriptor.dataset_id: descriptor for descriptor in bootstrapped_descriptors
    }

    assert set(WAVE_1_HOT_SET_TIER_A_DATASET_IDS).issubset(descriptors_by_id)
    assert set(WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS).issubset(descriptors_by_id)
    assert descriptors_by_id["sama-pos-weekly"].source_locator == "/en-US/Indices/Pages/POS.aspx"
    assert (
        descriptors_by_id["sama-money-supply-weekly"].source_locator
        == "/en-US/Indices/Pages/WeeklyMoneySupply.aspx"
    )
    assert (
        descriptors_by_id["sama-repo-rate"].source_locator
        == "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx"
    )
    assert (
        descriptors_by_id["sama-reverse-repo-rate"].source_locator
        == "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx"
    )
    assert descriptors_by_id["sama-deposits-core"].source_locator == "report.aspx?cid=55"
    assert (
        descriptors_by_id["sama-exchange-rates-current"].source_locator
        == "/en-US/FinExc/Pages/Currency.aspx"
    )
    assert any(descriptor.source == "data-gov-sa" for descriptor in bootstrapped_descriptors)


def test_bootstrap_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")

    first_run = bootstrap_registry(repository)
    second_run = bootstrap_registry(repository)

    assert first_run == second_run
    assert repository.list_datasets() == first_run


def test_subsequent_bootstrap_preserves_existing_health_state(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    updated_health = HealthMetadata(
        dataset_id="sama-money-supply",
        health_status=DatasetHealthStatus.DEGRADED,
    )

    bootstrap_registry(repository)
    repository.upsert_health(updated_health)
    second_run = bootstrap_registry(repository)

    assert second_run == list(INITIAL_DATASET_DESCRIPTORS)
    assert repository.get_health("sama-money-supply") == updated_health
    assert repository.get_dataset("sama-money-supply") is not None
    assert repository.get_dataset("sama-money-supply").health_status is (
        DatasetHealthStatus.DEGRADED
    )
