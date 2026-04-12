"""Deterministic initial registry bootstrap."""

from __future__ import annotations

from .models import DatasetDescriptor, DatasetHealthStatus, UpdateFrequency
from .repository import RegistryRepository

WAVE_1_HOT_SET_TIER_A_DATASET_IDS: tuple[str, ...] = (
    "sama-pos-weekly",
    "sama-exchange-rates-current",
    "sama-money-supply-weekly",
    "sama-repo-rate",
    "sama-reverse-repo-rate",
    "sama-deposits-core",
)
WAVE_1_HOT_SET_OPTIONAL_DATASET_IDS: tuple[str, ...] = ("sama-pos-by-city",)
SAMA_SHARED_SOURCE_LOCATOR_GROUPS: dict[tuple[str, str], tuple[str, ...]] = {
    ("sama", "/en-US/Indices/Pages/POS.aspx"): (
        "sama-pos-by-city",
        "sama-pos-weekly",
    ),
    ("sama", "report.aspx?cid=55"): (
        "sama-deposits-core",
        "sama-money-supply",
    ),
}

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
        dataset_id="mof-budget-balance-quarterly",
        source="mof",
        source_locator="/en/financialreport/2025/Pages/default.aspx",
        title="Budget Balance Quarterly",
        description=(
            "Registry entry for the Ministry of Finance quarterly budget performance "
            "reports page and linked quarterly report PDFs."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first Ministry of Finance fiscal entry normalizes one narrow "
            "headline budget-balance series from supported quarterly report PDFs "
            "linked by the official MoF 2025 budget performance page.",
        ),
        known_issues=(
            "Only the top-line quarterly budget-balance series is normalized. This "
            "does not yet cover total revenue, total expenditure, financing tables, "
            "public debt, or broader fiscal statement coverage.",
            "This connector path is intentionally pinned to the official 2025 budget "
            "performance page and requires explicit rollover when the Ministry of "
            "Finance publishes the next annual reports page.",
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
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        source="stats-gov-sa",
        source_locator="/en/news?q=inflation&delta=20&start=0",
        title="CPI Headline Inflation Monthly",
        description=(
            "Registry entry for headline CPI monthly release cards on the official "
            "stats.gov.sa inflation news surface."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first non-SAMA macro entry normalizes supported headline CPI release "
            "cards from the official stats.gov.sa inflation-filtered news page.",
        ),
        known_issues=(
            "Only supported release cards with explicit observation month, annual "
            "headline rate, monthly headline rate, and release link are normalized. "
            "This does not yet cover CPI index values, category tables, regional cuts, "
            "or the GASTAT statistical database.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="sama-exchange-rates-current",
        source="sama",
        source_locator="/en-US/FinExc/Pages/Currency.aspx",
        title="Current Exchange Rates",
        description=("Registry entry for the SAMA current exchange-rates page."),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.DAILY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This canonical dataset normalizes the latest published closing-price rows "
            "from the official SAMA current exchange-rates page.",
        ),
        known_issues=(
            "Only supported paginated results for the latest published date with "
            "resolvable currency codes and explicit closing-price rows are normalized.",
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
            "This bundled canonical dataset remains intentionally unsplit for now "
            "because the current SAMA monthly report surface publishes the core "
            "deposit components inside one shared report payload.",
            "This descriptor intentionally shares the same SAMA report locator as "
            "sama-money-supply.",
        ),
        known_issues=(
            "This upstream mapping is hand-curated and may need revision if SAMA "
            "changes report structure or routes.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="stats-gov-sa-real-gdp-growth-quarterly",
        source="stats-gov-sa",
        source_locator="/en/news?q=gdp&delta=20&start=0",
        title="GDP Headline Growth Quarterly",
        description=(
            "Registry entry for quarterly headline real GDP release cards on the "
            "official stats.gov.sa gdp news surface."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first GASTAT GDP entry normalizes supported headline real GDP "
            "release cards from the official stats.gov.sa gdp-filtered news page.",
        ),
        known_issues=(
            "Only supported release cards with an explicit observation quarter, "
            "headline real GDP growth rate, publication date, and release link are "
            "normalized. This does not yet cover GDP levels, nominal GDP, activity "
            "breakdowns, seasonally adjusted quarterly growth, PDFs, or the broader "
            "national-accounts statistical database.",
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
            "This descriptor intentionally shares the same SAMA report locator as "
            "sama-deposits-core.",
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
            "This canonical dataset normalizes supported weekly aggregate tables "
            "from the official weekly money-supply page.",
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
            "This canonical dataset normalizes supported published date and rate "
            "rows from the official repo-rate table on the official page.",
        ),
        known_issues=(
            "Only supported repo-rate table layouts with explicit Publish Date "
            "and Rate (%) columns are normalized.",
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
            "This descriptor intentionally shares the same SAMA page locator as "
            "sama-pos-weekly, but keeps a separate canonical dataset_id.",
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
            "This canonical dataset normalizes supported weekly summary content "
            "from the official POS report bundle linked from the official POS page.",
            "This descriptor intentionally shares the same SAMA page locator as "
            "sama-pos-by-city.",
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
            "This canonical dataset normalizes supported effective-date and rate "
            "content from the official reverse-repo-rate page.",
        ),
        known_issues=(
            "Only supported page text or simple table layouts with explicit "
            "effective-date and rate content are normalized.",
        ),
    ),
    DatasetDescriptor(
        dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
        source="stats-gov-sa",
        source_locator="/en/news?q=unemployment&delta=20&start=0",
        title="Unemployment Rate Total Population Quarterly",
        description=(
            "Registry entry for quarterly total-population unemployment release cards "
            "on the official stats.gov.sa unemployment news surface."
        ),
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        caveats=(
            "This first GASTAT labor entry normalizes supported labor-market release "
            "cards from the official stats.gov.sa unemployment-filtered news page.",
        ),
        known_issues=(
            "Only supported release cards with an explicit observation quarter, "
            "overall unemployment rate for Saudis and non-Saudis, publication date, "
            "and release link are normalized. This does not yet cover Saudi-only "
            "series, participation rates, demographic cuts, publication PDFs, or the "
            "broader labor statistical database.",
        ),
    ),
)


def _group_descriptors_by_source(
    descriptors: tuple[DatasetDescriptor, ...],
) -> dict[str, tuple[DatasetDescriptor, ...]]:
    grouped: dict[str, list[DatasetDescriptor]] = {}
    for descriptor in descriptors:
        grouped.setdefault(descriptor.source, []).append(descriptor)

    return {
        source: tuple(source_descriptors)
        for source, source_descriptors in grouped.items()
    }


INITIAL_DATASET_DESCRIPTORS_BY_SOURCE: dict[str, tuple[DatasetDescriptor, ...]] = (
    _group_descriptors_by_source(INITIAL_DATASET_DESCRIPTORS)
)


def bootstrap_registry(repository: RegistryRepository) -> list[DatasetDescriptor]:
    """Seed the registry with the current MVP descriptor set."""

    bootstrapped_descriptors = [
        descriptor.model_copy(deep=True) for descriptor in INITIAL_DATASET_DESCRIPTORS
    ]
    for descriptor in bootstrapped_descriptors:
        repository.seed_dataset(descriptor)

    return bootstrapped_descriptors
