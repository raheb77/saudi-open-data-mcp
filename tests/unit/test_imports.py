"""Unit tests for scaffold imports."""

import subprocess
import sys
from pathlib import Path

import pytest

from saudi_open_data_mcp.config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    load_config,
    prepare_runtime_storage,
)
from saudi_open_data_mcp.resources.catalog import (
    CatalogDatasetSummary,
    CatalogResource,
    CatalogSummary,
)
from saudi_open_data_mcp.resources.policies import (
    DataSurfacePolicySummary,
    PoliciesResource,
    ToolPolicySummary,
)
from saudi_open_data_mcp.security.http_auth import HTTPAuthCapability


def test_load_config_defaults() -> None:
    config = load_config()

    assert config.app_name == "saudi-open-data-mcp"
    assert config.source.sama_base_url == "https://www.sama.gov.sa"
    assert config.source.stats_gov_sa_base_url == "https://www.stats.gov.sa"
    assert config.source.data_gov_sa_base_url == "https://open.data.gov.sa"
    assert config.transport.http_host == "127.0.0.1"
    assert config.transport.http_port == 8000
    assert config.transport.http_auth_token is None
    assert config.transport.http_auth_capabilities == frozenset(HTTPAuthCapability)
    assert config.tier_a_refresh.enabled is False
    assert config.tier_a_refresh.interval_seconds == 3600


def test_load_config_respects_data_gov_sa_base_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_GOV_SA_BASE_URL", "https://example.data.gov.sa")

    config = load_config()

    assert config.source.data_gov_sa_base_url == "https://example.data.gov.sa"


def test_load_config_respects_stats_gov_sa_base_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STATS_GOV_SA_BASE_URL", "https://example.stats.gov.sa")

    config = load_config()

    assert config.source.stats_gov_sa_base_url == "https://example.stats.gov.sa"


def test_load_config_respects_sama_base_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAMA_BASE_URL", "https://example.sama.gov.sa")

    config = load_config()

    assert config.source.sama_base_url == "https://example.sama.gov.sa"


def test_load_config_respects_http_transport_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("HTTP_PORT", "8080")
    monkeypatch.setenv("HTTP_AUTH_TOKEN", "internal-test-token")
    monkeypatch.setenv("HTTP_AUTH_CAPABILITIES", "read,materialize")
    monkeypatch.setenv("TIER_A_REFRESH_ENABLED", "true")
    monkeypatch.setenv("TIER_A_REFRESH_INTERVAL_SECONDS", "900")

    config = load_config()

    assert config.transport.http_host == "0.0.0.0"
    assert config.transport.http_port == 8080
    assert config.transport.http_auth_token is not None
    assert config.transport.http_auth_token.get_secret_value() == "internal-test-token"
    assert config.transport.http_auth_capabilities == frozenset(
        {
            HTTPAuthCapability.READ,
            HTTPAuthCapability.MATERIALIZE,
        }
    )
    assert config.tier_a_refresh.enabled is True
    assert config.tier_a_refresh.interval_seconds == 900


def test_load_config_rejects_invalid_http_auth_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_AUTH_CAPABILITIES", "read,admin")

    with pytest.raises(RuntimeConfigurationError, match="HTTP_AUTH_CAPABILITIES"):
        load_config()


def test_load_config_rejects_empty_http_auth_capability_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_AUTH_CAPABILITIES", "read,,refresh")

    with pytest.raises(RuntimeConfigurationError, match="HTTP_AUTH_CAPABILITIES"):
        load_config()


def test_load_config_rejects_invalid_boolean_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIER_A_REFRESH_ENABLED", "sometimes")

    with pytest.raises(RuntimeConfigurationError, match="TIER_A_REFRESH_ENABLED"):
        load_config()


@pytest.mark.parametrize(
    ("env_name", "value"),
    (
        ("HTTP_PORT", "not-an-int"),
        ("TIER_A_REFRESH_INTERVAL_SECONDS", "not-an-int"),
    ),
)
def test_load_config_rejects_invalid_integer_overrides(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    value: str,
) -> None:
    monkeypatch.setenv(env_name, value)

    with pytest.raises(RuntimeConfigurationError, match=env_name):
        load_config()


def test_load_config_rejects_out_of_range_http_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PORT", "70000")

    with pytest.raises(RuntimeConfigurationError, match="http_port"):
        load_config()


def test_load_config_rejects_blank_http_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_HOST", "   ")

    with pytest.raises(RuntimeConfigurationError, match="HTTP_HOST"):
        load_config()


def test_load_config_rejects_conflicting_storage_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared_path = tmp_path / "runtime-state"
    monkeypatch.setenv("REGISTRY_PATH", str(shared_path))
    monkeypatch.setenv("SNAPSHOT_DIR", str(shared_path))

    with pytest.raises(RuntimeConfigurationError, match="REGISTRY_PATH and SNAPSHOT_DIR"):
        load_config()


def test_prepare_runtime_storage_creates_expected_paths(tmp_path: Path) -> None:
    config = RuntimeConfig(
        registry_path=tmp_path / "runtime" / "registry.sqlite",
        snapshot_dir=tmp_path / "runtime" / "snapshots",
        cache_dir=tmp_path / "runtime" / "cache",
    )

    prepare_runtime_storage(config)

    assert config.registry_path.parent.is_dir()
    assert config.snapshot_dir.is_dir()
    assert config.cache_dir.is_dir()


def test_prepare_runtime_storage_rejects_file_snapshot_dir(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "runtime" / "snapshots"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("not a directory", encoding="utf-8")
    config = RuntimeConfig(
        registry_path=tmp_path / "runtime" / "registry.sqlite",
        snapshot_dir=snapshot_path,
        cache_dir=tmp_path / "runtime" / "cache",
    )

    with pytest.raises(RuntimeConfigurationError, match="SNAPSHOT_DIR"):
        prepare_runtime_storage(config)


def test_catalog_resource_types_import_cleanly() -> None:
    assert CatalogDatasetSummary.__name__ == "CatalogDatasetSummary"
    assert CatalogSummary.__name__ == "CatalogSummary"
    assert CatalogResource.__name__ == "CatalogResource"


def test_policies_resource_types_import_cleanly() -> None:
    assert ToolPolicySummary.__name__ == "ToolPolicySummary"
    assert DataSurfacePolicySummary.__name__ == "DataSurfacePolicySummary"
    assert PoliciesResource.__name__ == "PoliciesResource"


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
                "import saudi_open_data_mcp.connectors.stats_gov_sa; "
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
