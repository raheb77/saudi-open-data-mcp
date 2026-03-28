# Datasets

## Source Scope

- Initial source scope is SAMA only.
- Only approved official sources may be accessed.

## Current State

- No dataset fetching is implemented in the repository scaffold.
- No dataset registry entries are persisted yet.
- Dataset descriptors and health metadata will be owned by `registry/` when implemented.

## Contract Direction

- normalized outputs will use typed Pydantic models
- registry metadata will remain the source of truth for descriptors, caveats, schema versions, and health metadata
