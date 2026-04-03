# ADR-003: Freshness and Hybrid Resolution Policy

## Status

Accepted

## Context

`saudi-open-data-mcp` now has three interacting runtime behaviors:

- local raw snapshot persistence
- explicit snapshot freshness evaluation
- hybrid local/live resolution in `preview_dataset`

These behaviors existed in code, but parts of the operational policy were still
implicit. Internal serving needs an explicit policy for freshness semantics,
hybrid resolution semantics, and graceful degradation semantics.

## Decision

### Freshness semantics

Freshness is evaluated from local snapshot evidence only.

- `fresh`: a local snapshot exists and its age is within the deterministic
  freshness window for the declared `update_frequency`
- `stale`: a local snapshot exists and its age exceeds that window
- `missing`: no local snapshot artifact exists
- `unknown`: a local snapshot exists but the dataset does not currently declare
  a deterministic freshness window

For the current runtime contract:

- `UpdateFrequency.UNSPECIFIED` is treated as `unknown`
- `UpdateFrequency.AD_HOC` is treated as `unknown`
- `None` update frequency is also treated as `unknown`

These cases are intentionally not treated as implicitly fresh.

### Hybrid resolution semantics for `preview_dataset`

`preview_dataset` is the only tool in this phase that uses the hybrid policy.

- `serve_local`: read and normalize a usable local snapshot
- `refresh_then_serve`: perform a live connector refresh, persist the snapshot,
  then normalize and serve that refreshed payload
- `serve_stale_with_notice`: serve a stale local snapshot with explicit notice
  after an allowed degraded-path decision
- `fail_closed`: return a structured failure instead of serving invented,
  partial, or unverified data

### Graceful degradation rules

- `fresh` local snapshot: serve local
- `stale` local snapshot: attempt live refresh first
- `stale` local snapshot + refresh failure: serve stale snapshot with notice
- `missing` snapshot: attempt live refresh
- `missing` snapshot + refresh failure: fail closed
- `unknown` freshness because frequency is `unspecified` or `ad_hoc`: serve
  local if a usable snapshot exists
- policy selected local but local artifact is unusable: log the miss explicitly
  and fall through to live refresh

The system does not broaden stale fallback to missing snapshots. Degradation is
allowed only when a stale local artifact actually exists.

### Shared-locator semantics

Freshness and snapshot presence are evaluated per `(source, source_locator)`
artifact, then rebound to the canonical `dataset_id` in tool responses.

Current shared-locator examples:

- `sama-pos-weekly` and `sama-pos-by-city` both use
  `/en-US/Indices/Pages/POS.aspx`
- `sama-money-supply` and `sama-deposits-core` both use
  `report.aspx?cid=55`

This means those datasets currently share the same raw snapshot evidence and
freshness state. This is intentional for the current hot-set phase and is not a
sub-series extraction guarantee.

## Consequences

- Freshness classifications are explicit instead of inferred.
- Hybrid preview behavior is explicit and testable.
- Degraded serving is limited to stale local evidence, not missing data.
- Shared-locator coupling is visible to operators and future maintainers.
