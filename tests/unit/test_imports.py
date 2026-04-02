"""Unit tests for scaffold imports."""

import subprocess
import sys
from pathlib import Path

import pytest

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
    assert config.source.base_url == "https://www.sama.gov.sa"
    assert config.source.data_gov_sa_base_url == "https://open.data.gov.sa"


def test_load_config_respects_data_gov_sa_base_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_GOV_SA_BASE_URL", "https://example.data.gov.sa")

    config = load_config()

    assert config.source.data_gov_sa_base_url == "https://example.data.gov.sa"


def test_catalog_resource_types_import_cleanly() -> None:
    assert CatalogDatasetSummary.__name__ == "CatalogDatasetSummary"
    assert CatalogSummary.__name__ == "CatalogSummary"
    assert CatalogResource.__name__ == "CatalogResource"


def test_storage_and_connector_modules_import_cleanly_in_fresh_interpreter() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(root / 'src')!r}); "
                "import saudi_open_data_mcp.storage.snapshots; "
                "import saudi_open_data_mcp.connectors.data_gov_sa; "
                "import saudi_open_data_mcp.connectors.sama; "
                "import saudi_open_data_mcp.connectors; "
                "print('ok')"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"
