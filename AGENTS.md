# Repository Guidance

## Scope

This repository is a production-minded foundation for `saudi-open-data-mcp`.

- MCP is the interface layer, not the core value
- the core value is source isolation, normalized dataset contracts, registry-backed metadata, health checks, and reliable AI-facing tool interfaces
- v0.1 starts with SAMA only

## Approved Structure

Keep changes inside the approved repository layout under `src/saudi_open_data_mcp/`:

- `connectors/`
- `normalization/`
- `registry/`
- `storage/`
- `health/`
- `tools/`
- `resources/`
- `observability/`
- `security/`
- `server.py`
- `config.py`
- `cli.py`

Do not add service packages, prompt packages, or alternate architectural areas.

## Boundary Rules

- `tools/` must not import raw connectors directly
- MCP-facing modules must not contain raw source access logic
- raw payload fetching must not happen inside `tools/`, `resources/`, or `server.py`
- normalization logic must stay inside `normalization/`
- registry metadata and health metadata must come from `registry/`
- all source access must go through connector abstractions
- all normalized outputs must use typed Pydantic models
- no LLM, semantic search, or query rewriting in the core path for v0.1
- use `httpx` only for HTTP access
- only approved official sources may be accessed

## Scaffolding Rules

- keep placeholders minimal, deterministic, and importable
- do not implement real SAMA fetching yet
- do not implement MCP business tools yet
- do not add fake examples, fake benchmarks, or half-implemented business logic

## Tooling

- Python 3.12
- FastMCP 2.x
- Ruff
- pytest
- pytest-asyncio
- respx
- DuckDB
- SQLite

## Local Checks

- `uv run ruff check .`
- `uv run pytest`
