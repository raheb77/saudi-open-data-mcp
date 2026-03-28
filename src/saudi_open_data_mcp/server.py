from __future__ import annotations

from fastmcp import FastMCP

from .config import RuntimeConfig, load_config
from .connectors.sama import SAMAConnector
from .registry.bootstrap import bootstrap_registry
from .registry.repository import RegistryRepository
from .resources.catalog import CatalogResource
from .tools.health import DatasetHealthTool
from .tools.metadata import DatasetMetadataTool
from .tools.preview import DatasetPreviewTool
from .tools.search import DatasetSearchTool


def create_server(config: RuntimeConfig | None = None) -> FastMCP:
    """Create the FastMCP application and wire the current MCP surface."""

    runtime_config = config or load_config()
    repository = RegistryRepository(runtime_config.registry_path)
    bootstrap_registry(repository)

    catalog_resource = CatalogResource(repository)
    health_tool = DatasetHealthTool(repository)
    metadata_tool = DatasetMetadataTool(repository)
    preview_tool = DatasetPreviewTool(
        SAMAConnector(base_url=runtime_config.source.base_url).fetch_dataset_payload
    )
    search_tool = DatasetSearchTool(repository)

    app = FastMCP(runtime_config.app_name)

    @app.resource(
        "resource://catalog",
        name="catalog",
        description="Registry-backed summary of the initial seeded dataset catalog.",
    )
    def catalog() -> str:
        return catalog_resource.read().model_dump_json(indent=2)

    @app.tool(
        name="dataset_metadata",
        description="Exact registry metadata lookup by dataset_id.",
    )
    def dataset_metadata(dataset_id: str) -> dict:
        return metadata_tool.get_dataset_metadata(dataset_id).model_dump(mode="json")

    @app.tool(
        name="dataset_health",
        description="Exact registry-backed health lookup by dataset_id.",
    )
    def dataset_health(dataset_id: str) -> dict:
        return health_tool.get_dataset_health(dataset_id).model_dump(mode="json")

    @app.tool(
        name="search_datasets",
        description="Search registry-backed datasets using deterministic substring matching.",
    )
    def search_datasets(query: str) -> dict:
        return search_tool.search_datasets(query).model_dump(mode="json")

    @app.tool(
        name="preview_dataset",
        description="Fetch and preview a dataset by exact dataset identifier or locator.",
    )
    async def preview_dataset(dataset_id: str) -> dict:
        return (await preview_tool.preview_dataset(dataset_id)).model_dump(mode="json")

    return app
