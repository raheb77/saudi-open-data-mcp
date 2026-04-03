"""Deterministic initial registry bootstrap."""

from __future__ import annotations

from .models import DatasetDescriptor, DatasetHealthStatus, UpdateFrequency
from .repository import RegistryRepository

WAVE_1_HOT_SET_TIER_A_DATASET_IDS: tuple[str, ...] = (
    "sama-pos-weekly",
    "sama-money-supply-weekly",
    "sama-repo-rate",
    "sama-reverse-repo-rate",
    "sama-deposits-core",
)
WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS: tuple[str, ...] = ("sama-pos-by-city",)

INITIAL_DATASET_DESCRIPTORS: tuple[DatasetDescriptor, ...] = (
    DatasetDescriptor(
        dataset_id="sama-balance-of-payments",
        source="sama",
        source_locator="report.aspx?cid=41",
        title="Balance of Payments",
        description=("Registry entry for the SAMA balance of payments dataset."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="data-gov-sa-census-marital-status",
        source="data-gov-sa",
        source_locator=(
            "/ar/datasets/view/104380ce-60b6-46bc-ba0a-6d5e10ac46cb/"
            "preview/parsed/Census%20Marital%20Status%20CSV.json"
        ),
        title="Census Marital Status",
        description=("Registry entry for a data.gov.sa census marital status dataset."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.UNSPECIFIED,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated registry entry, not a complete data.gov.sa catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision "
            "if data.gov.sa changes preview routes or parsed resource formats.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-deposits-core",
        source="sama",
        source_locator="report.aspx?cid=55",
        title="Deposits Core Series",
        description=("Registry entry for SAMA-published core deposit aggregates."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave hot-set entry materializes the bundled report payload, "
            "not source-specific extracted deposit sub-series.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-interest-rates",
        source="sama",
        source_locator="report.aspx?cid=52",
        title="Interest Rates",
        description=("Registry entry for SAMA-published interest rate data."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-money-supply",
        source="sama",
        source_locator="report.aspx?cid=55",
        title="Money Supply",
        description=("Registry entry for SAMA monetary aggregate data."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This is a hand-curated registry entry, not a complete SAMA catalog entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-money-supply-weekly",
        source="sama",
        source_locator="/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
        title="Money Supply Weekly",
        description=("Registry entry for SAMA-published weekly money supply updates."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave hot-set entry materializes the official page payload "
            "without source-specific weekly series extraction.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes page routes or page content structure.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-repo-rate",
        source="sama",
        source_locator="/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
        title="Official Repo Rate",
        description=("Registry entry for the SAMA official repo rate page."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.AD_HOC,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave hot-set entry materializes the official page payload "
            "without source-specific rate extraction.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes page routes or page content structure.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-pos-by-city",
        source="sama",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        title="POS by City",
        description=("Registry entry for SAMA POS weekly reporting with city-level tables."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave Tier B entry reuses the same official POS page payload "
            "as the weekly POS hot-set entry.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes page routes, page structure, or city-table placement.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-pos-weekly",
        source="sama",
        source_locator="/en-US/Indices/Pages/POS.aspx",
        title="POS Weekly",
        description=("Registry entry for SAMA weekly point-of-sale reporting."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.WEEKLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave hot-set entry materializes the official page payload "
            "without source-specific weekly table extraction.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes page routes or page content structure.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-reverse-repo-rate",
        source="sama",
        source_locator="/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        title="Reverse Repo Rate",
        description=("Registry entry for the SAMA reverse repo rate page."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.AD_HOC,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first-wave hot-set entry materializes the official page payload "
            "without source-specific rate extraction.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes page routes or page content structure.",
        ),
    ),
)


def bootstrap_registry(repository: RegistryRepository) -> list[DatasetDescriptor]:
    """Seed the registry with the current MVP descriptor set."""

    bootstrapped_descriptors = [
        descriptor.model_copy(deep=True) for descriptor in INITIAL_DATASET_DESCRIPTORS
    ]
    for descriptor in bootstrapped_descriptors:
        repository.seed_dataset(descriptor)

    return bootstrapped_descriptors
