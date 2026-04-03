"""Integration tests for scaffold composition."""

from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)
from saudi_open_data_mcp.registry.bootstrap import bootstrap_registry
from saudi_open_data_mcp.registry.models import DatasetDescriptor
from saudi_open_data_mcp.registry.repository import RegistryRepository


def test_registry_and_normalization_scaffold_compose(tmp_path: Path) -> None:
    repository = RegistryRepository(tmp_path / "registry.sqlite")
    payload = RawPayload(
        source="sama",
        dataset_id="report.aspx?cid=55",
        content={
            "url": "https://www.sama.gov.sa/en-US/EconomicReports/Pages/report.aspx?cid=55",
            "status_code": 200,
            "content_type": "application/json",
            "body": {"rows": [{"period": "2026-01", "value": 1}]},
        },
    )

    bootstrapped_descriptors = bootstrap_registry(repository)
    result = NormalizationPipeline().normalize(payload)
    descriptors_by_id = {
        descriptor.dataset_id: descriptor for descriptor in bootstrapped_descriptors
    }

    assert bootstrapped_descriptors == repository.list_datasets()
    assert all(isinstance(item, DatasetDescriptor) for item in bootstrapped_descriptors)
    assert descriptors_by_id["sama-money-supply"].source_locator == "report.aspx?cid=55"
    assert descriptors_by_id["sama-deposits-core"].source_locator == "report.aspx?cid=55"
    assert descriptors_by_id["sama-pos-weekly"].source_locator == "/en-US/Indices/Pages/POS.aspx"
    assert (
        descriptors_by_id["sama-money-supply-weekly"].source_locator
        == "/en-US/Indices/Pages/WeeklyMoneySupply.aspx"
    )
    assert any(item.source == "data-gov-sa" for item in bootstrapped_descriptors)
    assert result.dataset_id == "report.aspx?cid=55"
    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 1
    assert result.records[0].dataset_id == "report.aspx?cid=55"
    assert result.records[0].source == "sama"
    assert result.records[0].record_index == 0
    assert result.records[0].fields == {"period": "2026-01", "value": 1}
    assert result.validation_result is not None
