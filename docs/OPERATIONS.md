# Operations Notes

Internal-only runtime and durability guidance for the current container-first phase.

## Runtime Model

- `REGISTRY_PATH` points to the SQLite registry file. Treat it as persistent state.
- `SNAPSHOT_DIR` stores raw connector payload snapshots. Treat it as persistent state.
- `CACHE_DIR` is recreatable scratch state. It may be wiped and rebuilt.
- `resource://observability` counters, in-memory rate limits, and Tier A refresh loop state are process-local. They reset on process restart.

## Startup

1. Set `HTTP_AUTH_TOKEN` for `run-http`.
2. Set `HTTP_AUTH_CAPABILITIES` for the allowed HTTP surface.
3. Set persistent `REGISTRY_PATH` and `SNAPSHOT_DIR` if you are not using the default container volume.
4. Optionally set `TIER_A_REFRESH_ENABLED=true` and `TIER_A_REFRESH_INTERVAL_SECONDS`.
5. Validate startup locally with:

```bash
python src/saudi_open_data_mcp/cli.py check-startup
```

6. Start the internal HTTP service with:

```bash
docker compose up --build
```

Config failures are expected to fail fast with concise CLI errors. Common examples:

- invalid boolean values such as `TIER_A_REFRESH_ENABLED=sometimes`
- conflicting storage paths such as `REGISTRY_PATH` matching `SNAPSHOT_DIR`
- path-type mistakes such as pointing `SNAPSHOT_DIR` at a file
- missing `HTTP_AUTH_TOKEN` for `run-http`
- invalid `HTTP_AUTH_CAPABILITIES` values

Readiness for the internal container path is intentionally narrow:

- `GET /readyz` means the process is running, config validation passed, runtime storage preparation passed, and the core FastMCP app was wired successfully.
- `GET /readyz` does not claim upstream reachability, dataset freshness, or full-system health.
- The container image and the provided Compose service both use that same `/readyz` contract for health checks.
- `/mcp` still requires an MCP-aware client for real protocol/session validation.

## Shutdown

- Prefer graceful stop: `docker compose stop`
- Do not delete the persistent runtime volume if you want registry and snapshot state to survive replacement.
- A process restart clears process-local counters and in-memory rate-limit state, but does not remove persistent registry or snapshot data.

## Tier A Refresh

- When enabled, the Tier A loop runs once immediately after service startup and then repeats on the configured interval.
- Per-dataset failures stay inside the materialization result and do not stop the loop.
- Cycle-level failures increment `tier_a_refresh.run_failures` and emit `tier_a_refresh.run.failed` logs.
- Per-dataset materialization outcomes still use `materialize.*` counters.

## Stale Data / Refresh Failure

- `preview_dataset` may serve a stale snapshot with notice only when:
  - a stale local snapshot exists
  - live refresh fails
- If the snapshot is missing and refresh fails, preview fails closed.
- `query_dataset` remains local-only and never performs a live refresh.

## Observability

- Read `resource://observability` for the current grouped process-local counter snapshot.
- Use structured logs for event detail:
  - `server.startup.*`
  - `preview.request.*`
  - `audit.*`
  - `connector.request.*`
  - `materialize.*`
  - `tier_a_refresh.*`
  - `http.authz.rejected`
  - `http.authz.coverage_missing`
- `audit.*` logs are the narrow governance/audit layer for important core operations such as query, preview, materialization, local artifact lookup, metadata/health lookup, and capability denials.
- When the request context is available on the HTTP path, audit events include best-effort request identity fields such as request id, JSON-RPC id, transport, and a token fingerprint rather than the raw bearer token.
- Do not treat `resource://observability` as a health endpoint or a public metrics API.

## HTTP Capabilities

- `read`:
  - `resource://catalog`
  - `resource://observability`
  - `dataset_metadata`
  - `dataset_health`
  - `download_dataset`
  - `query_dataset`
  - `search_datasets`
- `refresh`:
  - `preview_dataset`
- `materialize`:
  - `materialize_hot_set`

`preview_dataset` requires `refresh` because its hybrid policy can trigger live
connector refreshes.

## Backup / Restore

Backup:

1. Stop the service or otherwise ensure no active writer is modifying registry or snapshots.
2. Copy:
   - `REGISTRY_PATH`
   - all of `SNAPSHOT_DIR`
3. `CACHE_DIR` is optional and usually not worth backing up.

Restore:

1. Stop the service.
2. Restore `REGISTRY_PATH` and `SNAPSHOT_DIR` to the intended runtime location.
3. Remove or ignore stale `CACHE_DIR` contents if needed.
4. Restart the service and verify startup plus current counters/logs.

This phase improves internal reliability only. It does not claim public-internet deployment readiness.
