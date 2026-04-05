"""Canonical contract targets for the current enriched macro dataset set."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ContractText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ContractVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d+\.\d+\.\d+$"),
]


class CanonicalRecordShape(StrEnum):
    """Supported target record shapes for canonical enrichment work."""

    SNAPSHOT_OBSERVATION = "snapshot_observation"
    TIME_SERIES_OBSERVATION = "time_series_observation"


class CanonicalFieldType(StrEnum):
    """Supported canonical field types for contract definitions."""

    DATE = "date"
    DECIMAL = "decimal"
    INTEGER = "integer"
    STRING = "string"
    YEAR_QUARTER = "year_quarter"
    YEAR_MONTH = "year_month"


class CanonicalFieldRole(StrEnum):
    """Supported canonical field roles for query-oriented records."""

    DIMENSION = "dimension"
    MEASURE = "measure"


class TemporalGranularity(StrEnum):
    """Declared analytical time grain for a canonical contract."""

    DAILY = "daily"
    EVENT = "event"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    WEEKLY = "weekly"


class SchemaEvolutionPolicy(StrEnum):
    """Backward-safe evolution mode for a canonical contract."""

    ADDITIVE_WITHIN_MAJOR = "additive_within_major"


class CanonicalFieldDefinition(BaseModel):
    """Typed canonical field definition."""

    model_config = ConfigDict(extra="forbid")

    name: ContractText
    type: CanonicalFieldType
    role: CanonicalFieldRole
    description: ContractText
    required: bool = True
    unit: ContractText | None = None


class CanonicalDatasetContract(BaseModel):
    """Canonical record contract for a dataset after source-specific enrichment."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: ContractText
    schema_version: ContractVersion
    record_shape: CanonicalRecordShape
    temporal_granularity: TemporalGranularity
    primary_key: tuple[ContractText, ...]
    dimensions: tuple[CanonicalFieldDefinition, ...] = Field(default_factory=tuple)
    measures: tuple[CanonicalFieldDefinition, ...] = Field(default_factory=tuple)
    structure_note: ContractText | None = None
    intended_analytical_uses: tuple[ContractText, ...] = Field(default_factory=tuple)
    evolution_policy: SchemaEvolutionPolicy = SchemaEvolutionPolicy.ADDITIVE_WITHIN_MAJOR

    @model_validator(mode="after")
    def validate_contract(self) -> "CanonicalDatasetContract":
        """Validate field-role consistency and key coverage."""

        dimension_names = tuple(field.name for field in self.dimensions)
        measure_names = tuple(field.name for field in self.measures)
        all_field_names = dimension_names + measure_names

        if not self.primary_key:
            raise ValueError("canonical contract must declare at least one primary key field")
        if not self.measures:
            raise ValueError("canonical contract must declare at least one measure field")
        if len(set(all_field_names)) != len(all_field_names):
            raise ValueError("canonical contract field names must be unique")
        if any(field.role is not CanonicalFieldRole.DIMENSION for field in self.dimensions):
            raise ValueError("dimension definitions must use the dimension role")
        if any(field.role is not CanonicalFieldRole.MEASURE for field in self.measures):
            raise ValueError("measure definitions must use the measure role")

        missing_key_fields = tuple(
            field_name for field_name in self.primary_key if field_name not in dimension_names
        )
        if missing_key_fields:
            formatted = ", ".join(missing_key_fields)
            raise ValueError(
                f"canonical contract primary_key fields must be declared as dimensions: {formatted}"
            )

        return self


def _dimension(
    name: str,
    *,
    type: CanonicalFieldType,
    description: str,
) -> CanonicalFieldDefinition:
    return CanonicalFieldDefinition(
        name=name,
        type=type,
        role=CanonicalFieldRole.DIMENSION,
        description=description,
    )


def _measure(
    name: str,
    *,
    type: CanonicalFieldType,
    description: str,
    unit: str | None = None,
) -> CanonicalFieldDefinition:
    return CanonicalFieldDefinition(
        name=name,
        type=type,
        role=CanonicalFieldRole.MEASURE,
        description=description,
        unit=unit,
    )


SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS: tuple[CanonicalDatasetContract, ...] = (
    CanonicalDatasetContract(
        dataset_id="sama-pos-weekly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.WEEKLY,
        primary_key=("week_start_date", "week_end_date"),
        dimensions=(
            _dimension(
                "week_start_date",
                type=CanonicalFieldType.DATE,
                description="Inclusive start date for the reported POS week.",
            ),
            _dimension(
                "week_end_date",
                type=CanonicalFieldType.DATE,
                description="Inclusive end date for the reported POS week.",
            ),
        ),
        measures=(
            _measure(
                "transaction_count",
                type=CanonicalFieldType.INTEGER,
                description="Total POS transactions recorded during the week.",
            ),
            _measure(
                "transaction_value_sar",
                type=CanonicalFieldType.DECIMAL,
                description="Total POS transaction value normalized to Saudi Riyals.",
                unit="SAR",
            ),
            _measure(
                "average_ticket_sar",
                type=CanonicalFieldType.DECIMAL,
                description=(
                    "Derived average POS transaction value for the week, normalized to "
                    "Saudi Riyals."
                ),
                unit="SAR",
            ),
        ),
        intended_analytical_uses=(
            "Track weekly POS spending momentum in value and volume terms.",
            "Support derived metrics such as average ticket size and week-over-week growth.",
        ),
    ),
    CanonicalDatasetContract(
        dataset_id="sama-money-supply-weekly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.WEEKLY,
        primary_key=("week_end_date", "monetary_aggregate_code"),
        dimensions=(
            _dimension(
                "week_end_date",
                type=CanonicalFieldType.DATE,
                description="Reported week-ending date for the money-supply snapshot.",
            ),
            _dimension(
                "monetary_aggregate_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the reported monetary aggregate.",
            ),
            _dimension(
                "monetary_aggregate_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable name of the reported monetary aggregate.",
            ),
        ),
        measures=(
            _measure(
                "amount_sar",
                type=CanonicalFieldType.DECIMAL,
                description="Aggregate amount normalized to Saudi Riyals.",
                unit="SAR",
            ),
        ),
        intended_analytical_uses=(
            "Track weekly liquidity changes across monetary aggregates.",
            "Compare growth patterns across M0, M1, M2, and later compatible aggregate groupings.",
        ),
    ),
    CanonicalDatasetContract(
        dataset_id="sama-deposits-core",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.MONTHLY,
        primary_key=("observation_month", "deposit_category_code"),
        dimensions=(
            _dimension(
                "observation_month",
                type=CanonicalFieldType.YEAR_MONTH,
                description="Reported month for the deposit observation.",
            ),
            _dimension(
                "deposit_category_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the deposit category within the bundled series.",
            ),
            _dimension(
                "deposit_category_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable deposit category label.",
            ),
            _dimension(
                "related_monetary_aggregate_code",
                type=CanonicalFieldType.STRING,
                description=(
                    "Lowest standard monetary aggregate level where the deposit "
                    "component enters the M1/M2/M3 sequence."
                ),
            ),
            _dimension(
                "related_monetary_aggregate_name",
                type=CanonicalFieldType.STRING,
                description=(
                    "Human-readable label for the related monetary aggregate level."
                ),
            ),
        ),
        measures=(
            _measure(
                "amount_sar",
                type=CanonicalFieldType.DECIMAL,
                description="Deposit amount normalized to Saudi Riyals.",
                unit="SAR",
            ),
        ),
        structure_note=(
            "Remains a bundled canonical dataset for now because the current SAMA "
            "monthly report surface publishes the core deposit components inside "
            "one shared report payload."
        ),
        intended_analytical_uses=(
            "Compare monthly demand, time-and-savings, and quasi-money deposit trends.",
            "Relate deposit-category shifts to the M1/M2/M3 monetary aggregate ladder "
            "without pretending the current source is already split into standalone "
            "deposit datasets.",
        ),
    ),
    CanonicalDatasetContract(
        dataset_id="sama-exchange-rates-current",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.SNAPSHOT_OBSERVATION,
        temporal_granularity=TemporalGranularity.DAILY,
        primary_key=("as_of_date", "currency_code"),
        dimensions=(
            _dimension(
                "as_of_date",
                type=CanonicalFieldType.DATE,
                description="As-of date for the daily current exchange-rate snapshot.",
            ),
            _dimension(
                "currency_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the non-SAR currency quoted against Saudi Riyal.",
            ),
            _dimension(
                "currency_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable name of the non-SAR currency.",
            ),
            _dimension(
                "quote_currency_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the quote currency used for the published rates.",
            ),
            _dimension(
                "quote_currency_name",
                type=CanonicalFieldType.STRING,
                description=(
                    "Human-readable name of the quote currency used for the "
                    "published rates."
                ),
            ),
        ),
        measures=(
            _measure(
                "buy_rate_sar",
                type=CanonicalFieldType.DECIMAL,
                description="Bank buy rate quoted in Saudi Riyals per currency unit.",
                unit="SAR",
            ),
            _measure(
                "sell_rate_sar",
                type=CanonicalFieldType.DECIMAL,
                description="Bank sell rate quoted in Saudi Riyals per currency unit.",
                unit="SAR",
            ),
        ),
        structure_note=(
            "Current exchange rates remain a daily current-quote snapshot surface. "
            "The canonical contract does not claim an authoritative intraday timestamp "
            "beyond the published as-of date."
        ),
        intended_analytical_uses=(
            "Answer daily FX quote lookups by non-SAR currency on a SAR-quoted basis.",
            "Compare buy/sell spreads across currencies and across stored daily snapshots.",
        ),
    ),
    CanonicalDatasetContract(
        dataset_id="sama-repo-rate",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.EVENT,
        primary_key=("effective_date",),
        dimensions=(
            _dimension(
                "effective_date",
                type=CanonicalFieldType.DATE,
                description="Effective date of the official repo rate observation.",
            ),
            _dimension(
                "policy_rate_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the policy rate series.",
            ),
            _dimension(
                "policy_rate_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the policy rate series.",
            ),
        ),
        measures=(
            _measure(
                "rate_percent",
                type=CanonicalFieldType.DECIMAL,
                description="Official repo rate expressed as a percentage.",
                unit="percent",
            ),
        ),
        structure_note=(
            "Current repo-rate enrichment extracts one effective-date observation "
            "from the official current policy-rate page. The source remains a simple "
            "current-page surface with ad-hoc policy updates, not a full historical table."
        ),
        intended_analytical_uses=(
            "Track the policy timeline of official repo rate changes.",
            "Join policy-rate changes to weekly liquidity and spending indicators.",
        ),
    ),
    CanonicalDatasetContract(
        dataset_id="sama-reverse-repo-rate",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.EVENT,
        primary_key=("effective_date",),
        dimensions=(
            _dimension(
                "effective_date",
                type=CanonicalFieldType.DATE,
                description="Effective date of the reverse repo rate observation.",
            ),
            _dimension(
                "policy_rate_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the policy rate series.",
            ),
            _dimension(
                "policy_rate_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the policy rate series.",
            ),
        ),
        measures=(
            _measure(
                "rate_percent",
                type=CanonicalFieldType.DECIMAL,
                description="Reverse repo rate expressed as a percentage.",
                unit="percent",
            ),
        ),
        structure_note=(
            "Current reverse-repo-rate enrichment extracts one effective-date observation "
            "from the official current policy-rate page. The source remains a simple "
            "current-page surface with ad-hoc policy updates, not a full historical table."
        ),
        intended_analytical_uses=(
            "Track the policy timeline of reverse repo rate changes.",
            "Compare reverse repo movements with repo-rate and liquidity series behavior.",
        ),
    ),
)

SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS: tuple[str, ...] = tuple(
    contract.dataset_id for contract in SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS
)

GASTAT_INFLATION_CONTRACTS: tuple[CanonicalDatasetContract, ...] = (
    CanonicalDatasetContract(
        dataset_id="stats-gov-sa-cpi-headline-monthly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.MONTHLY,
        primary_key=("observation_month", "inflation_series_code"),
        dimensions=(
            _dimension(
                "observation_month",
                type=CanonicalFieldType.YEAR_MONTH,
                description="Observed CPI month reported by the official release card.",
            ),
            _dimension(
                "inflation_series_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the supported headline CPI series.",
            ),
            _dimension(
                "inflation_series_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the supported headline CPI series.",
            ),
            _dimension(
                "release_date",
                type=CanonicalFieldType.DATE,
                description="Official publication date of the release card.",
            ),
        ),
        measures=(
            _measure(
                "yoy_rate_percent",
                type=CanonicalFieldType.DECIMAL,
                description="Headline year-over-year CPI inflation rate.",
                unit="percent",
            ),
            _measure(
                "mom_rate_percent",
                type=CanonicalFieldType.DECIMAL,
                description="Headline month-over-month CPI inflation rate.",
                unit="percent",
            ),
        ),
        structure_note=(
            "This first GASTAT inflation contract extracts supported headline CPI "
            "release cards from the official stats.gov.sa inflation-filtered news "
            "surface. It does not yet claim full CPI category tables, index values, "
            "regional cuts, or direct statistical-database coverage."
        ),
        intended_analytical_uses=(
            "Track the monthly headline CPI inflation path with explicit release dates.",
            "Support local exact-match analysis over monthly headline year-over-year "
            "and month-over-month inflation rates.",
        ),
    ),
)

GASTAT_INFLATION_DATASET_IDS: tuple[str, ...] = tuple(
    contract.dataset_id for contract in GASTAT_INFLATION_CONTRACTS
)

GASTAT_LABOR_CONTRACTS: tuple[CanonicalDatasetContract, ...] = (
    CanonicalDatasetContract(
        dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.QUARTERLY,
        primary_key=("observation_quarter", "labor_series_code"),
        dimensions=(
            _dimension(
                "observation_quarter",
                type=CanonicalFieldType.YEAR_QUARTER,
                description=(
                    "Observed labor-market quarter reported by the official release card."
                ),
            ),
            _dimension(
                "labor_series_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the supported total-unemployment series.",
            ),
            _dimension(
                "labor_series_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the supported labor series.",
            ),
            _dimension(
                "release_date",
                type=CanonicalFieldType.DATE,
                description="Official publication date of the labor-market release card.",
            ),
        ),
        measures=(
            _measure(
                "value_percent",
                type=CanonicalFieldType.DECIMAL,
                description=(
                    "Overall unemployment rate for the total population, expressed "
                    "as a percentage."
                ),
                unit="percent",
            ),
        ),
        structure_note=(
            "This first GASTAT labor contract extracts supported quarterly labor-market "
            "release cards from the official stats.gov.sa unemployment-filtered news "
            "surface. It does not yet claim full labor-market publication tables, "
            "Saudi-only series, sex or age cuts, participation rates, or the broader "
            "labor statistical database."
        ),
        intended_analytical_uses=(
            "Track the quarterly total-population unemployment rate with explicit "
            "release dates.",
            "Support local exact-match analysis over a narrow official labor-market "
            "headline series before broader labor-family expansion.",
        ),
    ),
)

GASTAT_LABOR_DATASET_IDS: tuple[str, ...] = tuple(
    contract.dataset_id for contract in GASTAT_LABOR_CONTRACTS
)

GASTAT_GDP_CONTRACTS: tuple[CanonicalDatasetContract, ...] = (
    CanonicalDatasetContract(
        dataset_id="stats-gov-sa-real-gdp-growth-quarterly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.QUARTERLY,
        primary_key=("observation_quarter", "gdp_series_code"),
        dimensions=(
            _dimension(
                "observation_quarter",
                type=CanonicalFieldType.YEAR_QUARTER,
                description="Observed GDP quarter reported by the official release card.",
            ),
            _dimension(
                "gdp_series_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the supported headline real GDP series.",
            ),
            _dimension(
                "gdp_series_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the supported GDP series.",
            ),
            _dimension(
                "release_date",
                type=CanonicalFieldType.DATE,
                description="Official publication date of the GDP release card.",
            ),
        ),
        measures=(
            _measure(
                "value_percent",
                type=CanonicalFieldType.DECIMAL,
                description=(
                    "Headline real GDP year-over-year growth rate, expressed as a "
                    "percentage."
                ),
                unit="percent",
            ),
        ),
        structure_note=(
            "This first GASTAT GDP contract extracts supported quarterly headline real GDP "
            "release cards from the official stats.gov.sa gdp-filtered news surface. "
            "It does not yet claim GDP levels, nominal GDP, expenditure or activity "
            "breakdowns, seasonally adjusted quarter-over-quarter growth, or the broader "
            "national-accounts statistical releases."
        ),
        intended_analytical_uses=(
            "Track the official quarterly headline real GDP growth path with explicit "
            "release dates.",
            "Support local exact-match analysis over one narrow GDP headline series "
            "before broader national-accounts expansion.",
        ),
    ),
)

GASTAT_GDP_DATASET_IDS: tuple[str, ...] = tuple(
    contract.dataset_id for contract in GASTAT_GDP_CONTRACTS
)

MOF_FISCAL_CONTRACTS: tuple[CanonicalDatasetContract, ...] = (
    CanonicalDatasetContract(
        dataset_id="mof-budget-balance-quarterly",
        schema_version="1.0.0",
        record_shape=CanonicalRecordShape.TIME_SERIES_OBSERVATION,
        temporal_granularity=TemporalGranularity.QUARTERLY,
        primary_key=("observation_quarter", "fiscal_series_code"),
        dimensions=(
            _dimension(
                "observation_quarter",
                type=CanonicalFieldType.YEAR_QUARTER,
                description=(
                    "Observed fiscal quarter reported by the official Ministry of Finance "
                    "quarterly budget performance materials."
                ),
            ),
            _dimension(
                "fiscal_series_code",
                type=CanonicalFieldType.STRING,
                description="Stable code for the supported top-line fiscal series.",
            ),
            _dimension(
                "fiscal_series_name",
                type=CanonicalFieldType.STRING,
                description="Human-readable label for the supported fiscal series.",
            ),
        ),
        measures=(
            _measure(
                "value_sar_bn",
                type=CanonicalFieldType.DECIMAL,
                description=(
                    "Quarterly headline budget balance normalized to Saudi Riyals, "
                    "billions."
                ),
                unit="SAR bn",
            ),
        ),
        structure_note=(
            "This first Ministry of Finance fiscal contract extracts the headline budget "
            "balance series from supported quarterly budget performance report PDFs "
            "linked from the official 2025 Ministry of Finance budget performance page. "
            "It does not yet claim total revenue, total expenditure, financing tables, "
            "public debt, or broader fiscal statement coverage."
        ),
        intended_analytical_uses=(
            "Track the quarterly top-line budget balance path on the official Ministry "
            "of Finance reporting surface.",
            "Support local exact-match analysis over one narrow fiscal headline series "
            "before broader public-finance expansion.",
        ),
    ),
)

MOF_FISCAL_DATASET_IDS: tuple[str, ...] = tuple(
    contract.dataset_id for contract in MOF_FISCAL_CONTRACTS
)

QUERY_PRIMARY_CANONICAL_DATASET_IDS: tuple[str, ...] = (
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS
    + GASTAT_INFLATION_DATASET_IDS
    + GASTAT_LABOR_DATASET_IDS
    + GASTAT_GDP_DATASET_IDS
    + MOF_FISCAL_DATASET_IDS
)

_CANONICAL_CONTRACTS_BY_DATASET_ID = {
    contract.dataset_id: contract
    for contract in (
        SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS
        + GASTAT_INFLATION_CONTRACTS
        + GASTAT_LABOR_CONTRACTS
        + GASTAT_GDP_CONTRACTS
        + MOF_FISCAL_CONTRACTS
    )
}


def get_canonical_dataset_contract(dataset_id: str) -> CanonicalDatasetContract:
    """Return the declared canonical contract for a supported dataset identifier."""

    try:
        return _CANONICAL_CONTRACTS_BY_DATASET_ID[dataset_id]
    except KeyError as exc:
        raise ValueError(
            f"No canonical contract is defined for dataset_id '{dataset_id}'"
        ) from exc
