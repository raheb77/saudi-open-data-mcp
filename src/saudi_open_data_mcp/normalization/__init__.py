"""Normalization contracts."""

from .arabic import normalize_arabic_text
from .contracts import (
    GASTAT_GDP_CONTRACTS,
    GASTAT_GDP_DATASET_IDS,
    GASTAT_INFLATION_CONTRACTS,
    GASTAT_INFLATION_DATASET_IDS,
    GASTAT_LABOR_CONTRACTS,
    GASTAT_LABOR_DATASET_IDS,
    QUERY_PRIMARY_CANONICAL_DATASET_IDS,
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS,
    SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS,
    CanonicalDatasetContract,
    CanonicalFieldDefinition,
    CanonicalFieldRole,
    CanonicalFieldType,
    CanonicalRecordShape,
    SchemaEvolutionPolicy,
    TemporalGranularity,
    get_canonical_dataset_contract,
)
from .field_mapping import get_field_mapping
from .pipeline import CanonicalRecord, NormalizationPipeline, NormalizationResult
from .validators import validate_dataset_id

__all__ = [
    "CanonicalDatasetContract",
    "CanonicalFieldDefinition",
    "CanonicalFieldRole",
    "CanonicalFieldType",
    "CanonicalRecord",
    "CanonicalRecordShape",
    "GASTAT_GDP_CONTRACTS",
    "GASTAT_GDP_DATASET_IDS",
    "GASTAT_INFLATION_CONTRACTS",
    "GASTAT_INFLATION_DATASET_IDS",
    "GASTAT_LABOR_CONTRACTS",
    "GASTAT_LABOR_DATASET_IDS",
    "NormalizationPipeline",
    "NormalizationResult",
    "QUERY_PRIMARY_CANONICAL_DATASET_IDS",
    "SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS",
    "SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS",
    "SchemaEvolutionPolicy",
    "TemporalGranularity",
    "get_field_mapping",
    "get_canonical_dataset_contract",
    "normalize_arabic_text",
    "validate_dataset_id",
]
