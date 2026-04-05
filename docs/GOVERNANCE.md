# Core Governance Notes

Short governance and operations summary for the current internal MCP core.

This document is intentionally narrow. It describes what the system does today.
It does not claim full IAM, compliance controls, or public-internet maturity.

## Auth / Authz Model

- HTTP serving uses one internal bearer token from `HTTP_AUTH_TOKEN`.
- Auth is enforced on the HTTP path only. `run-stdio` remains a local host path
  and is not wrapped in the HTTP auth middleware.
- The HTTP role model is:
  - `viewer` -> `read`
  - `operator` -> `read`, `refresh`, `materialize`
  - `admin` -> same current bundle as `operator`
- Capabilities remain the actual enforcement mechanism at the HTTP boundary.
- `HTTP_AUTH_ROLE` selects the supported role bundle.
- `HTTP_AUTH_CAPABILITIES` may be set explicitly, but it must match the
  selected role bundle.
- Current capability meaning:
  - `read` covers resources plus local read/query/search tools
  - `refresh` covers `preview_dataset`
  - `materialize` covers `materialize_hot_set`
- There is no per-user identity, no session auth model, and no dataset-level
  permission matrix in the current core.

## Audit Model

- Important core operations emit structured `audit.*` logs.
- Current audit-covered operations include:
  - `query_dataset`
  - `preview_dataset`
  - `materialize_hot_set`
  - `download_dataset`
  - `dataset_metadata`
  - `dataset_health`
  - HTTP authorization denial and authorization-coverage-missing paths
- Audit is currently log-only.
- There is no dedicated audit database, retention service, export pipeline, or
  tamper-evident audit store yet.
- When request context is available on the HTTP path, audit events may include:
  - `actor_type`
  - `actor_role`
  - `actor_token_fingerprint`
  - `actor_capabilities`
  - `request_id`
  - `rpc_request_id`
  - `transport`
  - `path`
  - operation-specific fields such as `dataset_id`, `source`,
    `resolution_outcome`, `data_origin`, `freshness_status`,
    `failure_stage`, and `degradation_reason`

## Data Access Boundaries

- `query_dataset` is local-only.
  - It reads local snapshots and normalized canonical records only.
  - It does not perform live refresh.
- `download_dataset` is local-only.
  - It reports local artifact presence and local freshness evidence.
  - It does not fetch remotely.
- `preview_dataset` is the only current hybrid data path.
  - It may serve local data, refresh live, or serve stale-with-notice.
  - It fails closed when a live refresh is required and no usable fallback
    exists.
- `materialize_hot_set` is an explicit operational write path.
  - It fetches and persists the fixed Wave 1 hot set.
  - It is not a generic scheduler or a broad ingestion framework.
- `dataset_metadata` and `dataset_health` are registry-backed read surfaces.
  - `dataset_health` may include local freshness evidence.
  - It does not do live source probing.
- Live source access remains connector-scoped and approved-source-only.
  Current live source families in the repo are still explicit and source-specific:
  - SAMA
  - `stats.gov.sa` inflation, labor, and gdp news surfaces
  - existing `data.gov.sa` pilot paths already in the registry

## Retention / Deletion Basics

- Persistent local state:
  - `REGISTRY_PATH` SQLite registry
  - `SNAPSHOT_DIR` raw payload snapshots
- Recreatable local state:
  - `CACHE_DIR`
- Process-local only:
  - `resource://observability` counters
  - in-memory rate-limit state
  - Tier A refresh loop state
  - request-scoped audit context
- Not implemented yet:
  - audit-log retention policy
  - audit-log deletion workflow
  - automated backup/restore orchestration
  - snapshot-retention pruning policy
  - per-user deletion or access review workflow

Use [docs/OPERATIONS.md](docs/OPERATIONS.md) for startup, shutdown, readiness,
backup, and restore details.
