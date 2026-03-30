"""Deterministic initial registry bootstrap."""

from __future__ import annotations

from .models import DatasetDescriptor, DatasetHealthStatus, UpdateFrequency
from .repository import RegistryRepository

INITIAL_DATASET_DESCRIPTORS: tuple[DatasetDescriptor, ...] = (
    DatasetDescriptor(
        dataset_id="sama-balance-of-payments",
        source="sama",
        source_locator="report.aspx?cid=41",
        title="Balance of Payments",
        description=(
            "Initial v0.1 seed descriptor for the SAMA balance of payments dataset."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated v0.1 registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated for v0.1 and may need revision "
            "if SAMA changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-interest-rates",
        source="sama",
        source_locator="report.aspx?cid=52",
        title="Interest Rates",
        description=(
            "Initial v0.1 seed descriptor for SAMA-published interest rate data."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated v0.1 registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated for v0.1 and may need revision "
            "if SAMA changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-money-supply",
        source="sama",
        source_locator="report.aspx?cid=55",
        title="Money Supply",
        description=(
            "Initial v0.1 seed descriptor for SAMA monetary aggregate data."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated v0.1 registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated for v0.1 and may need revision "
            "if SAMA changes report structure or routes.",
        ),
    ),
)


def bootstrap_registry(repository: RegistryRepository) -> list[DatasetDescriptor]:
    """Seed the registry with the initial v0.1 descriptor set."""

    bootstrapped_descriptors = [
        descriptor.model_copy(deep=True) for descriptor in INITIAL_DATASET_DESCRIPTORS
    ]
    for descriptor in bootstrapped_descriptors:
        repository.upsert_dataset(descriptor)

    return bootstrapped_descriptors
