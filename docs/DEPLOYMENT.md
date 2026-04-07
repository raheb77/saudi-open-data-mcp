# Deployment and Runtime Guide

Current deployment/runtime guide for the repository as it exists today.

This guide is intentionally narrow:

- no speculative cloud topology
- no compliance claims
- no hidden "future" runtime assumptions

## Runtime Topology

Current runtime surfaces:

- backend/core:
  - Python MCP service
  - local CLI over the same core
  - streamable HTTP at `/mcp`
  - readiness probe at `/readyz`
- dashboard:
  - separate Vite/React frontend package under `dashboard/`
  - prototype-only today
  - uses mock payloads shaped like current core responses
  - does not call `/mcp` or `/readyz` in the current branch

Concise topology:

```text
dashboard/ (optional prototype, mock-driven today)
        |
        |  no live dependency in the current branch
        v
Python MCP core
  - CLI
  - streamable HTTP `/mcp`
  - readiness `/readyz`
  - local registry/snapshot storage
```

## Required vs Optional

Required to run the governed core:

- Python environment via `uv sync`
- backend runtime config
- local storage paths for registry/snapshots
- `HTTP_AUTH_TOKEN` when using `run-http`

Optional:

- Docker/Compose for the containerized path
- Tier A refresh loop
- source base-URL overrides
- the dashboard package

Important current-state note:

- the backend/core is the real governed system
- the dashboard is still an optional Arabic RTL prototype package in this branch
- the dashboard's export actions are prototype-local because the dashboard is still mock-driven here
- the CLI export path is the governed institutional export path today

## Supported Deployment Posture Today

The current deployment posture is suitable for:

- internal evaluation
- operator-managed self-hosting
- sovereign-hosting-friendly environments that want the runtime and persistent
  state under direct institutional control

What that means in current-state terms:

- one backend process or container is the supported runtime shape
- persistent state stays in operator-controlled local paths or mounted volumes
- the backend can run without any required external managed control plane
- the only live external dependency is outbound access to the approved official
  source surfaces already implemented in the connectors
- CLI and stdio remain valid local operator/engineer access paths alongside
  `/mcp`

This is intentionally not positioned as:

- a managed SaaS platform
- a multi-node deployment model
- a public-internet reference architecture
- a zero-trust or enterprise service-mesh design

## Self-Hostable / Sovereign-Hosting-Friendly Meaning

The repository can reasonably be described that way today only in this narrow
sense:

- the governed core can run entirely in institution-controlled infrastructure
- persistent backend state can remain on institution-controlled storage
- auth configuration is operator-owned
- no hosted AI service, external vector store, or vendor-managed metadata plane
  is required for the core path

The repository does not claim:

- sovereign-cloud certification
- residency/legal compliance guarantees by itself
- secret-management, HSM, or KMS integration beyond whatever the deployment
  environment provides
- full offline operation when live source refresh is required

## Local Development

### Backend/Core

Install:

```bash
uv sync
```

Useful local commands:

```bash
python src/saudi_open_data_mcp/cli.py check-startup
python src/saudi_open_data_mcp/cli.py run-stdio
HTTP_AUTH_TOKEN=dev-internal-token python src/saudi_open_data_mcp/cli.py run-http --host 127.0.0.1 --port 8000
```

Useful local exports:

```bash
python src/saudi_open_data_mcp/cli.py export sama-pos-weekly --output result.json
python src/saudi_open_data_mcp/cli.py export sama-pos-weekly --format excel --output result.xml
python src/saudi_open_data_mcp/cli.py export sama-pos-weekly --format pdf --output result.pdf
```

### Dashboard

The dashboard package is optional and separate:

```bash
cd dashboard
npm install
npm run dev
```

Current dashboard reality:

- serves on `127.0.0.1:5173` by default
- Arabic-only and RTL
- mock-driven in the current branch
- useful for UI iteration and evaluator review
- not required to run the governed backend/core

## Containerized Run Path

Current container entrypoint:

```text
python src/saudi_open_data_mcp/cli.py run-http
```

Current Compose path:

```bash
docker compose up --build
```

What Compose provides today:

- builds the backend image
- runs the MCP HTTP service on `127.0.0.1:8000`
- mounts persistent runtime state at `/var/lib/saudi-open-data-mcp`
- checks `/readyz`
- requires `HTTP_AUTH_TOKEN`

The Compose file does not start the dashboard package.

## Environment Variables

Main backend/runtime variables:

- required for `run-http`:
  - `HTTP_AUTH_TOKEN`
- commonly configured:
  - `HTTP_AUTH_ROLE`
  - `HTTP_AUTH_CAPABILITIES`
  - `HTTP_HOST`
  - `HTTP_PORT`
  - `LOG_LEVEL`
  - `REGISTRY_PATH`
  - `SNAPSHOT_DIR`
  - `CACHE_DIR`
  - `TIER_A_REFRESH_ENABLED`
  - `TIER_A_REFRESH_INTERVAL_SECONDS`
- source-specific optional overrides:
  - `SAMA_BASE_URL`
  - `STATS_GOV_SA_BASE_URL`
  - `MOF_BASE_URL`
  - `DATA_GOV_SA_BASE_URL`

Role/capability rule:

- `HTTP_AUTH_ROLE` is the main operator-facing setting
- `HTTP_AUTH_CAPABILITIES` may be omitted or set explicitly to the matching bundle
- startup validates that role and capability bundle agree

## MCP HTTP Assumptions

`/mcp` today means:

- streamable HTTP MCP transport
- session-aware
- bearer-token protected
- intended for MCP-aware clients and inspectors
- not a generic browser JSON endpoint

`/readyz` today means:

- process is up
- config validation passed
- runtime storage preparation passed
- core FastMCP app wiring succeeded

`/readyz` does not mean:

- upstream sources are reachable
- all datasets are fresh
- every source connector is healthy

## Institutional Reader Summary

For an evaluator or institutional operator, the short current-state reading is:

- the backend/core is the deployable system
- the CLI is a thin local/operator façade over that same system
- exports are governed outputs of current query results
- the dashboard remains optional and prototype-only in this branch
- governance/security boundaries are real but intentionally narrow
- deployment expectations are clear, but broad enterprise platform claims are
  intentionally out of scope

## Frontend / Backend Expectations

Current expectations are intentionally simple:

- the backend/core can run alone
- the dashboard can run alone as a prototype
- there is no required full-stack orchestration layer in this branch
- there is no required reverse proxy between dashboard and backend today

If an evaluator wants to review the full repository:

1. run the backend/core locally or in Compose
2. optionally run the dashboard separately for UI review
3. treat CLI exports as the governed artifact path today

## Export Path Assumptions

Current governed export path:

- `python src/saudi_open_data_mcp/cli.py export ...`

Current supported governed formats:

- `json`
- Excel-compatible XML (`--format excel`)
- text-first PDF (`--format pdf`)

Current export semantics:

- exports are built from governed query results
- metadata stays explicit
- degraded/limited/failure states remain visible
- no report-writing or secondary interpretation layer is added

## Related Docs

- [README.md](../README.md)
- [docs/OPERATIONS.md](./OPERATIONS.md)
- [docs/PERSISTENCE.md](./PERSISTENCE.md)
- [docs/RUNBOOKS.md](./RUNBOOKS.md)
- [docs/GOVERNANCE.md](./GOVERNANCE.md)
- [dashboard/README.md](../dashboard/README.md)
