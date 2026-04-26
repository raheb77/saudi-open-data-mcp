# AGENTS_TASK_CONTEXT.md

> **Purpose:** Single source of truth for any AI agent executing tasks in `saudi-open-data-mcp` during the **v0.4.0 hardening cycle**.
>
> **Read first.** Re-read before each commit. Do not assume anything not stated here.
>
> **Lifetime:** Active until v0.4.0 is tagged. Delete or archive after release.

---

## 1. Project Identity

- **Name:** `saudi-open-data-mcp`
- **Purpose:** MCP server exposing Saudi government open data (SAMA, data.gov.sa, GASTAT, MoF) to AI agents.
- **Owner:** Raheb Almutairi (`raheb77` on GitHub).
- **Current version:** 0.3.x baseline → targeting **0.4.0 alpha**.
- **Release type for this cycle:** **Internal / evaluator alpha.** Not a public live-data product. Do not write copy or commits implying production reliability for live upstream data.

---

## 2. The Cardinal Rule

> **Build on top of MCP, don't replace it.**

If a change adds machinery that re-implements something MCP already provides (transport, capability negotiation, schema declaration), stop and ask before proceeding.

---

## 3. Architecture (Authoritative)

Three layers. The boundary is **enforced by AST-based contract tests**, not just convention.

```
┌─────────────────────────────────────────────────┐
│  Layer 3: Tools / Resources / CLI               │
│  - tools/*.py, resources/*.py, cli.py, server.py│
│  - May import from Layer 2 only                 │
├─────────────────────────────────────────────────┤
│  Layer 2: Normalization / Registry / Contracts  │
│  - registry/, normalization/, storage/          │
│  - May import from Layer 1 only                 │
├─────────────────────────────────────────────────┤
│  Layer 1: Connectors (Data Access)              │
│  - connectors/*.py                              │
│  - Pure data fetch. No business logic.          │
└─────────────────────────────────────────────────┘
```

**Rules:**
- Tools must NEVER import from `connectors/` directly.
- Connectors must NEVER import from `tools/` or `resources/`.
- Cross-layer dependencies go through `Protocol` interfaces.
- AST tests in `tests/contracts/test_architecture_boundaries.py` enforce this.

---

## 4. Stack (Pinned Reality)

| Component | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | Strict typing required |
| MCP framework | FastMCP 2.x | Both stdio + HTTP transports |
| HTTP client | httpx | Sync + async paths |
| Data validation | Pydantic v2 (`extra="forbid"` common; `frozen=True` selective) | Typed result/contract models, with config/connector models following local needs |
| Package manager | uv | Not pip, not poetry |
| Linter | Ruff | All-green required |
| Type checker | mypy strict | All-green required |
| Tests | pytest | Run via `pytest tests/ -v` |
| Container | Docker multi-stage | Pinned `uv:0.11.2`, `python:3.12.13-slim-bookworm` |
| CI | GitHub Actions | Lint + typecheck + test + build + dashboard + docker |

**Things that are NOT in the stack despite appearances:**
- ❌ DuckDB — listed in `AGENTS.md:59` and `ADR-001` but **zero code uses it**. Will be removed in this cycle.
- ❌ A working `CacheStore` — `storage/cache.py` is path-computation only. Will be removed in this cycle.
- ❌ A wired `health/` package — exists but disconnected. **Decision: delete.**

---

## 5. Known Technical Debt (DO NOT REINTRODUCE)

The following four items are the **Tier 1 security debt** being resolved in Prompt 2 / Prompt 2A+2B:

### TD-1: Circular import (latent)
- **Where:** Between `connectors/` and `storage/`
- **Status as of cycle start:** Present, not fixed.
- **Constraint for agents:** Any new code must NOT add cross-imports between these packages. Use Protocol interfaces in a third location.

### TD-2: `DATA_GOV_SA_BASE_URL` hardcoded
- **Where:** `connectors/data_gov_sa.py` (or equivalent)
- **Status:** Hardcoded constant.
- **Constraint:** Must become env-configurable with HTTPS-only + hostname allowlist validation in `config.py`.

### TD-3: Rate limiting is in-memory only
- **Where:** Sliding-window implementation in `security/` layer.
- **Status:** Process-local. Not durable.
- **Constraint:** Document the limit boundary explicitly in `OPERATIONS.md`. Do not claim distributed rate limiting.

### TD-4: `snapshot_path` leaks filesystem layout
- **Where:** Response models in `tools/` (preview, query, download).
- **Status:** Raw filesystem path returned to MCP clients.
- **Constraint:** Replace with opaque `snapshot_id` (e.g., short hash). Internal mapping stays server-side. NO filesystem layout in any MCP-visible response.

---

## 6. Decision Log (Active Constraints)

These decisions are LOCKED for v0.4.0. Do not relitigate in commits or PR descriptions.

| ID | Decision | Implication for code |
|---|---|---|
| D-01 | Release = internal/evaluator alpha | No "production-ready" claims in README/docs/server.json |
| D-03 | **Delete** `health/` package | Remove the directory + update `AGENTS.md`, `ARCHITECTURE.md` |
| D-04 | **Delete** `CacheStore` placeholder | Remove from `storage/` + `storage/__init__.py` exports |
| D-05 | `resource://policies` stays hardcoded for now, data-driven in Wave 3 | Don't refactor yet |
| D-06 | Prompt 2 splits to 2A+2B if it touches >5 core files OR changes shared Protocols | Agent must self-report file count before edits |
| D-08 | Tier 4 (PDPL/licensing/Arabic+TZ) deferred to Wave 4 (pre-Saudi-review) | Don't add Saudi-specific docs in Waves 1–3 |

---

## 7. What Each Agent Must NOT Touch

Unless explicitly assigned, an agent must not modify:

- `pyproject.toml` dependency list — coordinate version bumps with the user, not unilateral additions.
- `Dockerfile` pinned versions — these are deliberately pinned.
- `tests/contracts/test_architecture_boundaries.py` — this is the boundary enforcer, not a test to "fix."
- `.github/workflows/*.yml` — except when explicitly adding the post-build smoke step (Prompt 1 territory).
- The `dashboard/` directory — out of scope for this cycle.

---

## 8. Test Discipline

- Tests live in `tests/` with subdirs: `unit/`, `integration/`, `contracts/`, `smoke/`.
- Fixtures in `tests/fixtures/{source}/{dataset_id}/`.
- **Before any code change:** run `pytest tests/ -v` and record the pass count.
- **After the change:** pass count must be ≥ baseline. New tests welcomed; no test deletions without justification.
- Architectural boundary tests are sacred. If they fail, the change is wrong.

**Test counting note:** The exact baseline at cycle start is **unverified** (reports vary between 219 and 475). Each agent must run the suite first and use the observed number as their personal baseline.

---

## 9. Code Style

- **Ruff** all-green. No `# noqa` without inline reason.
- **mypy strict** all-green. No `# type: ignore` without inline reason.
- **Docstrings:** required on public functions in `tools/`, `resources/`, `registry/`. One-line summary minimum.
- **Pydantic models:** match existing local model config: `extra="forbid"` is common on typed result/contract models; `frozen=True` is selective for immutable summaries/policies, not universal.
- **No print statements.** Use `log_event()` from `observability/logging.py`.
- **No bare `except:`.** Catch specific exceptions.

---

## 10. Commit & Branch Discipline

- **Default branch:** `main`.
- **Commits this cycle:** **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`). Even though the project's historical commits are free-form, this cycle uses Conventional Commits to make the audit pass (Prompt 10) easier. This is a temporary discipline, not a permanent project rule.
- **One concern per commit.** A "fix circular import + add config validation" commit is two commits.
- **Commit message body:** include WHY, not just WHAT, when the diff is non-obvious.
- **No force pushes** to main during this cycle.

---

## 11. Documentation Truthfulness

This cycle is partly motivated by **overclaim removal**. Concrete rules:

- If a feature is incomplete, the docs must say so or the feature must be removed.
- If a module looks production-ready but isn't, either wire it up or delete it.
- Avoid: "production-grade", "battle-tested", "fully observable" unless the evidence supports it.
- Prefer: "internal alpha", "evaluator preview", "fixture-backed", "process-local".
- Version/Wave/Phase terminology MUST be consistent across all docs (enforced in Prompt 6).

---

## 12. Wave Plan (Where We Are)

| Wave | Status | Contents |
|---|---|---|
| Wave 1 (sequential) | **Active** | Prompts 1 → 2 (or 2A+2B) → 3 → 4 |
| Wave 2 (parallel × 2 agents) | Pending | Agent A: Prompt 5 / Agent B: Prompt 6 + docs |
| Wave 3 (sequential) | Pending | Prompts 8 → 9 |
| Prompt 10 (audit) | Pending | Final security + release-gate review |
| Wave 4 (deferred) | Not started | Tier 4 — only before Saudi institutional review |

An agent receiving a task must know **which Wave they are in** and refuse work that belongs to a later Wave.

---

## 13. Failure Modes to Watch

These are recurring failure patterns in past contributions to this codebase:

1. **Helpful expansion.** Agent fixes the requested item and "improves" three nearby things. Result: review nightmare. **Stay scoped.**
2. **Documentation drift.** Code change without corresponding doc update. **Update docs in same commit.**
3. **Security as afterthought.** "I'll add validation in a follow-up." No follow-ups in this cycle. **Validate inputs in the same change.**
4. **Mock-driven testing.** Tests that mock so much they no longer exercise real behavior. **Prefer fixture files over mocks.**
5. **Reintroducing deleted concerns.** A later agent adds back something an earlier agent removed (e.g., DuckDB references). **Check Decision Log first.**

---

## 14. Saudi-Context Awareness (Cycle-Limited)

Tier 4 (PDPL, source licensing, Arabic + Asia/Riyadh tests) is **deferred** to Wave 4. However, agents in Waves 1–3 must still:

- NOT introduce English-only assumptions in error messages where Arabic content may flow through (e.g., dataset titles).
- NOT hardcode UTC where dataset semantics are local (e.g., business-day freshness windows).
- NOT add PII collection paths. The project handles **public open data only**.

If an agent encounters a clear PDPL or Arabic-handling concern, it must flag it in the PR description for Wave 4, not fix it inline.

---

## 15. Token & Time Budget

The user runs ~1M tokens/week across AI agents on this project. Be efficient:

- **Read once, edit precisely.** Don't re-read files you've already seen this session.
- **Batch related edits.** A single `str_replace` is cheaper than three.
- **Avoid speculative refactors.** "While I'm here, I'll also..." is the enemy of this cycle.
- **Stop when done.** Don't pad responses with "next steps I could take."

---

## 16. Final Reminder

> The user's pattern is **deep analysis outpaces shipping velocity**. This cycle is designed to ship in ~2 days. Every decision in this document is calibrated to that goal. If a task feels like it's expanding scope, it probably is. **Stop, ask, then proceed.**

---

**End of context.** If anything in this file conflicts with a task prompt, the task prompt takes precedence ONLY if the task prompt explicitly says "overrides AGENTS_TASK_CONTEXT.md section X". Otherwise, this document wins.
