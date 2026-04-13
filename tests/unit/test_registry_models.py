"""Unit tests for registry metadata models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from saudi_open_data_mcp.registry.models import (
    DatasetCoverageStatus,
    DatasetDescriptor,
    DatasetHealthStatus,
    HealthMetadata,
    UpdateFrequency,
)


def test_dataset_descriptor_accepts_valid_metadata() -> None:
    descriptor = DatasetDescriptor(
        dataset_id="sama-balance-of-payments",
        source="sama",
        source_locator="report.aspx?cid=41",
        title="Balance of Payments",
        description="Official balance of payments dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.QUARTERLY,
        health_status=DatasetHealthStatus.HEALTHY,
        coverage_status=DatasetCoverageStatus.CATALOG_ONLY,
        caveats=("Publication timing may vary by release cycle.",),
        known_issues=("Historical backfills may change reported totals.",),
    )

    assert descriptor.dataset_id == "sama-balance-of-payments"
    assert descriptor.source_locator == "report.aspx?cid=41"
    assert descriptor.schema_version == "0.1.0"
    assert descriptor.update_frequency is UpdateFrequency.QUARTERLY
    assert descriptor.health_status is DatasetHealthStatus.HEALTHY
    assert descriptor.caveats == ("Publication timing may vary by release cycle.",)
    assert descriptor.known_issues == ("Historical backfills may change reported totals.",)


def test_dataset_descriptor_defaults_issue_collections_to_typed_empty_tuples() -> None:
    descriptor = DatasetDescriptor(
        dataset_id="sama-money-supply",
        source="sama",
        source_locator="report.aspx?cid=55",
        title="Money Supply",
        description="Official monetary aggregate dataset published by SAMA.",
        schema_version="0.1.0",
        update_frequency=UpdateFrequency.MONTHLY,
        health_status=DatasetHealthStatus.UNKNOWN,
        coverage_status=DatasetCoverageStatus.CATALOG_ONLY,
    )

    assert descriptor.caveats == ()
    assert descriptor.known_issues == ()
    assert isinstance(descriptor.caveats, tuple)
    assert isinstance(descriptor.known_issues, tuple)


def test_dataset_descriptor_rejects_invalid_enum_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DatasetDescriptor(
            dataset_id="sama-interest-rates",
            source="sama",
            source_locator="report.aspx?cid=52",
            title="Interest Rates",
            description="Official interest rate series published by SAMA.",
            schema_version="0.1.0",
            update_frequency="hourly",
            health_status="green",
            coverage_status="ready",
        )

    assert "update_frequency" in str(exc_info.value)
    assert "health_status" in str(exc_info.value)
    assert "coverage_status" in str(exc_info.value)


def test_dataset_descriptor_requires_declared_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DatasetDescriptor(
            dataset_id="sama-foreign-assets",
            source="sama",
            title="Foreign Assets",
            schema_version="0.1.0",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.HEALTHY,
            coverage_status=DatasetCoverageStatus.CATALOG_ONLY,
        )

    assert "source_locator" in str(exc_info.value)
    assert "description" in str(exc_info.value)


def test_dataset_descriptor_rejects_invalid_schema_version() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DatasetDescriptor(
            dataset_id="sama-external-debt",
            source="sama",
            source_locator="report.aspx?cid=77",
            title="External Debt",
            description="Official external debt dataset published by SAMA.",
            schema_version="latest",
            update_frequency=UpdateFrequency.QUARTERLY,
            health_status=DatasetHealthStatus.HEALTHY,
            coverage_status=DatasetCoverageStatus.CATALOG_ONLY,
        )

    assert "schema_version" in str(exc_info.value)


def test_dataset_descriptor_rejects_invalid_note_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DatasetDescriptor(
            dataset_id="sama-reserves",
            source="sama",
            source_locator="report.aspx?cid=88",
            title="Reserves",
            description="Official reserve assets dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.DEGRADED,
            coverage_status=DatasetCoverageStatus.LIMITED,
            caveats=("   ",),
        )

    assert "caveats" in str(exc_info.value)


def test_dataset_descriptor_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DatasetDescriptor(
            dataset_id="sama-credit",
            source="sama",
            source_locator="report.aspx?cid=99",
            title="Credit",
            description="Official credit dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.HEALTHY,
            coverage_status=DatasetCoverageStatus.QUERYABLE,
            unexpected_field="not allowed",
        )


def test_health_metadata_uses_operational_enum() -> None:
    metadata = HealthMetadata(
        dataset_id="sama-credit",
        health_status=DatasetHealthStatus.DEGRADED,
    )

    assert metadata.health_status is DatasetHealthStatus.DEGRADED


def test_dataset_descriptor_rejects_unavailable_coverage_status() -> None:
    with pytest.raises(ValidationError, match="coverage_status"):
        DatasetDescriptor(
            dataset_id="sama-foreign-assets",
            source="sama",
            source_locator="report.aspx?cid=41",
            title="Foreign Assets",
            description="Official foreign assets dataset published by SAMA.",
            schema_version="0.1.0",
            update_frequency=UpdateFrequency.MONTHLY,
            health_status=DatasetHealthStatus.UNKNOWN,
            coverage_status=DatasetCoverageStatus.UNAVAILABLE,
        )
