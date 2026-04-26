# Repository Guidance

## Scope

This repository is a production-minded foundation for `saudi-open-data-mcp`.

- MCP is the interface layer, not the core value
- the core value is source isolation, normalized dataset contracts, registry-backed metadata, health checks, and reliable AI-facing tool interfaces
- the current baseline is the `0.3.x` internal/evaluator-controlled runtime
- current source scope includes SAMA, three narrow `stats.gov.sa` macro datasets, one Ministry of Finance fiscal dataset, and one narrow `data.gov.sa` pilot dataset
- the deployed runtime is container-first streamable HTTP, while stdio remains supported for local development and command-based host integration

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
- no LLM, semantic search, or query rewriting in the core path
- use `httpx` for new/default HTTP access paths; do not add new alternate HTTP clients. The existing narrow SAMA transport fallback is a compatibility exception, not a pattern to spread.
- only approved official sources may be accessed

## Implementation Rules

- keep placeholders minimal, deterministic, and importable when they are still necessary
- do not add fake examples, fake benchmarks, or half-implemented business logic
- keep `README.md`, `AGENTS.md`, `docs/CHANGELOG.md`, `TASKS.md`, and `server.json` aligned when changing supported surfaces or runtime posture

## Temporary v0.4.0 Hardening Context

For the v0.4.0 hardening cycle, all agents must also read `AGENTS_TASK_CONTEXT.md` before making changes.

If there is any conflict between the general repository guidance in this file and the temporary hardening-cycle rules in `AGENTS_TASK_CONTEXT.md`, the task prompt must explicitly state which section overrides which.

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
- `cd dashboard && npm run test` when touching the dashboard package
- `cd dashboard && npm run build` when touching the dashboard package
