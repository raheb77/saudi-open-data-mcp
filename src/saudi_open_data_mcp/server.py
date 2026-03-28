"""FastMCP server scaffold."""

from __future__ import annotations

from fastmcp import FastMCP

from .config import load_config
from .resources.catalog import register as register_catalog_resource
from .resources.policies import register as register_policies_resource
from .tools.download import register as register_download_tool
from .tools.health import register as register_health_tool
from .tools.metadata import register as register_metadata_tool
from .tools.preview import register as register_preview_tool
from .tools.query import register as register_query_tool
from .tools.search import register as register_search_tool


def _register_components(app: FastMCP) -> None:
    """Register placeholder resources and tools."""

    for register in (
        register_catalog_resource,
        register_policies_resource,
        register_search_tool,
        register_metadata_tool,
        register_preview_tool,
        register_query_tool,
        register_download_tool,
        register_health_tool,
    ):
        register(app)


def create_server() -> FastMCP:
    """Create the FastMCP application without business logic."""

    config = load_config()
    app = FastMCP(config.app_name)
    _register_components(app)
    return app
