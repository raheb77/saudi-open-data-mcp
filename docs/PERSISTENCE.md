# Persistence, Backup, and Restore

Current-state persistence and recovery guide for this branch.

This document is intentionally narrow:

- no disaster-recovery claims
- no hidden storage replication story
- no automated backup workflow claims

## Persistence Map

### Persistent Runtime State

These are the current backend state paths that matter operationally:

- `REGISTRY_PATH`
  - SQLite registry state
  - bootstrapped descriptors plus runtime metadata updates
  - should be treated as persistent
- `SNAPSHOT_DIR`
  - raw connector payload snapshots
  - should be treated as persistent

### Recreatable Local State

- `CACHE_DIR`
  - recreatable scratch state
  - may be deleted and rebuilt
  - usually not worth backing up

### Process-Local Only

These reset on process restart and are not restored from disk:

- `resource://observability` counters
- in-memory rate-limit state
- Tier A refresh loop state
- request-scoped audit/request context

### Derived / Generated Outputs

- CLI export files such as JSON, Excel-compatible XML, and PDF artifacts
  - only exist if an operator explicitly writes them
  - not tracked by the application as managed state
  - back them up only if the institution wants to preserve those exact artifacts
- structured logs
  - emitted by the process
  - persistence depends on the runtime environment or container log collection, not on an app-managed log store

### Local / Optional But Not Core Runtime State

- dashboard `node_modules`, build outputs, and dev caches
  - not governed backend state
  - regeneratable
- dashboard runtime state in this branch
  - there is no live dashboard data store to back up
  - the dashboard remains a mock-driven prototype in this branch

## What To Back Up

Minimum current backup set for the governed backend:

1. `REGISTRY_PATH`
2. all of `SNAPSHOT_DIR`

Optional backup set:

- export files written intentionally for institutional use
- runtime/container log outputs, if your local operational environment keeps them and you care about preserving them

Usually safe to regenerate instead of backing up:

- `CACHE_DIR`
- dashboard dependencies and build caches
- process-local counters and in-memory state

## What Restore Means Today

Restore in the current system is practical and manual:

1. stop the service
2. restore `REGISTRY_PATH`
3. restore all of `SNAPSHOT_DIR`
4. remove or ignore stale `CACHE_DIR` contents if needed
5. start the service again
6. verify startup, then check a few datasets with:
   - `dataset_health`
   - `query_dataset`
   - `preview_dataset`

In current-state terms, restore means:

- the registry file and local raw snapshots are put back into their intended runtime paths
- the service can then rebuild its process-local state from that disk state
- queryability depends on the restored snapshots still matching the current narrow normalization support

## Manual Recovery Notes

- restore the registry and snapshots together when possible
- if only snapshots are restored, the service may need manual re-bootstrap and health/query verification
- if only the registry is restored, datasets may appear in metadata but still have missing local artifacts
- if the runtime volume was lost entirely, there is no hidden server-side copy to recover from
- if export artifacts were not backed up separately, they should be treated as operator outputs that may need to be regenerated

## Explicit Limitations

Current backup/restore limits are important:

- no built-in backup command
- no scheduled backup subsystem
- no point-in-time or transactionally coordinated backup across registry and snapshot files
- no automatic snapshot pruning or retention-policy engine
- no object-storage replication layer
- no built-in restore verification command
- no guarantee that a restored stale snapshot set can be refreshed immediately if upstream sources are unavailable
- no guarantee that previously generated export artifacts can be reproduced byte-for-byte unless the exact same inputs and export timestamping assumptions are preserved

## Current Honest Guarantees

What the system does support today:

- explicit knowledge of which state is persistent vs recreatable
- manual file-level backup of the registry and snapshot store
- manual restore of those same paths
- deterministic startup validation after restore
- explicit health/query/preview checks after restore

Use this guide together with:

- [docs/DEPLOYMENT.md](./DEPLOYMENT.md)
- [docs/OPERATIONS.md](./OPERATIONS.md)
- [docs/RUNBOOKS.md](./RUNBOOKS.md)
