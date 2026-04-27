# Roadmap

## Current Baseline

- governed multi-source core with explicit source isolation, typed normalization, registry-backed metadata, and deterministic MCP/CLI surfaces
- installable Python package plus container-first internal HTTP runtime
- optional dashboard package as a live consumer of the governed backend
- CI coverage for source-tree checks, built artifacts, dashboard build/test, and Docker image build

## Next Focus

1. Add a post-build container startup smoke so CI exercises the built image, not just the Docker build.
2. Expand approved source coverage conservatively, one dataset family at a time, with matching test and canary coverage.
3. Tighten operational lifecycle automation around release publication, snapshot retention, and operator verification without widening the core product scope.

## Post-0.4.0 Deferrals

- `resource://policies` remains hardcoded for v0.4.0 per Decision D-05; making it data-driven from tool registrations is deferred to [GitHub issue #3](https://github.com/raheb77/saudi-open-data-mcp/issues/3).
