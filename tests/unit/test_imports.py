"""Unit tests for scaffold imports."""

from saudi_open_data_mcp.config import load_config
from saudi_open_data_mcp.resources.catalog import (
    CatalogDatasetSummary,
    CatalogResource,
    CatalogSummary,
)


def test_load_config_defaults() -> None:
    config = load_config()

    assert config.app_name == "saudi-open-data-mcp"
    assert config.source.name == "sama"


def test_catalog_resource_types_import_cleanly() -> None:
    assert CatalogDatasetSummary.__name__ == "CatalogDatasetSummary"
    assert CatalogSummary.__name__ == "CatalogSummary"
    assert CatalogResource.__name__ == "CatalogResource"
