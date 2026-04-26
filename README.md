# saudi-open-data-mcp

`saudi-open-data-mcp` is a production-minded MCP server for Saudi open data sources.

<!-- mcp-name: io.github.raheb77/saudi-open-data-mcp -->

The project is not just an MCP wrapper around upstream websites. Its value is in the layers underneath MCP:

- source isolation through explicit connectors
- typed normalization and canonical record contracts
- registry-backed dataset metadata and health metadata
- deterministic AI-facing resource and tool interfaces

Current implementation now includes curated official-source coverage across SAMA, `stats.gov.sa`, Ministry of Finance, and one narrow `data.gov.sa` pilot dataset. The current baseline is an internal, container-first MCP service with stdio still available for local development and command-based host integration.

The repository also includes an Arabic RTL dashboard package under `dashboard/`.
That package remains optional, but on `main` it is now a thin live consumer of
the governed backend over `/mcp` and `/startupz` with `/readyz` kept as a
startup-only compatibility alias, not a separate backend or required runtime
dependency for the core.

## License and Release Boundaries

- The code in this repository is licensed under the Apache License, Version 2.0.
- Model weights are not included in this repository.
- Model weights are not licensed under Apache-2.0 by default.
- Any future release of model weights will be governed separately.

See [ARCHITECTURE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/ARCHITECTURE.md) for the architecture, [ADR-001](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/ADR/ADR-001-start-with-sama.md) for the initial source decision, [GOVERNANCE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/GOVERNANCE.md) for the current core auth/audit/data-access model, [OPERATIONS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/OPERATIONS.md) for runtime and durability guidance, [DEPLOYMENT.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/DEPLOYMENT.md) for the current local/container/runtime topology, [RUNBOOKS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/RUNBOOKS.md) for concise failure/recovery handling, [PERSISTENCE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/PERSISTENCE.md) for current persistence and backup/restore boundaries, and [CHANGELOG.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/CHANGELOG.md) for current baseline change visibility and migration notes.

## What The System Does

- isolates approved official Saudi data sources behind explicit connectors
- normalizes a narrow supported dataset set into typed contracts
- keeps dataset metadata and health metadata in a registry-backed model
- exposes a small governed MCP surface for search, metadata, health, preview, query, download, and controlled materialization
- provides a thin local CLI over the same core
- produces governed institutional artifacts from query results through JSON, Excel-compatible XML, and text-first PDF export

## What The System Does Not Do

- it is not a generic BI suite or reporting platform
- it is not a broad national data lake or a crawler for arbitrary sites
- it does not add LLM rewriting, semantic search, or AI-generated narrative reporting in the core path
- it does not make `query_dataset` a live remote query surface
- it does not claim full public-internet deployment maturity or disaster-recovery automation
- the dashboard is not a separate backend, control plane, or canonical institutional export path

## Why It Is Trustworthy

- source boundaries are explicit and approved-source-only
- normalized outputs use typed contracts rather than free-form transport payloads
- registry-backed metadata keeps descriptors, health state, and caveats out of ad hoc request-time logic
- `query_dataset` and `download_dataset` stay local-only, while `preview_dataset` is the only hybrid path and exposes freshness/origin/degradation context explicitly
- HTTP auth, narrow RBAC, structured audit logs, and current-state governance docs are already in place
- deployment, runbook, and persistence expectations are documented explicitly rather than implied

## Current System Surfaces

| Surface | Purpose | Current state |
| --- | --- | --- |
| Backend/core | Governed MCP service over `/mcp` with `/startupz` | primary runtime |
| CLI | Thin operator/engineer façade over the same core | supported |
| Dashboard | Arabic RTL UI package under `dashboard/` | optional live consumer of `/mcp` and `/startupz` |
| Exports | Institutional artifacts over governed query results | CLI-governed path today |

## Deployment Fit Today

The current deployment fit is intentionally narrow and practical:

- internal or evaluator-controlled deployment
- self-hosted or sovereign-hosting-friendly environments that can run one Python service or container and manage local persistent storage
- operator-controlled auth token, role bundle, registry path, and snapshot path
- outbound access only to the approved official source surfaces already implemented in the connectors
- MCP-aware clients or inspectors on `/mcp`, plus CLI/stdio for local host integration

In current-state terms, "self-hostable" or "sovereign-hosting-friendly" means:

- there is no required vendor-managed control plane
- there is no required hosted search/index layer
- there is no required hosted database beyond the local SQLite registry
- persistent runtime state can remain on operator-controlled disk or volume storage

What this repository does not claim today:

- managed SaaS operation
- public-internet hardened service posture
- multi-node or highly available clustered runtime
- full enterprise IAM or per-user authorization
- compliance certification or sovereign-cloud accreditation

## Supported Scope

### Supported Sources

- SAMA
- `stats.gov.sa`
- Ministry of Finance
- one narrow `data.gov.sa` pilot path

### Supported Dataset Families

- SAMA high-frequency monetary and market datasets currently in the registry
- `stats.gov.sa` headline CPI monthly
- `stats.gov.sa` total unemployment rate quarterly
- `stats.gov.sa` real GDP growth quarterly
- Ministry of Finance headline budget balance quarterly

See [DATASETS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/DATASETS.md) for the current canonical dataset direction and current narrow-contract limits.

### Stable vs Evolving

Stable enough to evaluate and operate now:

- current MCP tool/resource surface
- current CLI over that surface
- current auth/audit/governance model
- current container/runtime/deployment story
- current governed CLI export path

Still intentionally evolving:

- breadth of source and dataset coverage
- richness of normalization for HTML/PDF-oriented sources
- automation depth around operations, backup, and restore
- dashboard operational resilience and cross-surface coherence as a live consumer of the governed core

## Start Here By Audience

- Evaluator:
  - start with this README, then [CHANGELOG.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/CHANGELOG.md), [ARCHITECTURE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/ARCHITECTURE.md), [GOVERNANCE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/GOVERNANCE.md), and [DEPLOYMENT.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/DEPLOYMENT.md)
- Operator:
  - start with [CHANGELOG.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/CHANGELOG.md), [DEPLOYMENT.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/DEPLOYMENT.md), [OPERATIONS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/OPERATIONS.md), [RUNBOOKS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/RUNBOOKS.md), and [PERSISTENCE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/PERSISTENCE.md)
- Engineer:
  - start with [CHANGELOG.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/CHANGELOG.md), [ARCHITECTURE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/ARCHITECTURE.md), [DATASETS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/DATASETS.md), [GOVERNANCE.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/GOVERNANCE.md), and [dashboard/README.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/dashboard/README.md) for the current UI/live-integration boundary

## Current Architecture

The current codebase is organized around three layers.

### Data Access Layer

- `connectors/` defines the typed connector contract and the current source-specific connectors for SAMA, `stats.gov.sa`, Ministry of Finance, and one narrow `data.gov.sa` pilot dataset.
- `storage/` provides raw snapshot persistence for connector payloads.
- `httpx` is the only HTTP client in the core path.

### Normalization & Contract Layer

- `normalization/` contains source-aware field mapping, source-aware validation, the normalization pipeline, and the current minimal canonical record layer.
- `registry/` owns dataset descriptors, health metadata, SQLite persistence, and deterministic bootstrap data.
- Canonical records are produced only for narrow supported JSON shapes:
  - top-level list of objects
  - object with a `rows` list of objects

### AI-Facing Tool Layer

- `resources/` exposes read-only registry-backed resource views.
- `tools/` exposes deterministic MCP tool layers over the registry, local snapshots, and preview/query paths.
- `server.py` wires the current MCP surface into FastMCP.

## Current Implemented MCP Surface

The current exposed MCP surface is intentionally small:

- `resource://catalog`
- `resource://observability`
- `resource://policies`
- `dataset_metadata`
- `dataset_health`
- `download_dataset`
- `materialize_hot_set`
- `query_dataset`
- `search_datasets`
- `preview_dataset`

What each one does now:

- `resource://catalog`: read-only summary of the bootstrapped registry catalog
- `resource://observability`: read-only grouped summary of current process-local counters, plus the raw counter snapshot for internal operators
- `resource://policies`: read-only summary of current data-facing semantics, including why `query_dataset` remains the primary analytical surface and `preview_dataset` remains hybrid
- `dataset_metadata`: exact lookup of registry-backed dataset metadata by `dataset_id`
- `dataset_health`: exact lookup of registry-backed health metadata by `dataset_id`, with local snapshot freshness evidence when available
- `download_dataset`: local-only raw snapshot availability lookup by `dataset_id`
- `materialize_hot_set`: explicit Wave 1 hot-set fetch and local snapshot persistence for the safe SAMA subset
- `query_dataset`: local-only exact-match query over canonical records derived from local snapshots
- `search_datasets`: deterministic registry-backed substring search over dataset metadata
- `preview_dataset`: exact preview by canonical `dataset_id`, using explicit local/live hybrid resolution metadata and the registry-owned `source_locator` internally for source access

Concise example of the current surface:

```text
resource://catalog
resource://observability
resource://policies
dataset_metadata({"dataset_id": "sama-money-supply"})
dataset_health({"dataset_id": "sama-money-supply"})
download_dataset({"dataset_id": "sama-money-supply"})
materialize_hot_set({"include_optional": false})
query_dataset({"dataset_id": "sama-money-supply", "filters": {"period": "2026-01"}, "limit": 5})
search_datasets({"query": "money"})
preview_dataset({"dataset_id": "sama-money-supply"})
```

## What Works Now

- Architecture documents and ADRs are in place and aligned with the codebase.
- The connector contract is typed and implemented for SAMA, `stats.gov.sa`, Ministry of Finance, and one narrow `data.gov.sa` pilot dataset.
- Raw payload snapshots can be written and read locally.
- Local snapshot freshness is evaluated deterministically from filesystem evidence only.
- Registry models, SQLite repository behavior, and deterministic bootstrap data are implemented.
- Registry descriptors now distinguish canonical `dataset_id` from source-specific `source_locator`.
- Normalization field mapping, validation, pipeline composition, and minimal canonical record extraction are implemented and dispatched by source.
- The MCP server is wired with a real working surface for catalog, metadata, health, download, materialize, query, search, and preview.
- Wave 1 hot-set materialization is implemented for the current safe SAMA subset.
- Tier A background refresh is available for the internal container runtime and remains opt-in.
- Preview resolves the connector by descriptor source and uses the current normalization dispatch path; it can return either:
  - `record_derivable`
  - `limited`
  - `failed`
- Preview now exposes explicit hybrid metadata including data origin, freshness status, and resolution outcome.
- Query and download are local-only and do not fetch remotely when a snapshot is missing.
- Internal HTTP serving has explicit bearer-token auth, capability checks, a canonical `/startupz` startup probe, and a `/readyz` compatibility alias with the same startup-only semantics.
- A curated `upstream-canary` command and scheduled workflow now exercise one live approved dataset path per current source family.
- Unit, integration, contract, and smoke tests are in the repo and passing.

## What Is Intentionally Not Implemented Yet

- no broad source-family coverage beyond the current narrow curated official datasets
- no semantic search
- no LLM in the core path
- no connector-backed catalog discovery
- no full-system health scoring or broad connector uptime monitoring beyond the curated upstream canary subset
- no remote fallback in `download_dataset` or `query_dataset`
- no mature canonical record layer that turns every source payload shape into final business records
- no generic canonical identity translation beyond the current registry-owned `dataset_id` plus single `source_locator`

One important limitation to keep explicit: `preview_dataset` uses the real connector and normalization path, but the normalization layer may still return `limited` results for HTML/text payloads and does not yet claim final normalized domain records.

Another important limitation: `query_dataset` only works on local snapshots that can be normalized into the current narrow canonical record shapes. Unsupported JSON shapes and HTML/text payloads remain explicit rather than queryable.

## Local Setup

This repo uses a `src/` layout. For the current phase, the source-tree CLI
remains the supported local development path; local commands do not require
manually setting `PYTHONPATH`.

Install and sync with `uv`:

```bash
uv sync
```

Then either activate the local environment:

```bash
source .venv/bin/activate
```

or call the tools from `.venv/bin/...` explicitly.

Lint:

```bash
ruff check .
```

Tests:

```bash
pytest
```

## Local Run

The supported local development activation path is the source-tree CLI:

```bash
python src/saudi_open_data_mcp/cli.py check-startup
python src/saudi_open_data_mcp/cli.py run-stdio
HTTP_AUTH_TOKEN=0123456789abcdef0123456789abcdef python src/saudi_open_data_mcp/cli.py run-http --host 127.0.0.1 --port 8000
```

The installed package also exposes the `saudi-open-data-mcp` console script:

```bash
saudi-open-data-mcp check-startup
saudi-open-data-mcp run-stdio
HTTP_AUTH_TOKEN=0123456789abcdef0123456789abcdef saudi-open-data-mcp run-http --host 127.0.0.1 --port 8000
```

The same source-tree CLI also provides a thin non-interactive local façade over
the current core operations. These commands emit structured JSON by default and
support `--output` for file writes. `--quiet` only applies when `--output` is
set. `--format` remains `json` for the read/health/config commands, while
`export` now also supports `excel` and `pdf` artifacts over the governed
`query_dataset` result:

```bash
python src/saudi_open_data_mcp/cli.py list
python src/saudi_open_data_mcp/cli.py query sama-pos-weekly --filter week_end_date=2024-01-13 --limit 5
python src/saudi_open_data_mcp/cli.py preview stats-gov-sa-cpi-headline-monthly
python src/saudi_open_data_mcp/cli.py download sama-money-supply
python src/saudi_open_data_mcp/cli.py export sama-money-supply-weekly --output money_supply.json
python src/saudi_open_data_mcp/cli.py export sama-money-supply-weekly --format excel --output money_supply.xml
python src/saudi_open_data_mcp/cli.py export sama-money-supply-weekly --format pdf --output money_supply.pdf
python src/saudi_open_data_mcp/cli.py health mof-budget-balance-quarterly
python src/saudi_open_data_mcp/cli.py refresh --dataset sama-money-supply
python src/saudi_open_data_mcp/cli.py refresh --include-optional
python src/saudi_open_data_mcp/cli.py config
```

The Excel artifact is an Excel-compatible XML workbook with visible metadata and
records worksheets. The PDF artifact is a metadata-first text PDF that keeps
status, origin, freshness, and limitations explicit instead of adding
decorative reporting layers.

Use the source-tree CLI or the local helper scripts for development and local
host integration. The packaged console script exists for installed-package
usage, but source-tree invocation remains the primary contributor workflow.

`run-stdio` remains the primary local host/operator path for Claude Desktop and
other command-based MCP hosts.

`run-http` starts the same app over streamable HTTP. Treat that path as
MCP-aware and session-aware only. It is suitable for MCP inspectors and MCP
clients, not generic browser probing. It now requires
`Authorization: Bearer <token>` using `HTTP_AUTH_TOKEN`, plus an explicit HTTP
role from `HTTP_AUTH_ROLE`. The configured role resolves to the allowed
capability bundle, and `HTTP_AUTH_CAPABILITIES` may be left implicit or set to
the same role bundle explicitly.

By default, local registry and snapshot state resolve under the repo's
`.local/` directory; set `REGISTRY_PATH` or `SNAPSHOT_DIR` to override them
explicitly. For reproducible host runs, prefer explicit `REGISTRY_PATH`,
`SNAPSHOT_DIR`, `SAMA_BASE_URL`, and `DATA_GOV_SA_BASE_URL` values.

Local state expectations:

- `download_dataset` reports only what exists in the local snapshot store. It does not fetch remotely.
- `query_dataset` only works when a local snapshot exists and the normalization layer can derive canonical records from that snapshot.
- If no local snapshot exists, `download_dataset` returns `artifact_missing` and `query_dataset` returns `snapshot_missing`.
- On a fresh checkout, those local-only states are the expected result until snapshots have been written under the configured snapshot directory.
- Public download and health outputs expose artifact presence plus freshness evidence, not local snapshot paths.
- When meaningful, core tool results expose consistent top-level metadata such as `data_origin`, `freshness_status`, `failure_stage`, and `degradation_reason` to make degraded and failed paths easier to interpret.

The helper script remains available for local HTTP development:

```bash
./scripts/run_local_http.sh
```

## Official Internal Container Serving

The official internal serving path for this phase is containerized streamable
HTTP.

Chosen serving mode:

- `run-http` over FastMCP streamable HTTP

Why this mode:

- it gives one long-running service shape for internal operators
- it fits container process supervision better than stdio
- it keeps the same MCP surface and tool semantics already exercised locally

The canonical container entrypoint is:

```text
saudi-open-data-mcp run-http
```

The image sets container-specific runtime defaults:

- `HTTP_HOST=0.0.0.0`
- `HTTP_PORT=8000`
- `HTTP_AUTH_TOKEN` must be provided by the operator
- `HTTP_AUTH_ROLE=operator`
- `HTTP_AUTH_CAPABILITIES=read,refresh,materialize`
- `TIER_A_REFRESH_ENABLED=false`
- `TIER_A_REFRESH_INTERVAL_SECONDS=3600`
- `REGISTRY_PATH=/var/lib/saudi-open-data-mcp/registry.sqlite`
- `SNAPSHOT_DIR=/var/lib/saudi-open-data-mcp/snapshots`
- `CACHE_DIR=/var/lib/saudi-open-data-mcp/cache`

Persistence expectations for that runtime:

- `REGISTRY_PATH` and `SNAPSHOT_DIR` should live on durable storage if you need state to survive replacement
- `CACHE_DIR` is recreatable scratch space
- logs, `resource://observability` counters, in-memory rate limits, and refresh loop state are process-local

Build and serve with Docker Compose:

```bash
docker compose up --build
```

The provided compose file publishes the service on `127.0.0.1:8000` on the
host, persists runtime state in a Docker-managed volume mounted at
`/var/lib/saudi-open-data-mcp`, enables `init: true`, and applies the same
`/startupz` startup-probe contract as the image. It also requires
`HTTP_AUTH_TOKEN` to be set in the operator environment before startup.

Internal observability remains intentionally simple:

- read `resource://observability` to inspect the current grouped in-process counters in one place
- inspect structured container logs for event-level detail such as `server.startup.*`, `preview.request.*`, `connector.request.*`, `materialize.*`, and `tier_a_refresh.*`
- treat the observability resource as a process-local operator aid, not as a health endpoint or external metrics API

For operator startup, shutdown, refresh, backup, and restore guidance, see [OPERATIONS.md](https://github.com/raheb77/saudi-open-data-mcp/blob/main/docs/OPERATIONS.md).

Direct container run example:

```bash
docker build -t saudi-open-data-mcp .
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -e HTTP_AUTH_TOKEN=0123456789abcdef0123456789abcdef \
  -v saudi-open-data-mcp-data:/var/lib/saudi-open-data-mcp \
  saudi-open-data-mcp
```

Container/runtime expectations:

- registry bootstrap still happens on startup
- Tier A background refresh is available but disabled by default
- when enabled, Tier A refresh runs immediately after service lifespan starts and then repeats on the configured interval
- refresh reuses the existing Tier A hot-set materialization path only; Tier B remains out of scope in this phase
- per-dataset refresh failures remain explicit in the materialization result and do not abort the whole refresh loop
- no external scheduler or distributed refresh system is added in this phase
- minimal bearer-token auth is enforced on the HTTP path only
- HTTP roles are enforced on the HTTP path only:
  - `viewer` for read/query/metadata/health/policies/observability
  - `operator` for `viewer` access plus `preview_dataset` and `materialize_hot_set`
  - `admin` as the highest current role with the same operational bundle as `operator`
- the current role bundles remain capability-based under the hood:
  - `read` for resources and local read/query/search tools
  - `refresh` for `preview_dataset`
  - `materialize` for `materialize_hot_set`
- no public-internet deployment hardening is claimed in this phase
- persistent storage is expected if you want registry and snapshot state to
  survive container replacement
- `HTTP_AUTH_TOKEN`, `HTTP_AUTH_ROLE`, `HTTP_AUTH_CAPABILITIES`, `TIER_A_REFRESH_ENABLED`, `TIER_A_REFRESH_INTERVAL_SECONDS`,
  `SAMA_BASE_URL`, `DATA_GOV_SA_BASE_URL`, and `LOG_LEVEL` are the main
  operator-facing overrides
  These base-URL overrides remain explicitly source-specific in the current
  config because the runtime still carries SAMA-specific and data.gov.sa-pilot
  assumptions.

Startup/readiness contract:

- the container's job is to start the MCP HTTP service and stay running
- `GET /startupz` is the canonical machine-friendly startup probe for this phase
- `GET /readyz` remains a compatibility alias for the same startup-only payload
- `/startupz` and `/readyz` mean only:
  - the process is running
  - config validation passed
  - runtime storage preparation passed
  - core FastMCP app wiring completed
- HTTP requests without a valid `Authorization: Bearer <token>` header are
  rejected with `401 Unauthorized`
- HTTP requests with a valid token but insufficient role/capability are rejected
  with `403 Forbidden`
- `/startupz` and `/readyz` do not claim:
  - upstream source reachability
  - dataset freshness
  - live connector health
  - full system health
- `/mcp` must be checked with an MCP-aware client if you want real session
  readiness validation
- naive `GET /` or `GET /mcp` probing can still return `404` or `406` and that
  is not, by itself, a serving failure

Curated live canary contract:

- `python src/saudi_open_data_mcp/cli.py upstream-canary` performs a live connector fetch plus normalization on:
  - `sama-exchange-rates-current`
  - `stats-gov-sa-cpi-headline-monthly`
  - `mof-budget-balance-quarterly`
  - `data-gov-sa-census-marital-status`
- a canary failure means one of those curated approved routes drifted in reachability, response shape, or normalization behavior enough to stop producing the expected record-derivable result
- the canary does not claim full catalog coverage, dataset freshness, or complete connector health

## MCP Host Registration

For local desktop MCP host registration, use stdio. That remains the supported
development/operator path for command-based hosts and is separate from the
official internal container serving path.

For stdio-based MCP hosts, use the source-tree CLI directly with absolute paths.
The repo's `server.json` is repository-level MCP metadata for this
internal/evaluator alpha. It intentionally declares no PyPI, npm, or MCP
registry package until a package is actually published.

Claude Desktop example:

```json
{
  "mcpServers": {
    "saudi-open-data-mcp": {
      "command": "/absolute/path/to/saudi-open-data-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/saudi-open-data-mcp/src/saudi_open_data_mcp/cli.py",
        "run-stdio"
      ],
      "cwd": "/absolute/path/to/saudi-open-data-mcp",
      "env": {
        "LOG_LEVEL": "ERROR",
        "SAMA_BASE_URL": "https://www.sama.gov.sa",
        "DATA_GOV_SA_BASE_URL": "https://open.data.gov.sa"
      }
    }
  }
}
```

`cwd` is optional here. The default registry and snapshot paths are now anchored to the repo rather than the process working directory, but keeping `cwd` set to the repo root can still make local config and path reasoning easier.

After installing the package, command-based hosts can also launch the console
script directly:

```json
{
  "mcpServers": {
    "saudi-open-data-mcp": {
      "command": "saudi-open-data-mcp",
      "args": ["run-stdio"],
      "env": {
        "LOG_LEVEL": "ERROR",
        "SAMA_BASE_URL": "https://www.sama.gov.sa",
        "DATA_GOV_SA_BASE_URL": "https://open.data.gov.sa"
      }
    }
  }
}
```

If you prefer a single command path, the repo also includes a stdio helper script:

```json
{
  "mcpServers": {
    "saudi-open-data-mcp": {
      "command": "/absolute/path/to/saudi-open-data-mcp/scripts/run_local_stdio.sh"
    }
  }
}
```

Current limitation to keep explicit: local host registration remains stdio
through the source-tree CLI. The official container serving path is HTTP, not a
desktop stdio-host replacement.

## HTTP Testing Notes

HTTP is the official internal container serving mode, but it is not a plain
REST surface. Use an MCP-aware client against `/mcp`.

For machine-friendly internal startup checks, use `GET /startupz`. `GET /readyz`
is kept as a compatibility alias with the same startup-only payload.

Start the server in one shell:

```bash
HTTP_AUTH_TOKEN=0123456789abcdef0123456789abcdef python src/saudi_open_data_mcp/cli.py run-http --host 127.0.0.1 --port 8000
```

Naive probing can look broken even when the server is healthy:

- `GET /` can return `404`
- `GET /mcp` without the expected MCP headers can return `406`
- `GET /startupz` should return `200` with a narrow startup-only payload

That behavior is expected for the current streamable HTTP setup. Browser or `curl` checks are useful only as a negative smoke test here, not as a real MCP session test.

Minimal MCP-aware test example:

```python
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main() -> None:
    async with Client(
        transport=StreamableHttpTransport(
            "http://127.0.0.1:8000/mcp",
            headers={"Authorization": "Bearer 0123456789abcdef0123456789abcdef"},
        )
    ) as client:
        result = await client.call_tool(
            "dataset_metadata",
            {"dataset_id": "sama-money-supply"},
        )
        print(result.structured_content)


asyncio.run(main())
```

## Testing

The repo includes four test layers:

- `tests/unit/`: typed contracts, tool behavior, repository behavior, connector behavior, and normalization behavior
- `tests/integration/`: small cross-module composition checks
- `tests/contracts/`: architectural boundary checks, including the rule that tool modules must not import connectors directly
- `tests/smoke/`: basic CLI/importability verification

## Repo Structure

The main code lives under `src/saudi_open_data_mcp/`.

- `connectors/`: source access contracts and SAMA connector
- `normalization/`: field mapping, validators, pipeline, and minimal canonical records
- `registry/`: typed metadata models, SQLite repository, and bootstrap
- `storage/`: snapshots and local freshness helpers
- `resources/`: registry-backed MCP resources
- `tools/`: registry-backed and local-only MCP tools, plus preview over the connector path
- `server.py`: FastMCP wiring
- `docs/`: architecture, ADR, roadmap, and dataset notes

## Roadmap / Next Steps

Near-term work should stay aligned with the current architecture:

- harden the current MCP surface and keep its descriptions, contracts, and identity handling consistent
- deepen the normalization layer only where the source shape safely supports richer canonical records
- improve packaging, local run ergonomics, and release presentation around the current FastMCP server
- continue reliability and observability hardening
- add a second source only after the SAMA path and registry contracts are stable
