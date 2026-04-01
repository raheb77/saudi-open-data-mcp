# Datasets

## Source Scope

- Current MVP source scope is SAMA plus one narrow `data.gov.sa` pilot dataset.
- Only approved official sources may be accessed.

## Current State

- Dataset fetching is implemented through typed source-specific connectors.
- Registry entries are bootstrapped and persisted in SQLite.
- Dataset descriptors and health metadata are owned by `registry/`.
- Canonical public dataset identity is `dataset_id`.
- Source-boundary identity is kept as `source_locator` in the registry and connector path.

## Contract Direction

- normalized outputs use typed Pydantic models
- normalization dispatches by raw payload source
- registry metadata remains the source of truth for descriptors, caveats, schema versions, and health metadata
- MCP tools continue to accept canonical `dataset_id` across both supported sources
