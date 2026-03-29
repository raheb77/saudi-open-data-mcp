# saudi-open-data-mcp

`saudi-open-data-mcp` is a production-minded MCP server for Saudi open data sources.

The project is not just an MCP wrapper around upstream websites. Its value is in the layers underneath MCP:

- source isolation through explicit connectors
- typed normalization and canonical record contracts
- registry-backed dataset metadata and health metadata
- deterministic AI-facing resource and tool interfaces

Current implementation starts with SAMA only and already exposes a small working MCP surface.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the architecture and [docs/ADR/ADR-001-start-with-sama.md](docs/ADR/ADR-001-start-with-sama.md) for the initial source decision.

## Current Architecture

The current codebase is organized around three layers.

### Data Access Layer

- `connectors/` defines the typed connector contract and the current SAMA connector.
- `storage/` provides raw snapshot persistence for connector payloads.
- `httpx` is the only HTTP client in the core path.

### Normalization & Contract Layer

- `normalization/` contains field mapping, validation, the normalization pipeline, and the current minimal canonical record layer.
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
- `dataset_metadata`
- `dataset_health`
- `download_dataset`
- `query_dataset`
- `search_datasets`
- `preview_dataset`

What each one does now:

- `resource://catalog`: read-only summary of the bootstrapped registry catalog
- `dataset_metadata`: exact lookup of registry-backed dataset metadata by `dataset_id`
- `dataset_health`: exact lookup of registry-backed health metadata by `dataset_id`, with local snapshot freshness evidence when available
- `download_dataset`: local-only raw snapshot availability lookup by `dataset_id`
- `query_dataset`: local-only exact-match query over canonical records derived from local snapshots
- `search_datasets`: deterministic registry-backed substring search over dataset metadata
- `preview_dataset`: fetches a raw SAMA payload through the current connector path and runs the normalization pipeline using the current source-specific locator input

Concise example of the current surface:

```text
resource://catalog
dataset_metadata({"dataset_id": "sama-money-supply"})
dataset_health({"dataset_id": "sama-money-supply"})
download_dataset({"dataset_id": "sama-money-supply"})
query_dataset({"dataset_id": "sama-money-supply", "filters": {"period": "2026-01"}, "limit": 5})
search_datasets({"query": "money"})
preview_dataset({"dataset_id": "report.aspx?cid=55"})
```

## What Works Now

- Architecture documents and ADRs are in place and aligned with the codebase.
- The connector contract is typed and implemented for SAMA.
- Raw payload snapshots can be written and read locally.
- Local snapshot freshness is evaluated deterministically from filesystem evidence only.
- Registry models, SQLite repository behavior, and deterministic bootstrap data are implemented.
- Registry descriptors now distinguish canonical `dataset_id` from source-specific `source_locator`.
- Normalization field mapping, validation, pipeline composition, and minimal canonical record extraction are implemented.
- The MCP server is wired with a real working surface for catalog, metadata, health, download, query, search, and preview.
- Preview uses the current connector and normalization path and can return either:
  - `record_derivable`
  - `limited`
  - `failed`
- Query and download are local-only and do not fetch remotely when a snapshot is missing.
- Unit, integration, contract, and smoke tests are in the repo and passing.

## What Is Intentionally Not Implemented Yet

- no second source beyond SAMA
- no semantic search
- no LLM in the core path
- no connector-backed catalog discovery
- no live health scoring, uptime probing, or connector health checks
- no remote fallback in `download_dataset` or `query_dataset`
- no mature canonical record layer that turns every source payload shape into final business records
- no generic canonical identity translation beyond the current registry-owned `dataset_id` plus single `source_locator`

One important limitation to keep explicit: `preview_dataset` uses the real connector and normalization path, but the normalization layer may still return `limited` results for HTML/text payloads and does not yet claim final normalized domain records.

Another important limitation: `query_dataset` only works on local snapshots that can be normalized into the current narrow canonical record shapes. Unsupported JSON shapes and HTML/text payloads remain explicit rather than queryable.

## Local Setup

This repo uses a `src/` layout, but local test and CLI workflows no longer require manually setting `PYTHONPATH`.

Install and sync with `uv`:

```bash
uv sync
```

Then either activate the local environment:

```bash
source .venv/bin/activate
```

or call the tools from `.venv/bin/...` explicitly. That is the least ambiguous local path for the current project layout.

Lint:

```bash
ruff check .
```

Tests:

```bash
pytest
```

## Local Run

The current local entrypoint is the project CLI under `src/saudi_open_data_mcp/cli.py`.

Import / wiring check:

```bash
python src/saudi_open_data_mcp/cli.py --check-imports
```

This verifies that the FastMCP app can be constructed and that the currently wired MCP surface is importable.

Local HTTP run:

```bash
./scripts/run_local_http.sh
```

Optional host and port overrides:

```bash
./scripts/run_local_http.sh --host 127.0.0.1 --port 8080
```

The HTTP helper starts the current FastMCP app over streamable HTTP using configured defaults. It is intended for local development and inspection, not as a polished deployment entrypoint.

Local stdio run for MCP hosts:

```bash
python src/saudi_open_data_mcp/cli.py run-stdio
```

This starts the same FastMCP app over stdio. It is the current direct local activation path for hosts that expect a stdio MCP server command.

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
