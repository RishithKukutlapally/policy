# PolicyForge — Deployment

| | |
|---|---|
| **Decision** | DEC-001 — FastAPI + React (Vite) + SQLite, verified on **local dev servers** (no containers, no cloud) |
| **CI** | GitLab CI, `.gitlab-ci.yml` (stages `test` → `build` → `review`) |
| **Out of scope** | Production deployment, secret management, multi-region, distributed locking (brief §6.3) |

## 1. Environments

| Environment | Where | Purpose | Data |
|-------------|-------|---------|------|
| **Local dev** | Developer laptop (Windows / macOS / Linux) | Build, run, demo, harness `/evaluate` (Playwright MCP) | `backend/policyforge.db` (SQLite), synthetic seed |
| **Test (pytest)** | Local + CI `backend-test` | Unit / service / API / architecture tests | Temporary SQLite files or in-memory DBs per test; `DATABASE_URL` overridden |
| **CI** | GitLab runners (Docker images `python:3.12-slim`, `node:22`, `mcr.microsoft.com/playwright:v1.63.0-noble`) | Merge-request and branch pipelines | Throw-away SQLite created by `npm run e2e` |

There is **no staging or production** environment — by design (brief §6.3). The build stage produces
artefacts (`backend/dist/`, `frontend/dist/`) that prove the app builds; nothing is deployed.

### 1.1 Local dev — one command

Prerequisites: Python 3.12, `uv`, Node 20+ (CI uses Node 22).

```
npm start
```

In order (E1-S1 AC-6, E9-S3):

1. `cd backend && uv sync` — install backend dependencies (locked).
2. Install frontend dependencies (`npm ci` in `frontend/`).
3. `uv run alembic upgrade head` — apply migrations from `backend/migrations/versions/` (idempotent; a second
   run is a no-op).
4. `uv run python -m src.seed` — idempotent: imports `term_life/v1.json`, `motor/v1.json`, `household/v1.json`
   into `rule_set_versions` (each must match its `PUBLISHED.lock` line) and creates synthetic demo data
   (≥ 20 applications through the services, ≥ 70 % `AUTO_BIND`, sample policies). Re-running adds no rows.
5. Start the API: `uv run uvicorn src.main:app --port 8000` (`api_port`).
6. Start the UI: Vite dev server on port 3000 (`ui_port`), proxying `/api` and `/health` to `:8000`.

Readiness: `GET http://localhost:8000/health` → `200 {"status": "ok"}` within 1 s of startup (NFR-07);
`http://localhost:3000` serves the SPA. Demo users (role switcher): `cust-001` CUSTOMER, `uw-001` UNDERWRITER,
`admin-001` ADMIN. `init.sh` is the harness bootstrap equivalent used by `/evaluate`.

### 1.2 SQLite file

| Setting | Default | Resolves to |
|---------|---------|-------------|
| `database_url` (`DATABASE_URL`) | `sqlite:///./policyforge.db` | `backend/policyforge.db` (the API, Alembic and seed all run with `backend/` as working directory) |

- The DB file is git-ignored; delete it to reset the demo, then `npm start` recreates, migrates and seeds it.
- Single process, single writer; SQLite's file lock is sufficient (no distributed locking, brief §6.3).
- Tests never touch `backend/policyforge.db`; they override `DATABASE_URL`.

## 2. Configuration and secrets

| Name | Used by | Default / source | Secret? |
|------|---------|------------------|---------|
| `DATABASE_URL` | backend | `sqlite:///./policyforge.db` | no |
| `API_PORT` | `npm start` | `8000` | no |
| `UI_PORT` | `npm start` | `3000` | no |
| `RENEWAL_WINDOW_DAYS` | backend (`renewal_window_days`) | `30` | no |
| `ANTHROPIC_API_KEY` | CI job `claude-review` **only** | GitLab → Settings → CI/CD → Variables, flags **Masked** and **Protected** | **yes — the only secret** |

- The application itself needs **no secrets**: auth is the role-header stub, KYC/payment are internal stubs,
  data is synthetic.
- Pricing and lifecycle numbers (rates, grace, free look, admin fee, term) are **never** configuration — they live
  in versioned rule files (`backend/policy_rules/<product>/v<N>.json`).
- `ANTHROPIC_API_KEY` is Protected, so it only reaches pipelines on protected refs; MR source branches are
  protected with wildcard rules (`feat/*`, `chore/*`, `fix/*`). Without the variable, `claude-review` is skipped.
- `.env` (if created from `.env.example` by `init.sh`) is git-ignored and must contain no real credentials.

## 3. CI/CD pipeline (`.gitlab-ci.yml`)

Pipelines run for merge requests, and for branch pushes only when no MR is open (no duplicates). Tool versions
are pinned: `UV_VERSION 0.12.19`, `CLAUDE_CODE_VERSION 2.1.284`, `PLAYWRIGHT_IMAGE_TAG v1.63.0-noble`;
`uv`/`npm` caches keyed by branch.

```
test ──────────────────────────────────────────────┐
  backend-test   (if backend/pyproject.toml)       │
  hook-selftest  (always)                           ├─▶ build (if backend/pyproject.toml & frontend/package.json)
  frontend-test  (if frontend/package.json)        │
  e2e-test       (if package.json & e2e/playwright.config.ts)
review ─ claude-review (MR pipelines with ANTHROPIC_API_KEY only; needs: [])
```

| Stage | Job | Image | Steps | Gate (NFR) |
|-------|-----|-------|-------|------------|
| test | `backend-test` | `python:3.12-slim` | `uv sync --frozen` → `ruff check .` → `mypy src/` → `lint-imports` → `pytest --cov=src` (JUnit + Cobertura artefacts) | Layering contracts + architecture tests (NFR-08, NFR-01/02/05 arch tests, `PUBLISHED.lock` re-hash), AC tests, coverage |
| test | `hook-selftest` | `node:22` | `node .claude/hooks/tests/run-hook-tests.js` | Guard hooks block/allow cases (NFR-01/02/03/05) |
| test | `frontend-test` | `node:22` | `npm ci` → `npm run lint` → `npm run typecheck` → `npm test -- --run --coverage` | Zero `any`, unit tests |
| test | `e2e-test` | Playwright `v1.63.0-noble` | install `uv` → `npm ci` → `npm run e2e` (boots API + UI, runs Playwright journeys + snapshots at 1280 / 390 px) | AC-24 and E2E `AC-NN` titles |
| build | `build` | `node:22` | `uv build` (backend wheel/sdist → `backend/dist/`), `npm ci && npm run build` (→ `frontend/dist/`); artefacts kept 1 week | App builds |
| review | `claude-review` | `node:22` | Restore `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `docs/conventions.md` from the **target** branch; run Claude Code headless, read-only (Read/Grep/Glob; Bash/edits/web/MCP/hooks disabled) over `mr.diff`; fail on secret-like tokens; pass only if the last line is `VERDICT: PASS` | NFR-01…05 + layering + AC tagging review |

Jobs switch on as each part of the app lands (`rules: exists`), so early sprints run only `hook-selftest`.

### 3.1 Merge flow (DEC-008)

Work happens on `<type>/<description>` branches (never on `main`). `/sprint-close` produces the review verdicts;
branches are pushed from the office machine and merged through GitLab Merge Requests using the merge-commit
method (= `--no-ff`) once the pipeline is green. There is no automatic deployment after merge.

## 4. Infrastructure as code

Not applicable: no provisioned infrastructure. The reproducible definitions are:

- `.gitlab-ci.yml` (pipeline, pinned images and tool versions),
- `backend/pyproject.toml` + `uv.lock` (backend dependencies, `uv sync --frozen`),
- `frontend/package.json` + `package-lock.json` and root `package.json` (`npm ci`),
- Alembic revisions in `backend/migrations/versions/` (schema),
- rule files + `PUBLISHED.lock` in `backend/policy_rules/` (product configuration).

## 5. Migrations, seed and rule versions on start

| Artefact | Change process | On start |
|----------|----------------|----------|
| DB schema | New Alembic revision only (`uv run alembic revision -m "<change>"`); committed revisions are never edited or deleted (NFR-05; hooks `policy-immutability-check`, `shell-immutability-check`; `migration-coherence-agent`) | `alembic upgrade head` |
| Product rules | New `v<N>.json` + new `PUBLISHED.lock` line (`/publish-policy-version`), or admin DRAFT → publish through the API (append-only `rule_set_versions`) | Seed imports file versions not yet present |
| Demo data | `backend/src/seed.py` | `python -m src.seed` (idempotent) |

## 6. Rollback

Everything that matters is **append-only**, so rollback is **fix-forward**:

| What went wrong | Rollback procedure |
|-----------------|--------------------|
| Bad code merged | Revert the merge commit on a new branch (`git revert -m 1 <merge>`), MR, pipeline green, merge. |
| Bad migration merged | **Never** edit or delete it. Add a new revision that reverses the effect (e.g. adds back a column, creates a corrective table). Append-only tables are never dropped. Locally, a developer may delete `backend/policyforge.db` and re-run `npm start`. |
| Bad rule version published (file) | Never edit a PUBLISHED file (arch test re-hashes `PUBLISHED.lock`). Publish `v<N+1>` restoring the previous values; it becomes the active version. Quotes/policies on the bad version stay reproducible. |
| Bad rule version published (admin API) | Create and publish a new DRAFT with corrected values. |
| Bad DRAFT | Replace it with `PUT /api/products/{product}/versions/{version}` (DEC-009) — appends a new row. |
| Wrong end-of-day run | Runs are idempotent; transitions are terminal and append-only. Corrections require a new, explicitly specified compensating action (not in MVP scope). |
| Demo DB corrupted | Delete `backend/policyforge.db`; `npm start` re-migrates and re-seeds. |

## 7. Production concerns explicitly out of scope (brief §6.3)

- Production / cloud deployment, containers in production, TLS, domains, CDN.
- Secret management beyond the single CI variable (no vault, no key rotation).
- Multi-region, high availability, horizontal scaling, backups/DR of the SQLite file.
- Distributed locking / concurrent end-of-day runs (single instance; idempotency is structural).
- Real authentication/identity provider, real KYC, bureau/health/vehicle-record, and payment-gateway
  integrations (all internal stubs).
- Reinsurance, distribution channels, broker commission.
- Rate limiting and WAF.
