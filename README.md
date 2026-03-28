# saudi-open-data-mcp

`saudi-open-data-mcp` is a production-minded MCP server foundation for Saudi open data sources.

The project is not just an MCP wrapper around upstream websites. Its value is in the layers underneath MCP:

- source isolation through explicit connectors
- typed normalization contracts
- registry-backed dataset metadata and health metadata
- deterministic AI-facing resource and tool interfaces

Current implementation starts with SAMA only.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the architecture and [docs/ADR/ADR-001-start-with-sama.md](docs/ADR/ADR-001-start-with-sama.md) for the initial source decision.

## Current Architecture

The current codebase is organized around three layers.

### Data Access Layer

- `connectors/` defines the typed connector contract and the current SAMA connector.
- `storage/` provides raw snapshot persistence for connector payloads.
- `httpx` is the only HTTP client in the core path.

### Normalization & Contract Layer

- `normalization/` contains field mapping, validation, and the current normalization pipeline.
- `registry/` owns dataset descriptors, health metadata, SQLite persistence, and deterministic bootstrap data.
- The normalization path is typed and explicit, but it does not yet claim a mature canonical record model for all source shapes.

### AI-Facing Tool Layer

- `resources/` exposes read-only registry-backed resource views.
- `tools/` exposes deterministic MCP tool layers over the registry and preview path.
- `server.py` wires the current MCP surface into FastMCP.

## Current Implemented MCP Surface

The current exposed MCP surface is intentionally small:

- `resource://catalog`
- `dataset_metadata`
- `dataset_health`
- `search_datasets`
- `preview_dataset`

What each one does now:

- `resource://catalog`: read-only summary of the bootstrapped registry catalog
- `dataset_metadata`: exact lookup of registry-backed dataset metadata by `dataset_id`
- `dataset_health`: exact lookup of registry-backed health metadata by `dataset_id`
- `search_datasets`: deterministic registry-backed substring search over dataset metadata
- `preview_dataset`: fetches a raw SAMA payload through the current connector path and runs the normalization pipeline

## What Works Now

- Architecture documents and ADRs are in place and aligned with the codebase.
- The connector contract is typed and implemented for SAMA.
- Raw payload snapshots can be written and read locally.
- Registry models, SQLite repository behavior, and deterministic bootstrap data are implemented.
- Normalization field mapping, validation, and pipeline composition are implemented.
- The MCP server is wired with a real working surface for catalog, metadata, health, search, and preview.
- Preview uses the current connector and normalization path and can return either:
  - `record_derivable`
  - `limited`
  - `failed`
- Unit, integration, contract, and smoke tests are in the repo and passing.

## What Is Intentionally Not Implemented Yet

- no second source beyond SAMA
- no semantic search
- no LLM in the core path
- no connector-backed catalog discovery
- no live health scoring, uptime probing, or freshness math in the health tool
- no mature canonical record layer that turns every source payload shape into final business records
- no download or query MCP tools yet

One important limitation to keep explicit: `preview_dataset` uses the real connector and normalization path, but the normalization layer may still return `limited` results for HTML/text payloads and does not yet claim final normalized domain records.

## Local Setup

This repo uses a `src/` layout. Local test and CLI execution currently require `PYTHONPATH=src` unless you install the package into the environment first.

Install and sync with `uv`:

```bash
uv sync
```

Lint:

```bash
uv run ruff check .
```

Tests:

```bash
PYTHONPATH=src uv run pytest
```

## Local Run

The most practical local verification today is:

1. instantiate the FastMCP app
2. run the tests

Import / wiring check:

```bash
PYTHONPATH=src uv run python -m saudi_open_data_mcp.cli --check-imports
```

This currently verifies that the server can be constructed and that the wired MCP surface is importable. It does not claim a polished local hosting workflow yet.

## Testing

The repo includes four test layers:

- `tests/unit/`: typed contracts, tool behavior, repository behavior, connector behavior, and normalization behavior
- `tests/integration/`: small cross-module composition checks
- `tests/contracts/`: architectural boundary checks, including the rule that tool modules must not import connectors directly
- `tests/smoke/`: basic CLI/importability verification

## Repo Structure

The main code lives under `src/saudi_open_data_mcp/`.

- `connectors/`: source access contracts and SAMA connector
- `normalization/`: field mapping, validators, and pipeline
- `registry/`: typed metadata models, SQLite repository, and bootstrap
- `storage/`: snapshots and local storage helpers
- `resources/`: registry-backed MCP resources
- `tools/`: registry-backed MCP tools and preview tool
- `server.py`: FastMCP wiring
- `docs/`: architecture, ADR, roadmap, and dataset notes

## Roadmap / Next Steps

Near-term work should stay aligned with the current architecture:

- harden the remaining MCP surface only where real contracts already exist
- deepen the normalization layer so preview can produce richer canonical records when the source shape supports it
- improve packaging and local/deployed run ergonomics around the current FastMCP server
- continue reliability and observability hardening
- add a second source only after the SAMA path and registry contracts are stable
