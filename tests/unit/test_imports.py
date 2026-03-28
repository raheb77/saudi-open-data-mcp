"""Unit tests for scaffold imports."""

from saudi_open_data_mcp.config import load_config
from saudi_open_data_mcp.server import create_server


def test_load_config_defaults() -> None:
    config = load_config()

    assert config.app_name == "saudi-open-data-mcp"
    assert config.source.name == "sama"


def test_create_server_returns_fastmcp_app() -> None:
    app = create_server()

    assert app.name == "saudi-open-data-mcp"
