# saudi-open-data-mcp dashboard (Phase 5)

Arabic RTL dashboard prototype over the existing `saudi-open-data-mcp` core.
This is now a **thin live integration** over the existing MCP core.
The dashboard calls the current `/mcp` and `/readyz` surfaces directly, keeps
runtime payload validation at the frontend boundary, and does not invent a
parallel backend.

## Scope

- Three pages: Home, Query, System Status
- Arabic-only UI, full RTL, Latin numerals for data displays
- Mandatory shared `MetadataStrip` on every result-oriented view
- Distinct rendering for: loading, empty, success, limited, stale, failed,
  missing, snapshot_missing, unauthorized
- Thin live data adapter over `resource://catalog`, `resource://observability`,
  `query_dataset`, `preview_dataset`, `dataset_health`, and `/readyz`
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

For local live development against `run-http`, you can optionally proxy the
backend through Vite so the browser stays same-origin and bearer tokens remain
server-side:

```bash
cd dashboard
DASHBOARD_PROXY_TARGET=http://127.0.0.1:8000 \
DASHBOARD_PROXY_BEARER_TOKEN=your-token-here \
npm run dev
```

## Live surface mapping

| Frontend adapter call            | Core surface                    |
| -------------------------------- | ------------------------------- |
| `listDatasets()`                 | `resource://catalog`            |
| `getDatasetQueryResult()`        | `query_dataset`                 |
| `getDatasetPreviewResult()`      | `preview_dataset`               |
| `getDatasetHealthResult()`       | `dataset_health`                |
| `getObservability()`             | `resource://observability`      |
| `getReadiness()`                 | `/readyz`                       |

The remaining mock modules are now test/prototype fixtures only. The pages no
longer read them directly.
