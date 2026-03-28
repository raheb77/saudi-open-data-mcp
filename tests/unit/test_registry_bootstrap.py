"""Unit tests for the deterministic registry bootstrap."""

from __future__ import annotations

from pathlib import Path

from saudi_open_data_mcp.registry.bootstrap import (
    INITIAL_DATASET_DESCRIPTORS,
    bootstrap_registry,
)
from saudi_open_data_mcp.registry.models import DatasetDescriptor
from saudi_open_data_mcp.registry.repository import RegistryRepository


def test_bootstrap_inserts_expected_initial_descriptors(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")

    bootstrapped_descriptors = bootstrap_registry(repository)

    assert bootstrapped_descriptors == list(INITIAL_DATASET_DESCRIPTORS)
    assert repository.list_datasets() == bootstrapped_descriptors
    assert all(isinstance(item, DatasetDescriptor) for item in bootstrapped_descriptors)


def test_bootstrap_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")

    first_run = bootstrap_registry(repository)
    second_run = bootstrap_registry(repository)

    assert first_run == second_run
    assert repository.list_datasets() == first_run
