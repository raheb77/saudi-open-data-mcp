# ADR-001: Start with SAMA as the only source in v0.1

- Status: Accepted
- Date: YYYY-MM-DD

## Context

`saudi-open-data-mcp` is intended to be a production-minded MCP server for Saudi open data sources.

The project goal is not to maximize source count in v0.1. The goal is to establish the core architecture correctly:

- source isolation
- normalized dataset contracts
- a dataset registry
- health checks
- reliable AI-facing tool interfaces

The first release also has fixed technical constraints:

- Python 3.12
- FastMCP 2.x
- `httpx` only
- Pydantic v2
- DuckDB instead of pandas in v0.1
- SQLite for registry metadata
- no LLM dependency in the core path
- approved official sources only

The architecture therefore needs one real source that is sufficient to exercise connector design, normalization, registry usage, health checks, and MCP exposure without introducing multi-source coordination cost too early.

## Decision

Start v0.1 with SAMA as the only source.

The system will support only SAMA connectors, SAMA-specific raw payload handling, and SAMA-backed normalized datasets in the first accepted architecture.

Multi-source support is intentionally deferred. The architecture will preserve the boundaries needed for future expansion, but v0.1 will not claim that expansion as completed work.

The core path remains deterministic and typed:

- connectors fetch from approved official SAMA sources
- normalization maps raw payloads into Pydantic canonical models
- the registry stores dataset descriptors, schema versions, caveats, and health metadata
- MCP tools and resources orchestrate shared internal application logic over STDIO and Streamable HTTP

No LLM, semantic search, query rewriting, or natural-language enrichment is allowed in the core path for v0.1.

## Why SAMA Is the First Source

SAMA is the first source because it is enough to validate the intended architecture without forcing premature abstraction across multiple upstream systems.

Specific reasons:

- it provides a real official Saudi source, which satisfies the approved-source boundary
- one source is enough to validate connector isolation, retries, timeouts, and raw snapshot handling
- one source is enough to validate normalization into canonical typed contracts
- one source is enough to validate registry-backed metadata and health metadata
- one source is enough to validate MCP tool behavior over both transports

This decision keeps v0.1 focused on proving the boundaries, not on maximizing source breadth.

## Why Multi-Source Support Is Deferred

Multi-source support is deferred because adding a second source before the first source is operationally clean would hide design mistakes behind abstraction.

The deferred costs are explicit:

- more connector variants
- more field mapping divergence
- more schema reconciliation pressure
- more dataset registry entries and health states
- more tool branching logic

Deferral is a scope control mechanism. It protects the project from inventing generic abstractions before SAMA has validated the connector, normalization, registry, and MCP seams.

## Why No LLM Is Allowed in the Core Path

The core value of the project is deterministic access to Saudi open data through typed interfaces. An LLM in the core path would weaken that guarantee in v0.1.

The reasons are explicit:

- connector output normalization must be reproducible
- schema validation must be rule-based rather than model-interpreted
- dataset metadata and health metadata must come from the registry, not generated summaries
- MCP outputs must remain structured and deterministic for clients

Keeping the core path LLM-free also removes a dependency class that is unrelated to the first release objective of proving source isolation and typed contracts.

## Explicit Cost of Keeping LLM Out of the Core Path in v0.1

This decision has real costs:

- no semantic metadata search
- no Arabic query rewriting
- no natural-language enrichment in the core pipeline

These omissions mean users must rely on explicit tool parameters, deterministic metadata lookups, and typed results instead of fuzzy search or rewritten intent.

That is an accepted tradeoff in v0.1. The project prefers predictable behavior over more permissive natural-language ergonomics.

## Consequences

Positive consequences:

- the first release has a narrow operational surface
- connector failures are isolated to one source family
- canonical schema design can be tested against a concrete source
- registry design can be validated without multi-source complexity
- MCP tools can be made deterministic before broader source coverage is attempted

Negative consequences:

- dataset breadth is intentionally limited
- cross-source comparison use cases are not available
- discovery remains registry-driven rather than semantic
- Arabic-friendly query flexibility is limited because no rewriting is allowed

Neutral but important consequences:

- future expansion remains possible only if connector, normalization, and registry boundaries are preserved
- deferring multi-source support does not remove the need to design source-specific modules cleanly now

## Alternatives Considered

### Start with multiple Saudi sources immediately

Rejected because:

- it increases connector and normalization variance before the base contracts are proven
- it makes it harder to identify whether failures come from architecture problems or source differences
- it encourages generic abstractions too early

Tradeoff:

- broader initial coverage is lost
- architectural clarity is gained

### Start with a generic ingestion layer before selecting a first source

Rejected because:

- generic ingestion without a real source tends to produce vague interfaces
- the project would risk designing around hypothetical data instead of real source behavior

Tradeoff:

- abstract uniformity is lost
- source-driven correctness is gained

### Add an LLM for search and query rewriting in v0.1

Rejected because:

- it introduces nondeterminism into the core path
- it hides schema and metadata weaknesses behind prompt behavior
- it expands the runtime surface beyond the MVP goal

Tradeoff:

- user query flexibility is lost
- deterministic typed behavior is preserved

## Why SQLite and DuckDB Are Sufficient for MVP

SQLite is sufficient for the registry because registry data in v0.1 is small, structured, and local:

- dataset descriptors
- schema versions
- caveats
- health metadata

DuckDB is sufficient for local analytical helpers because the MVP needs deterministic local analysis without adding a dataframe dependency:

- inspect cached or snapshotted payloads
- support local analytical workflows near the data
- avoid pandas in v0.1

This split keeps operational roles clear:

- SQLite is the metadata source of truth
- DuckDB is a local analytical helper
- file storage keeps raw snapshots separate from both

## Why Both STDIO and Streamable HTTP Are Included from the Start

Both transports are included from the start because transport parity is part of the interface contract, not an afterthought.

STDIO is needed for local and client-driven MCP integration.

Streamable HTTP is needed for service deployment.

Including both early forces the correct boundary:

- business logic must live outside transport wiring
- the same internal application logic must support both execution modes
- tool behavior must stay consistent regardless of transport

The explicit tradeoff is a slightly larger startup surface in v0.1 in exchange for avoiding a transport rewrite after the first local-only version.

## Tradeoffs

The accepted tradeoffs are explicit:

- choose one real source instead of broad source coverage
- choose deterministic typed outputs instead of more permissive natural-language behavior
- choose SQLite plus DuckDB plus file snapshots instead of a larger storage stack
- choose transport parity now instead of adding HTTP later

These are not claims of universal optimality. They are scope decisions aligned to the MVP goal.

## What Would Change if This Decision Is Revisited in v0.2

If revisited in v0.2, the project could expand only after the v0.1 boundaries are proven in tests and in runtime behavior.

Possible changes:

- add a second approved official source by implementing a new connector, not by weakening the SAMA connector boundary
- extend canonical schemas and registry descriptors where a second source creates real schema divergence
- add additional registry metadata needed to describe source-specific caveats
- consider optional LLM-assisted features outside the deterministic core path

If LLM-assisted capabilities are reconsidered, the guardrail should remain explicit:

- LLM features must not replace connector fetching
- LLM features must not replace rule-based normalization
- LLM features must not become the source of truth for metadata
- LLM features should remain optional orchestration helpers outside the core deterministic pipeline

Revisiting the decision in v0.2 would therefore add capabilities only if the original architecture still enforces source isolation, typed contracts, registry ownership, and deterministic MCP outputs.
