# Operational Runbooks

Current-state runbooks for the most realistic failure and recovery situations in
the current baseline.

These runbooks are intentionally narrow:

- no control-plane workflows
- no automatic remediation
- no speculative infrastructure assumptions

Use them alongside:

- [docs/DEPLOYMENT.md](./DEPLOYMENT.md)
- [docs/OPERATIONS.md](./OPERATIONS.md)
- [docs/PERSISTENCE.md](./PERSISTENCE.md)

## Recovery Terminology

These runbooks use the current repository terms intentionally:

- restore
  - put previously backed-up `REGISTRY_PATH` and `SNAPSHOT_DIR` back into the
    intended runtime paths
- regenerate
  - recreate state from current live sources or from the runtime itself
- recover
  - restore, regenerate, or both, depending on what was lost and what still
    exists

Use [docs/PERSISTENCE.md](./PERSISTENCE.md) as the source of truth for what is
persistent, what is recreatable, and when restore is different from
regeneration.

## 1. Service Not Starting

**Symptom**

- `python src/saudi_open_data_mcp/cli.py check-startup` exits with an error
- `run-http` exits immediately
- `docker compose up` shows the container restarting
- `GET /startupz` never becomes ready

**Likely causes**

- `HTTP_AUTH_TOKEN` is missing for `run-http`
- `HTTP_AUTH_ROLE` is invalid
- `HTTP_AUTH_CAPABILITIES` is invalid or does not match the selected role
- storage-path configuration is invalid:
  - `REGISTRY_PATH` and `SNAPSHOT_DIR` conflict
  - a directory path points at a file
  - the configured path is not writable
- the configured HTTP port is already in use

**Quick checks**

```bash
python src/saudi_open_data_mcp/cli.py check-startup
docker compose logs app
```

- confirm that the configured HTTP port is free
- confirm that the runtime volume or local storage path exists and is writable

**Recovery steps**

1. Fix the reported config error first.
2. Ensure `HTTP_AUTH_ROLE` and `HTTP_AUTH_CAPABILITIES` agree.
3. Ensure `REGISTRY_PATH` and `SNAPSHOT_DIR` are distinct and writable.
4. Free the configured port or change it explicitly.
5. Start the service again and then confirm `/startupz`.

**Not yet supported / manual**

- no automatic config repair
- no automatic storage migration
- no installer or first-run wizard

## 2. MCP Endpoint Unavailable

**Symptom**

- the service is running, but the MCP client cannot use `/mcp`
- the client gets connection refused, `401`, or `403`
- a browser probe appears to "fail" even though the service is up

**Likely causes**

- the backend process is not actually running
- the client is using the wrong host, port, or path
- the bearer token is missing or wrong
- the HTTP role/capability bundle does not allow the requested operation
- the caller is using a generic HTTP client instead of an MCP-aware client
- the service is bound to `127.0.0.1` but the caller expects remote access

**Quick checks**

```bash
curl http://127.0.0.1:8000/startupz
docker compose logs app
```

- confirm the target path is `/mcp`
- confirm the caller is sending `Authorization: Bearer <token>`
- confirm the caller is an MCP-aware client or inspector

**Recovery steps**

1. Verify the service starts cleanly and `/startupz` is ready.
2. Correct the MCP endpoint URL, host, or port.
3. Correct the bearer token.
4. Correct the configured HTTP role if the current bundle is too narrow.
5. Retry with an MCP-aware client instead of treating `/mcp` as a generic JSON endpoint.

**Not yet supported / manual**

- no anonymous MCP access
- no browser-friendly REST fallback for `/mcp`
- no documented public-internet serving pattern today

## 3. Dashboard Unable To Load Live Data

**Symptom**

- an operator expects the dashboard to reflect live backend data
- the dashboard shows loading, unauthorized, or error states instead of live data
- browser network tools show failed `/mcp` or `/startupz` requests

**Likely causes**

- the backend is not running or `/startupz` is not actually ready
- the dashboard is not reaching the intended backend origin or local proxy target
- the bearer token or proxy token forwarding is missing or wrong
- the configured HTTP role/capability bundle does not allow the requested MCP operations
- the live dashboard received a malformed or unexpected payload and failed validation

**Quick checks**

- read [dashboard/README.md](../dashboard/README.md)
- confirm the browser network panel shows `/mcp` and `/startupz` requests
- confirm the backend is running and `/startupz` responds successfully
- if using local frontend development, confirm any optional Vite proxy target and bearer token are configured correctly

**Recovery steps**

1. Verify the backend starts cleanly and `/startupz` is ready.
2. Verify the dashboard is pointed at the correct same-origin backend or optional local proxy target.
3. Correct the bearer token or proxy token forwarding if MCP requests return `401` or `403`.
4. If the HTTP role is too narrow, correct the configured role/capability bundle and retry.
5. If the dashboard is failing on payload validation, treat it as a cross-surface integration issue and inspect the failing `/mcp` or `/startupz` response directly while the CLI remains the fallback governed access path.

**Not yet supported / manual**

- no dashboard-owned backend or fallback API
- no browser-friendly REST fallback for `/mcp`
- no repo-provided production reverse-proxy topology beyond the optional local Vite proxy path

## 4. Source Fetch Failure

**Symptom**

- `preview_dataset` returns `failed`
- `preview_dataset` returns `limited` after a live fetch attempt
- `materialize_hot_set` shows one or more failed dataset results
- logs show `connector.request.*`, `preview.request.*`, or `materialize.*` failures

**Likely causes**

- the upstream official source is temporarily unavailable
- local network egress is blocked
- a source base-URL override points to the wrong host or path
- an upstream HTML or PDF layout changed beyond the currently supported parser
- an upstream request timed out

**Quick checks**

```bash
python src/saudi_open_data_mcp/cli.py preview <dataset_id>
python src/saudi_open_data_mcp/cli.py health <dataset_id>
python src/saudi_open_data_mcp/cli.py upstream-canary
docker compose logs app
```

- review structured logs for `connector.request.*`
- confirm any `*_BASE_URL` override matches the intended official source

**Recovery steps**

1. Retry once if the failure looks transient.
2. Remove or correct bad source base-URL overrides.
3. If a local snapshot already exists, continue using local query or stale preview behavior where the tool exposes it.
4. If the upstream layout has changed, treat it as a code-maintenance issue and update the extractor conservatively.

**Not yet supported / manual**

- no automatic source failover
- no hidden remote fallback for `query_dataset`
- no automatic parser repair when a source layout drifts

## 5. Stale Or Missing Snapshots

**Symptom**

- `query_dataset` returns `snapshot_missing`
- `download_dataset` reports `artifact_missing`
- `dataset_health` shows stale or missing freshness
- `preview_dataset` serves stale data with notice, or fails closed when no snapshot exists and refresh fails

**Likely causes**

- no local snapshot has been written yet
- the snapshot volume or directory was deleted or not mounted persistently
- the Tier A refresh loop is disabled
- an upstream fetch failed, so no newer snapshot was written
- the dataset is outside the current hot-set materialization path

**Quick checks**

```bash
python src/saudi_open_data_mcp/cli.py health <dataset_id>
python src/saudi_open_data_mcp/cli.py preview <dataset_id>
python src/saudi_open_data_mcp/cli.py query <dataset_id> --limit 5
```

- confirm `SNAPSHOT_DIR` points to persistent storage
- for container runs, confirm the named volume is still attached

**Recovery steps**

1. If the local snapshot store still exists and you are trying to recreate fresher state, prefer regeneration first.
2. For Tier A SAMA datasets, run:

```bash
python src/saudi_open_data_mcp/cli.py refresh
```

3. For other supported datasets, run `preview_dataset` through the CLI or an MCP-aware client to attempt a live fetch/write through the current preview path.
4. If the runtime volume or snapshot directory was lost and you have a backup, use restore rather than regeneration:
   - restore `REGISTRY_PATH` and `SNAPSHOT_DIR`
   - then restart the service
5. Re-run `dataset_health`, then `query_dataset` or `download_dataset`.

**Not yet supported / manual**

- no automatic historical backfill
- no remote query path when a snapshot is missing
- no automatic recovery after accidental snapshot-volume deletion
- no guarantee that regeneration from current live sources recreates the exact
  prior snapshot set

## 6. Export Failure

**Symptom**

- `python src/saudi_open_data_mcp/cli.py export ...` exits non-zero
- no output file is written
- Excel-compatible XML or PDF export fails even though the CLI itself starts

**Likely causes**

- the output path is not writable
- `--format excel` or `--format pdf` was used without `--output`
- the dataset has no usable local query result yet:
  - `snapshot_missing`
  - failed local query
  - unsupported local normalization path
- the dataset health lookup used for freshness context also failed validation

**Quick checks**

```bash
python src/saudi_open_data_mcp/cli.py query <dataset_id> --limit 5
python src/saudi_open_data_mcp/cli.py health <dataset_id>
```

- confirm the output directory exists and is writable
- confirm the requested export format is one of `json`, `excel`, or `pdf`

**Recovery steps**

1. Fix the output path first.
2. For Excel/PDF, make sure `--output` is present.
3. Treat CLI export artifacts as derived outputs:
   - regenerate them by rerunning export when the underlying query result is available
4. Ensure the dataset has a local queryable snapshot before retrying export.
5. If the dataset is missing locally, recover the snapshot first through `refresh` or `preview_dataset`, depending on the dataset path.
6. If the institution needs the exact previous exported file, restore that file only if it was backed up separately; restoring `REGISTRY_PATH` and `SNAPSHOT_DIR` alone does not restore previously written export artifacts.

**Not yet supported / manual**

- no export-only data retrieval path
- no `.xlsx` export today
- no managed export archive or export-retention subsystem
- dashboard export actions remain UI convenience over live query-result semantics; the CLI remains the canonical governed institutional export path
