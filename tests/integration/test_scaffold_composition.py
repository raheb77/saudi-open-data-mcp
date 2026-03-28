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
            "body": {"rows": []},
        },
    )

    bootstrapped_descriptors = bootstrap_registry(repository)
    result = NormalizationPipeline().normalize(payload)

    assert bootstrapped_descriptors == repository.list_datasets()
    assert all(isinstance(item, DatasetDescriptor) for item in bootstrapped_descriptors)
    assert result.dataset_id == "report.aspx?cid=55"
    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert result.records == ()
    assert result.validation_result is not None
