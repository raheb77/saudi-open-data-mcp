# ADR-002: Multi-source readiness for v0.2

- Status: Accepted
- Date: 2026-04-01

## Context

`saudi-open-data-mcp` started with SAMA only in v0.1. That was the correct scope decision, but the codebase now needs a clear rule for how a second approved source is added without weakening the existing boundaries.

The goal for v0.2 is not a generic ingestion platform. The goal is narrower:

- add source 2 without breaking the current MCP surface
- keep canonical `dataset_id` stable at the public boundary
- keep source-specific routing and normalization out of MCP handlers

## Decision

Multi-source support will be added by dispatching both connector resolution and normalization by `descriptor.source`.

The registry remains the control plane:

- MCP tools accept canonical `dataset_id`
- the registry resolves that to a descriptor
- the descriptor provides `source` and `source_locator`
- connector selection uses `descriptor.source`
- source retrieval uses `descriptor.source_locator`
- normalization selection also uses `descriptor.source`

`server.py`, `tools/`, and `resources/` remain thin composition layers. They must not branch on specific source names.
Connector resolution will live in a small source-to-connector resolver/factory outside `server.py`, so `server.py` stays a composition layer rather than a source switchboard.

## Connector output contract before normalization

Every connector must produce the same typed raw payload contract before normalization runs.

Minimum required fields:

- `source`: source identifier from the registry descriptor
- `source_locator`: source-specific identifier or locator used at the source boundary
- `content`: typed raw retrieval payload and retrieval metadata

Normalization does not receive URLs or connector instances. It receives only the typed raw payload contract and dispatches by `raw_payload.source`.

## Public MCP surface stability

These public MCP rules stay stable when source 2 is added:

- MCP callers continue to use canonical `dataset_id`
- `source_locator` remains internal and must not be exposed in normal success responses
- existing top-level tool semantics stay intact:
  - registry misses stay explicit
  - snapshot-missing states stay distinct from registry misses
  - local-only tools do not fetch remotely as fallback
- stdio and HTTP remain transport-thin wrappers over the same internal logic

## Minimum code changes required for source 2

Adding source 2 requires changes in only these areas:

1. Add a new connector implementation under `connectors/`.
2. Add source-2 registry descriptors in `registry/bootstrap.py` or the active registry seed path.
3. Introduce normalization dispatch by source as a prerequisite for source 2.
4. Replace direct connector wiring with connector resolution by `descriptor.source`.
5. Add tests that prove source-1 and source-2 both work through the same MCP surface.

If adding source 2 requires changes in MCP handlers beyond dependency composition, the architecture is leaking.

## Out of scope for v0.2

The following remain out of scope for this decision:

- dynamic source discovery
- multiple locators per dataset
- semantic search or query rewriting
- cross-source canonical record unification beyond the current typed record layer
- a generic plugin system for arbitrary sources
- hiding all source-specific failures if the underlying connector needs them for debugging

## Consequences

Positive:

- source growth happens by adding adapters, not rewriting MCP tools
- canonical identity stays stable for MCP callers
- source-specific logic remains concentrated in connectors and normalization dispatch

Negative:

- v0.2 still requires explicit per-source mapping and validation code
- some normalization logic that is currently SAMA-only must be moved behind source dispatch before source 2 can land
