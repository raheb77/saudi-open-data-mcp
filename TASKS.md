# Current Release Readiness Notes

## Current Baseline In Repo

- Governed multi-source core across SAMA, `stats.gov.sa`, Ministry of Finance, and one narrow `data.gov.sa` pilot path
- Container-first internal streamable HTTP runtime plus stdio and CLI access paths
- Optional live-integrated dashboard package under `dashboard/`
- CI coverage for Ruff, mypy, pytest, package build, clean-install startup smoke, dashboard test/build, and Docker image build
- Curated live upstream canary coverage plus explicit registry descriptor reconciliation for persistent deployments

## Still Intentionally Open

- CI builds the Docker image but does not yet run a post-build container startup smoke.
- The upstream canary covers curated queryable datasets for SAMA, `stats.gov.sa`,
  and Ministry of Finance, not the full catalog.
- No queryable `data.gov.sa` dataset is registered yet; the canary intentionally
  skips `data.gov.sa` until a `queryable` data.gov.sa descriptor exists.
- Backup/restore, retention, and public release publication remain operator/release-process responsibilities rather than automated repo workflows.
