# Operational Runbooks

Current-state runbooks for the most realistic failure and recovery situations in
this branch.

These runbooks are intentionally narrow:

- no control-plane workflows
- no automatic remediation
- no speculative infrastructure assumptions

Use them alongside:

- [docs/DEPLOYMENT.md](./DEPLOYMENT.md)
- [docs/OPERATIONS.md](./OPERATIONS.md)

## 1. Service Not Starting

**Symptom**

- `python src/saudi_open_data_mcp/cli.py check-startup` exits with an error
- `run-http` exits immediately
- `docker compose up` shows the container restarting
- `GET /readyz` never becomes ready

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
5. Start the service again and then confirm `/readyz`.

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
curl http://127.0.0.1:8000/readyz
docker compose logs app
```

- confirm the target path is `/mcp`
- confirm the caller is sending `Authorization: Bearer <token>`
- confirm the caller is an MCP-aware client or inspector

**Recovery steps**

1. Verify the service starts cleanly and `/readyz` is ready.
2. Correct the MCP endpoint URL, host, or port.
3. Correct the bearer token.
4. Correct the configured HTTP role if the current bundle is too narrow.
5. Retry with an MCP-aware client instead of treating `/mcp` as a generic JSON endpoint.

**Not yet supported / manual**

- no anonymous MCP access
- no browser-friendly REST fallback for `/mcp`
- no documented public-internet serving pattern in this branch

## 3. Dashboard Unable To Load Live Data

**Symptom**

- an operator expects the dashboard to reflect live backend data
- the dashboard does not react to backend changes
- browser network tools show no `/mcp` or `/readyz` traffic

**Likely causes**

- the current dashboard package is still mock-driven by design in this branch
- the operator expected a live-integrated dashboard that does not exist here
- a local experimental branch or proxy setup is being confused with the supported branch

**Quick checks**

- read [dashboard/README.md](../dashboard/README.md)
- confirm the current dashboard pages still use `src/mocks/*`
- confirm the browser network panel shows no live MCP or readiness calls

**Recovery steps**

1. Treat the dashboard as a UI prototype only in this branch.
2. Use the governed backend through the CLI or an MCP-aware client for live operations.
3. If you are testing a local experimental dashboard integration, handle that outside the supported runbook path for this branch.

**Not yet supported / manual**

- no supported dashboard live-data integration in this branch
- no supported dashboard auth flow for `/mcp`
- no required dashboard/backend reverse-proxy topology

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

1. For Tier A SAMA datasets, run:

```bash
python src/saudi_open_data_mcp/cli.py refresh
```

2. For other supported datasets, run `preview_dataset` through the CLI or an MCP-aware client to attempt a live fetch/write through the current preview path.
3. Restore the snapshot directory from backup if the volume was lost.
4. Re-run `dataset_health`, then `query_dataset` or `download_dataset`.

**Not yet supported / manual**

- no automatic historical backfill
- no remote query path when a snapshot is missing
- no automatic recovery after accidental snapshot-volume deletion

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
3. Ensure the dataset has a local queryable snapshot before retrying export.
4. If the dataset is missing locally, recover the snapshot first through `refresh` or `preview_dataset`, depending on the dataset path.

**Not yet supported / manual**

- no export-only data retrieval path
- no `.xlsx` export in this branch
- the dashboard's export actions remain prototype-local because the dashboard is still mock-driven here
