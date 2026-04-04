"""Normalization contracts."""

from .arabic import normalize_arabic_text
from .contracts import (
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
    "NormalizationPipeline",
    "NormalizationResult",
    "SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_CONTRACTS",
    "SAMA_HIGH_FREQUENCY_ECONOMIC_CORE_DATASET_IDS",
    "SchemaEvolutionPolicy",
    "TemporalGranularity",
    "get_field_mapping",
    "get_canonical_dataset_contract",
    "normalize_arabic_text",
    "validate_dataset_id",
]
