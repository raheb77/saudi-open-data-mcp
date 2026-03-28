# Task Plan

## Milestone 1: Skeleton and Boundaries

- [x] Create the approved package and repository layout
- [x] Add minimal importable placeholders for approved modules
- [x] Add lint and test configuration
- [x] Add boundary-focused placeholder tests
- [ ] Add CI validation for lint and tests

## Milestone 2: SAMA Data Access and Snapshots

- [ ] Define connector abstraction behavior for approved official sources
- [ ] Implement SAMA connector timeouts and retries
- [ ] Add file-based snapshot and cache persistence
- [ ] Add freshness helpers for cached payloads

## Milestone 3: Canonical Contracts and Registry

- [ ] Define canonical normalized Pydantic models
- [ ] Implement normalization field mapping and validators
- [ ] Implement SQLite-backed registry models and repository behavior
- [ ] Add registry bootstrap for dataset descriptors and schema versions

## Milestone 4: MCP Tools and Resources

- [ ] Register deterministic MCP tools
- [ ] Register catalog and policy resources
- [ ] Wire STDIO and Streamable HTTP transports in `server.py`
- [ ] Keep MCP-facing modules dependent on internal orchestration only

## Milestone 5: Hardening

- [ ] Expand unit coverage for connectors, normalization, registry, and health
- [ ] Add integration coverage for module composition
- [ ] Add contract checks for architectural boundaries
- [ ] Add smoke coverage for CLI and transport startup
- [ ] Finalize Docker and GitHub Actions workflow behavior
