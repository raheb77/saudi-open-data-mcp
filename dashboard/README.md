# saudi-open-data-mcp dashboard (Phase 5)

Arabic RTL dashboard prototype over the existing `saudi-open-data-mcp` core.
This is now a **thin live integration** over the existing MCP core.
The dashboard calls the current `/mcp` and `/readyz` surfaces directly, keeps
runtime payload validation at the frontend boundary, and does not invent a
parallel backend.

This package is optional. The governed backend/core can run without the
dashboard. The dashboard is a separate frontend package that consumes the live
backend surfaces when they are available, but it is not required for running
the governed Python core.

The governed institutional export path today is still the CLI export surface in
the backend/core. Dashboard export actions use the same live query-result
semantics for local UI convenience, but the CLI remains the canonical
institutional export path.

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

## Runtime Expectations

- local dashboard dev server: `127.0.0.1:5173`
- separate package from the Python backend
- same-origin `/mcp` and `/readyz` are expected in production-style deployment
- local development can use the optional Vite proxy shown above
- no dashboard-owned backend logic or parallel API layer

For the current repository-wide deployment/runtime story, see
[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md). For current baseline change
visibility and migration notes, see [docs/CHANGELOG.md](../docs/CHANGELOG.md).

## Live surface mapping

| Frontend adapter call            | Core surface                    |
| -------------------------------- | ------------------------------- |
| `listDatasets()`                 | `resource://catalog`            |
| `getDatasetQueryResult()`        | `query_dataset`                 |
| `getDatasetPreviewResult()`      | `preview_dataset`               |
| `getDatasetHealthResult()`       | `dataset_health`                |
| `getObservability()`             | `resource://observability`      |
| `getReadiness()`                 | `/readyz`                       |

The remaining mock modules are now test fixtures only. The pages no longer read
them directly.
