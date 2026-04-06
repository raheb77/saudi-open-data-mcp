# saudi-open-data-mcp dashboard (Phase 5 prototype)

Arabic RTL dashboard prototype over the existing `saudi-open-data-mcp` core.
This is an **interactive prototype with mock data only** (build level B).
It does not call the real MCP core, but the mock payloads are shaped exactly
like `DatasetQueryResult`, `DatasetHealthLookupResult`,
`SnapshotFreshnessResult`, `ReadinessReport`, and `ObservabilitySummary` from
the current Python core.

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
