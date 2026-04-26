# ADR-004: v0.4.0 Release Strategy and Wave-Based Execution

- Status: Accepted
- Date: 2026-04-27
- Supersedes: ADR-001 (partially), ADR-002 (partially)

## Context

The `saudi-open-data-mcp` codebase reached a `0.3.x` baseline with four
source families (SAMA, stats.gov.sa, MoF, data.gov.sa pilot), a working
registry, normalization pipeline, CLI, HTTP serving, and dashboard. However,
documentation overclaims, dead code, and unresolved security debt had
accumulated faster than they were being resolved.

The v0.4.0 hardening cycle was designed as a structured, multi-agent pass to
ship a clean internal/evaluator alpha in approximately two days. The cycle
uses Wave-based execution to order work and prevent cross-agent conflicts.

## Decision

### Release posture

v0.4.0 is an **internal/evaluator alpha**. No documentation, commit message,
or server metadata may claim production readiness, public-internet hardening,
or live-data reliability. This is Decision D-01 and is locked for the cycle.

### Wave-based execution model

Work is organized into four waves executed sequentially at the wave level,
with limited parallelism within waves:

| Wave | Execution | Contents |
|---|---|---|
| Wave 1 | Sequential | Prompts 1-4: CI hardening, security debt (Tier 1), dead-code removal, state-path hardening |
| Wave 2 | Parallel (2 agents) | Agent A: Prompt 5 (runtime hardening) / Agent B: Prompt 6 (docs, CLI, narrative consistency) |
| Wave 3 | Sequential | Prompts 8-9: policies resource, CacheStore removal, final cleanup |
| Wave 4 | Deferred | Tier 4: PDPL, licensing, Arabic/TZ — only before Saudi institutional review |
| Prompt 10 | Final | Security audit and release-gate review |

Agents may not perform work assigned to a later wave. The boundary is enforced
by task prompts and the `AGENTS_TASK_CONTEXT.md` document.

### Locked decisions for v0.4.0

The following decisions are locked for the hardening cycle. They are not
subject to relitigation in commits or PR descriptions.

| ID | Decision | Implication |
|---|---|---|
| D-01 | Release = internal/evaluator alpha | No "production-ready" claims in any docs or metadata |
| D-03 | Delete `health/` package | Directory removed; references cleaned from AGENTS.md and ARCHITECTURE.md |
| D-04 | Delete `CacheStore` placeholder | Removed from `storage/` exports (Wave 3) |
| D-05 | `resource://policies` stays hardcoded | Data-driven refactor deferred to Wave 3 |
| D-06 | Prompt 2 splits if >5 core files or shared Protocol changes | Agent self-reports file count before edits |
| D-08 | Tier 4 deferred to Wave 4 | No Saudi-specific compliance docs in Waves 1-3 |

Decisions D-02, D-07, D-09, and D-10 were either resolved inline during cycle
planning or consolidated into other decisions.

## Relationship to prior ADRs

### ADR-001 (Start with SAMA)

Partially superseded. The single-source constraint was correct for v0.1 but no
longer reflects reality. The codebase now has four source families with
connector resolution by `descriptor.source`. The architectural principles
(source isolation, typed contracts, registry ownership, no-LLM core path)
remain fully in effect.

Additionally, the DuckDB references in ADR-001 are now historical. DuckDB was
planned as a local analytical helper but was never used. The normalization
pipeline uses Pydantic models directly.

### ADR-002 (Multi-source readiness)

Partially superseded. Multi-source readiness has been implemented: connector
resolution, normalization dispatch, and registry descriptors all work across
four sources. The decision's architectural rules (canonical dataset_id
stability, source-specific routing outside MCP handlers, connector resolution
by descriptor.source) are now enforced in code and contract tests. The "out of
scope for v0.2" items remain out of scope for v0.4.0 as well.

### ADR-003 (Freshness and hybrid resolution)

Not superseded. The freshness and hybrid resolution policy remains active and
accurate. v0.4.0 hardens the implementation without changing the policy.

## Consequences

- The hardening cycle produces a clean, honest internal alpha rather than
  expanding features.
- Dead code (health/, CacheStore, DuckDB references) is removed rather than
  documented as "planned".
- Security debt (Tier 1) is resolved in-cycle rather than deferred.
- Documentation overclaims are corrected to match actual implementation state.
- Wave-based execution prevents cross-agent conflicts and scope creep.
- Saudi-context compliance work (PDPL, licensing) is explicitly deferred to
  Wave 4, keeping Waves 1-3 focused on technical correctness.
