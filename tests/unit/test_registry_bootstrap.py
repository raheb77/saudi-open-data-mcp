"""Unit tests for the deterministic registry bootstrap."""

from __future__ import annotations

from pathlib import Path

from saudi_open_data_mcp.connectors.resolver import DEFAULT_CONNECTOR_SOURCE_IDS
from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    INITIAL_DATASET_DESCRIPTORS_BY_SOURCE,
    SAMA_SHARED_SOURCE_LOCATOR_GROUPS,
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
    assert set(INITIAL_DATASET_DESCRIPTORS_BY_SOURCE) == set(DEFAULT_CONNECTOR_SOURCE_IDS)
    assert {
        descriptor.dataset_id
        for descriptor in INITIAL_DATASET_DESCRIPTORS_BY_SOURCE["stats-gov-sa"]
    } == {
        "stats-gov-sa-cpi-headline-monthly",
        "stats-gov-sa-unemployment-rate-total-quarterly",
        "stats-gov-sa-real-gdp-growth-quarterly",
    }
    assert {
        descriptor.dataset_id for descriptor in INITIAL_DATASET_DESCRIPTORS_BY_SOURCE["mof"]
    } == {
        "mof-budget-balance-quarterly",
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
    assert SAMA_SHARED_SOURCE_LOCATOR_GROUPS == {
        ("sama", "/en-US/Indices/Pages/POS.aspx"): (
            "sama-pos-by-city",
            "sama-pos-weekly",
        ),
        ("sama", "report.aspx?cid=55"): (
            "sama-deposits-core",
            "sama-money-supply",
        ),
    }
    assert any(
        "shares the same SAMA page locator as sama-pos-by-city" in caveat
        for caveat in descriptors_by_id["sama-pos-weekly"].caveats
    )
    assert any(
        "shares the same SAMA report locator as sama-money-supply" in caveat
        for caveat in descriptors_by_id["sama-deposits-core"].caveats
    )
    assert any(descriptor.source == "data-gov-sa" for descriptor in bootstrapped_descriptors)
    assert (
        descriptors_by_id["stats-gov-sa-cpi-headline-monthly"].source_locator
        == "/en/news?q=inflation&delta=20&start=0"
    )
    assert (
        descriptors_by_id["stats-gov-sa-unemployment-rate-total-quarterly"].source_locator
        == "/en/news?q=unemployment&delta=20&start=0"
    )
    assert (
        descriptors_by_id["stats-gov-sa-real-gdp-growth-quarterly"].source_locator
        == "/en/news?q=gdp&delta=20&start=0"
    )
    assert any(descriptor.source == "stats-gov-sa" for descriptor in bootstrapped_descriptors)
    assert (
        descriptors_by_id["mof-budget-balance-quarterly"].source_locator
        == "/en/financialreport/2025/Pages/default.aspx"
    )
    assert any(
        "requires explicit rollover" in known_issue
        for known_issue in descriptors_by_id["mof-budget-balance-quarterly"].known_issues
    )
    assert any(descriptor.source == "mof" for descriptor in bootstrapped_descriptors)


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
