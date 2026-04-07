# Current Baseline Changelog and Migration Notes

Current-state change visibility for the repository as it exists today.

This is intentionally not a full release-history log. It is a narrow operator /
evaluator / engineer guide to the changes that materially affect:

- what the system does today
- what surfaces are trustworthy today
- what remains intentionally limited

## Current Baseline Snapshot

The current baseline now includes:

- a governed MCP core with explicit source isolation, registry-backed metadata,
  local query semantics, hybrid preview semantics, and structured audit logging
- narrow multi-source dataset coverage across SAMA, `stats.gov.sa`, Ministry of
  Finance, and one narrow `data.gov.sa` pilot path
- a thin local CLI over the same governed core
- institutional artifact export from governed query results through JSON,
  Excel-compatible XML, and text-first PDF
- an Arabic RTL dashboard package that remains optional and mock-driven in this
  branch
- deployment, runbook, persistence, and governance documentation aligned to the
  current runtime reality

## Meaningful Changes Reflected In The Current Baseline

### Governance / Trust Hardening

- HTTP auth moved to an explicit bearer-token plus role/capability model
- current roles are `viewer`, `operator`, and `admin`
- structured `audit.*` logging was added for important governed operations
- result metadata became more explicit around:
  - `data_origin`
  - `freshness_status`
  - `failure_stage`
  - `degradation_reason`

### Source / Data Expansion

- the system expanded beyond the initial SAMA-focused base
- current supported narrow additions are:
  - `stats.gov.sa` headline CPI monthly
  - `stats.gov.sa` total unemployment rate quarterly
  - `stats.gov.sa` real GDP growth quarterly
  - Ministry of Finance headline budget balance quarterly

### Local Usage Surfaces

- a thin CLI was added over the same core tool surface
- the CLI is now the governed institutional export path
- the dashboard package exists for UI review and iteration, but it remains a
  mock-driven prototype in this branch

### Operational / Adoption Hardening

- deployment/runtime assumptions are now documented explicitly
- operational runbooks now exist for realistic failure paths
- persistence, backup, restore, and operator responsibility boundaries are now
  documented explicitly

## Current Stable vs Evolving Reading

Stable enough to trust operationally now:

- current MCP tool/resource semantics
- current CLI over those same semantics
- current auth/authz/audit posture
- current governed CLI export path
- current runtime/deployment/runbook/persistence guidance

Still intentionally evolving:

- breadth of source and dataset coverage
- normalization richness for HTML/PDF-oriented sources
- depth of automation around operations and recovery
- dashboard integration depth, because the dashboard is still prototype-only in
  this branch

## Migration Notes That Still Matter

### HTTP Role / Capability Configuration

- `HTTP_AUTH_ROLE` is now the primary operator-facing HTTP auth setting
- `HTTP_AUTH_CAPABILITIES` may still be set explicitly, but it must match the
  selected role bundle
- deployments that previously relied on `HTTP_AUTH_CAPABILITIES` without
  `HTTP_AUTH_ROLE` should now set the matching role explicitly

### Viewer Role Tightening

- `viewer` is now read-only
- `preview_dataset` requires `refresh`, so it belongs to `operator` and `admin`

### Export Path Clarity

- the governed institutional export path today is the CLI `export` command
- the dashboard package is not the governed export surface in this branch
- if the dashboard exposes export actions during prototype review, treat them as
  prototype-local rather than as the canonical institutional artifact path

### Dashboard Boundary

- the dashboard remains optional and mock-driven in this branch
- do not treat it as a live operational dependency of the governed backend/core

## Canonical Semantic Anchors

To reduce cross-surface wording drift, use these as the current semantic
anchors:

- `query_dataset`
  - local-only analytical path over local snapshots
- `download_dataset`
  - local-only artifact-availability path
- `preview_dataset`
  - the only hybrid local/live/stale path
- CLI export
  - the governed institutional artifact path today
- dashboard
  - optional prototype surface in this branch, not a governed live runtime
- current metadata wording
  - `data_origin`
  - `freshness_status`
  - `failure_stage`
  - `degradation_reason`

For the underlying current-state detail, use:

- [docs/GOVERNANCE.md](./GOVERNANCE.md)
- [docs/DEPLOYMENT.md](./DEPLOYMENT.md)
- [docs/OPERATIONS.md](./OPERATIONS.md)
- [docs/RUNBOOKS.md](./RUNBOOKS.md)
- [docs/PERSISTENCE.md](./PERSISTENCE.md)
