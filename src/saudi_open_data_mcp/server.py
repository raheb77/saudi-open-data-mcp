from __future__ import annotations

import logging

from fastmcp import FastMCP

from .config import RuntimeConfig, load_config
from .connectors.resolver import build_default_connector_resolver
from .observability import configure_logging, get_logger, get_metrics, log_event
from .registry.bootstrap import bootstrap_registry
from .registry.repository import RegistryRepository
from .resources.catalog import CatalogResource
from .storage.snapshots import SnapshotStore
from .tools.download import DatasetDownloadTool
from .tools.health import DatasetHealthTool
from .tools.metadata import DatasetMetadataTool
from .tools.preview import DatasetPreviewTool
from .tools.query import DatasetQueryTool
from .tools.search import DatasetSearchTool

LOGGER = get_logger(__name__)


def create_server(config: RuntimeConfig | None = None) -> FastMCP:
    """Create the FastMCP application and wire the current MCP surface."""

    runtime_config = config or load_config()
    configure_logging(runtime_config.log_level)
    metrics = get_metrics()
    metrics.increment("server.startup.attempts")
    log_event(
        LOGGER,
        logging.INFO,
        "server.startup.begin",
        app_name=runtime_config.app_name,
    )

    repository = RegistryRepository(runtime_config.registry_path)
    bootstrapped_descriptors = bootstrap_registry(repository)
    snapshot_store = SnapshotStore(runtime_config.snapshot_dir)
    connector_resolver = build_default_connector_resolver(
        sama_base_url=runtime_config.source.base_url,
        data_gov_sa_base_url=runtime_config.source.data_gov_sa_base_url,
    )

    catalog_resource = CatalogResource(repository)
    health_tool = DatasetHealthTool(
        repository,
        snapshot_store,
    )
    download_tool = DatasetDownloadTool(repository, snapshot_store)
    metadata_tool = DatasetMetadataTool(repository)
    preview_tool = DatasetPreviewTool(
        repository,
        connector_resolver,
    )
    query_tool = DatasetQueryTool(repository, snapshot_store)
    search_tool = DatasetSearchTool(repository)
    metrics.increment("server.startup.success")
    log_event(
        LOGGER,
        logging.INFO,
        "server.startup.ready",
        app_name=runtime_config.app_name,
        dataset_count=len(bootstrapped_descriptors),
    )

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
        description=(
            "Exact registry-backed health lookup by dataset_id, "
            "with local snapshot freshness evidence when available."
        ),
    )
    def dataset_health(dataset_id: str) -> dict:
        return health_tool.get_dataset_health(dataset_id).model_dump(mode="json")

    @app.tool(
        name="download_dataset",
        description=(
            "Report local raw snapshot availability for an exact dataset_id. "
            "Local-only; no remote fetch."
        ),
    )
    def download_dataset(dataset_id: str) -> dict:
        return download_tool.get_dataset_download(dataset_id).model_dump(mode="json")

    @app.tool(
        name="query_dataset",
        description=(
            "Query local canonical records for an exact dataset_id "
            "using exact-match filters only. Local-only; no remote fetch."
        ),
    )
    def query_dataset(
        dataset_id: str,
        filters: dict[str, str | int | float | bool | None] | None = None,
        limit: int | None = None,
    ) -> dict:
        return query_tool.query_dataset(
            dataset_id,
            filters=filters,
            limit=limit,
        ).model_dump(mode="json")

    @app.tool(
        name="search_datasets",
        description=(
            "Search registry-backed dataset metadata using deterministic "
            "substring matching only."
        ),
    )
    def search_datasets(query: str) -> dict:
        return search_tool.search_datasets(query).model_dump(mode="json")

    @app.tool(
        name="preview_dataset",
        description=(
            "Fetch and preview a dataset for an exact registry dataset_id."
        ),
    )
    async def preview_dataset(dataset_id: str) -> dict:
        return (await preview_tool.preview_dataset(dataset_id)).model_dump(mode="json")

    return app
