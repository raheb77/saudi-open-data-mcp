from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastmcp import FastMCP

from .config import RuntimeConfig, load_config, prepare_runtime_storage
from .connectors.resolver import build_default_connector_resolver
from .observability import configure_logging, get_logger, get_metrics, log_event
from .registry.bootstrap import bootstrap_registry_with_summary
from .registry.repository import RegistryRepository
from .resources.catalog import CatalogResource
from .resources.observability import ObservabilityResource
from .resources.policies import PoliciesResource
from .storage.snapshots import SnapshotStore
from .tools.download import DatasetDownloadTool
from .tools.health import DatasetHealthTool
from .tools.input_schema import (
    DatasetIdInput,
    IncludeOptionalInput,
    QueryFiltersInput,
    QueryLimitInput,
    SearchQueryInput,
)
from .tools.materialize import HotSetMaterializationTool, TierABackgroundRefreshService
from .tools.metadata import DatasetMetadataTool
from .tools.preview import DatasetPreviewTool
from .tools.query import DatasetQueryTool
from .tools.search import DatasetSearchTool

LOGGER = get_logger(__name__)


def _build_server_lifespan(
    *,
    refresh_service: TierABackgroundRefreshService | None,
    runtime_config: RuntimeConfig,
):
    @asynccontextmanager
    async def lifespan(_server):
        refresh_task: asyncio.Task[None] | None = None
        if refresh_service is not None:
            log_event(
                LOGGER,
                logging.INFO,
                "tier_a_refresh.loop.enabled",
                interval_seconds=runtime_config.tier_a_refresh.interval_seconds,
            )
            refresh_task = asyncio.create_task(refresh_service.run_forever())

        try:
            yield {}
        finally:
            if refresh_task is not None:
                refresh_task.cancel()
                with suppress(asyncio.CancelledError):
                    await refresh_task

    return lifespan


def create_server(config: RuntimeConfig | None = None) -> FastMCP:
    """Create the FastMCP application and wire the current MCP surface."""

    metrics = get_metrics()
    metrics.increment("server.startup.attempts")
    runtime_config: RuntimeConfig | None = None

    try:
        runtime_config = config or load_config()
        configure_logging(runtime_config.log_level)
        log_event(
            LOGGER,
            logging.INFO,
            "server.startup.begin",
            app_name=runtime_config.app_name,
        )
        prepare_runtime_storage(runtime_config)

        repository = RegistryRepository(runtime_config.registry_path)
        bootstrap_summary = bootstrap_registry_with_summary(repository)
        bootstrapped_descriptors = list(bootstrap_summary.descriptors)
        snapshot_store = SnapshotStore(runtime_config.snapshot_dir)
        connector_resolver = build_default_connector_resolver(
            source_config=runtime_config.source,
        )

        catalog_resource = CatalogResource(repository)
        observability_resource = ObservabilityResource()
        policies_resource = PoliciesResource()
        health_tool = DatasetHealthTool(
            repository,
            snapshot_store,
        )
        download_tool = DatasetDownloadTool(repository, snapshot_store)
        metadata_tool = DatasetMetadataTool(repository)
        materialize_tool = HotSetMaterializationTool(
            repository,
            connector_resolver,
            snapshot_store,
        )
        refresh_service = (
            TierABackgroundRefreshService(
                materialize_tool,
                interval_seconds=runtime_config.tier_a_refresh.interval_seconds,
            )
            if runtime_config.tier_a_refresh.enabled
            else None
        )
        preview_tool = DatasetPreviewTool(
            repository,
            connector_resolver,
            snapshot_store=snapshot_store,
        )
        query_tool = DatasetQueryTool(repository, snapshot_store)
        search_tool = DatasetSearchTool(repository)

        app = FastMCP(
            runtime_config.app_name,
            lifespan=_build_server_lifespan(
                refresh_service=refresh_service,
                runtime_config=runtime_config,
            ),
        )

        @app.resource(
            "resource://catalog",
            name="catalog",
            description="Registry-backed summary of the initial seeded dataset catalog.",
        )
        def catalog() -> str:
            return catalog_resource.read().model_dump_json(indent=2)

        @app.resource(
            "resource://observability",
            name="observability",
            description=(
                "Read-only grouped process-local observability counters for internal "
                "operators. This is not a health claim or an external metrics API."
            ),
        )
        def observability() -> str:
            return observability_resource.read().model_dump_json(indent=2)

        @app.resource(
            "resource://policies",
            name="policies",
            description=(
                "Read-only summary of current data-facing MCP semantics, including "
                "the decision to keep query local/deterministic and preview hybrid."
            ),
        )
        def policies() -> str:
            return policies_resource.read().model_dump_json(indent=2)

        @app.tool(
            name="dataset_metadata",
            description="Exact registry metadata lookup by dataset_id.",
        )
        def dataset_metadata(dataset_id: DatasetIdInput) -> dict:
            return metadata_tool.get_dataset_metadata(dataset_id).model_dump(mode="json")

        @app.tool(
            name="dataset_health",
            description=(
                "Exact registry-backed health lookup by dataset_id, "
                "with local snapshot freshness evidence when available."
            ),
        )
        def dataset_health(dataset_id: DatasetIdInput) -> dict:
            return health_tool.get_dataset_health(dataset_id).model_dump(mode="json")

        @app.tool(
            name="download_dataset",
            description=(
                "Report local raw snapshot availability for an exact dataset_id. "
                "Local-only; no remote fetch."
            ),
        )
        def download_dataset(dataset_id: DatasetIdInput) -> dict:
            return download_tool.get_dataset_download(dataset_id).model_dump(mode="json")

        @app.tool(
            name="materialize_hot_set",
            description=(
                "Fetch and persist the fixed Wave 1 SAMA hot-set into local snapshots. "
                "Tier B remains opt-in via include_optional."
            ),
        )
        async def materialize_hot_set(
            include_optional: IncludeOptionalInput = False,
        ) -> dict:
            return (
                await materialize_tool.materialize_hot_set(include_optional=include_optional)
            ).model_dump(mode="json")

        @app.tool(
            name="query_dataset",
            description=(
                "Query local canonical records for an exact dataset_id "
                "using exact-match filters only. Local-only; no remote fetch."
            ),
        )
        def query_dataset(
            dataset_id: DatasetIdInput,
            filters: QueryFiltersInput = None,
            limit: QueryLimitInput = None,
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
        def search_datasets(query: SearchQueryInput) -> dict:
            return search_tool.search_datasets(query).model_dump(mode="json")

        @app.tool(
            name="preview_dataset",
            description=(
                "Fetch and preview a dataset for an exact registry dataset_id."
            ),
        )
        async def preview_dataset(dataset_id: DatasetIdInput) -> dict:
            return (await preview_tool.preview_dataset(dataset_id)).model_dump(mode="json")

    except Exception as exc:
        metrics.increment("server.startup.failures")
        log_event(
            LOGGER,
            logging.ERROR,
            "server.startup.failed",
            app_name=runtime_config.app_name if runtime_config is not None else None,
            error_type=type(exc).__name__,
            message=str(exc),
        )
        raise

    metrics.increment("server.startup.ready")
    log_event(
        LOGGER,
        logging.INFO,
        "server.startup.ready",
        app_name=runtime_config.app_name,
        dataset_count=len(bootstrapped_descriptors),
        registry_seed_inserted_count=len(bootstrap_summary.inserted_dataset_ids),
        registry_seed_updated_count=len(bootstrap_summary.updated_dataset_ids),
        registry_seed_unchanged_count=len(bootstrap_summary.unchanged_dataset_ids),
    )
    return app
