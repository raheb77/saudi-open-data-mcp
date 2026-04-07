# saudi-open-data-mcp dashboard (Phase 5 prototype)

Arabic RTL dashboard prototype over the existing `saudi-open-data-mcp` core.
This is an **interactive prototype with mock data only** (build level B).
It does not call the real MCP core, but the mock payloads are shaped exactly
like `DatasetQueryResult`, `DatasetHealthLookupResult`,
`SnapshotFreshnessResult`, `ReadinessReport`, and `ObservabilitySummary` from
the current Python core.

This package is optional. The governed backend/core can run without the
dashboard, and the dashboard does not currently require `/mcp` or `/readyz`
because it is still mock-driven in this branch.

The governed institutional export path today is still the CLI export surface in
the backend/core. Any dashboard export action in this branch should be treated
as prototype-local, not as the canonical institutional export path.

## Scope

- Three pages: Home, Query, System Status
- Arabic-only UI, full RTL, Latin numerals for data displays
- Mandatory shared `MetadataStrip` on every result-oriented view
- Distinct rendering for: loading, empty, success, limited, stale, failed,
  missing, snapshot_missing, unauthorized
- No BI tooling, no charts, no invented RBAC, no new datasets

## Commands

```bash
cd dashboard
npm install
npm run dev         # local dev server (http://127.0.0.1:5173)
npm run typecheck   # tsc -b --noEmit
npm run test        # vitest run
npm run build       # type-check + vite build
```

## Runtime Expectations

- local dashboard dev server: `127.0.0.1:5173`
- separate package from the Python backend
- no required reverse proxy in the current branch
- no live MCP session handling in the current branch
- export actions are prototype-local because the page data is still mock-driven
  and are not the governed institutional export path today

For the current repository-wide deployment/runtime story, see
[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md). For current baseline change
visibility and migration notes, see [docs/CHANGELOG.md](../docs/CHANGELOG.md).

## Mock-to-core mapping

| Mock module                  | Mirrors                         |
| ---------------------------- | ------------------------------- |
| `src/types/core.ts`          | Pydantic models from core tools |
| `src/mocks/datasets.ts`      | registry catalog subset         |
| `src/mocks/queryResults.ts`  | `DatasetQueryResult` scenarios  |
| `src/mocks/health.ts`        | `DatasetHealthLookupResult` +   |
|                              | `SnapshotFreshnessResult` +     |
|                              | `ReadinessReport`               |
| `src/mocks/observability.ts` | `ObservabilitySummary`          |

The query page exposes a scenario picker so the prototype can demonstrate
every core-visible status (`success`, `limited`, `stale`, `failed`,
`missing`, `snapshot_missing`, plus the UI-only `loading` and
`unauthorized` affordances) without fabricating new semantics.
