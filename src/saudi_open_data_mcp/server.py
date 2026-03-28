from __future__ import annotations

from fastmcp import FastMCP

from .config import RuntimeConfig, load_config
from .registry.bootstrap import bootstrap_registry
from .registry.repository import RegistryRepository
from .resources.catalog import CatalogResource
from .tools.metadata import DatasetMetadataTool


def create_server(config: RuntimeConfig | None = None) -> FastMCP:
    """Create the FastMCP application and wire the current MCP surface."""

    runtime_config = config or load_config()
    repository = RegistryRepository(runtime_config.registry_path)
    bootstrap_registry(repository)

    catalog_resource = CatalogResource(repository)
    metadata_tool = DatasetMetadataTool(repository)

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

    return app