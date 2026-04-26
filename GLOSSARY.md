# Glossary

Source-of-truth mapping for version, wave, phase, and tier terminology used
across the `saudi-open-data-mcp` codebase and documentation.

## Semver Versions

| Version | Meaning |
|---|---|
| **v0.1** | Initial single-source (SAMA-only) architecture. Referenced in ADR-001. Historical; the codebase has moved past this baseline. |
| **v0.2** | Multi-source readiness milestone. Referenced in ADR-002. Historical; multi-source support is now implemented. |
| **0.3.x** | The pre-hardening internal/evaluator baseline. Four sources (SAMA, stats.gov.sa, MoF, data.gov.sa pilot) are wired and tested. |
| **0.4.0a1** | Current target. Internal/evaluator alpha produced by the v0.4.0 hardening cycle. Not a public release. |

## Hardening Cycle Waves

Waves are execution phases within the v0.4.0 hardening cycle. They are defined
in `AGENTS_TASK_CONTEXT.md` section 12 and govern the order in which agent
prompts run.

| Term | Meaning |
|---|---|
| **Wave 1** | Sequential foundation work. Prompts 1 through 4: CI, security debt, dead-code removal, state-path hardening. |
| **Wave 2** | Parallel pair. Agent A (Prompt 5: runtime hardening) and Agent B (Prompt 6: docs/CLI/narrative consistency). |
| **Wave 3** | Sequential follow-up. Prompts 8 and 9: policies resource, CacheStore removal, final cleanup. |
| **Wave 4** | Deferred. Saudi-context work (PDPL, licensing, Arabic/TZ). Only runs before institutional review; not part of the v0.4.0 alpha. |
| **Prompt 10** | Final audit pass. Security and release-gate review after Waves 1-3. |

## Dashboard Build Phases

Phases describe the iterative build stages of the `dashboard/` package. They
are separate from hardening-cycle waves.

| Term | Meaning |
|---|---|
| **Phase 1-4** | Earlier dashboard iterations (layout, wiring, state handling, exports). Referenced historically in dashboard code. |
| **Phase 5** | Current dashboard baseline. Arabic RTL thin live integration over the governed MCP backend. Referenced in `dashboard/README.md` and `dashboard/package.json`. |

## Data Tier Classification

Tiers classify datasets and work items by priority and operational readiness.

| Term | Meaning |
|---|---|
| **Tier A** | Core hot-set datasets with background refresh support. Currently the safe SAMA subset. Used in `refresh`, `materialize_hot_set`, and the container runtime refresh loop. |
| **Tier B** | Optional datasets included only when `--include-optional` is passed to `refresh`. Not part of background refresh in the current baseline. |
| **Tier 1** | (Hardening cycle only) Highest-priority security debt items resolved in Prompts 2/2A+2B. See `AGENTS_TASK_CONTEXT.md` section 5. |
| **Tier 4** | (Hardening cycle only) Deferred Saudi-context concerns (PDPL, licensing, Arabic+TZ). Mapped to Wave 4. |

## Deprecated Terms

| Term | Status | Notes |
|---|---|---|
| DuckDB | **Removed.** | Listed in ADR-001 and the original AGENTS.md tooling section but never used in code. Removed during the v0.4.0 hardening cycle. |
| `health/` package | **Deleted.** | Existed as a disconnected placeholder. Removed in Wave 1 (Prompt 3). |
| `CacheStore` | **Pending removal.** | `storage/cache.py` is path-computation only. Scheduled for deletion in Wave 3 (Prompt 9). |
