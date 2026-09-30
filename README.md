# PolicyForge

PolicyForge is a policy issuance and lifecycle management platform for Horizon Insurance. It takes a
customer from quote to application, underwriting decision, issuance, endorsement, renewal and
cancellation, and prices every step from a **versioned rule set** so an in-force policy is always
rated on the rule file it was sold under. Every premium, refund and delta is `Decimal`; policy
versions, state transitions, payments, refunds and audit rows are append-only.

Three products ship with a published `v1` rule set:

| Product | Code | Rule file | Reason codes |
|---------|------|-----------|--------------|
| Term Life | `TERM_LIFE` | `backend/policy_rules/term_life/v1.json` | `TL-UW-###` |
| Motor | `MOTOR` | `backend/policy_rules/motor/v1.json` | `MO-UW-###` |
| Household | `HOUSEHOLD` | `backend/policy_rules/household/v1.json` | `HH-UW-###` |

## Quick start

**Prerequisites:** Node 20+, Python 3.12+, and [`uv`](https://docs.astral.sh/uv/).

```bash
npm start
```

That single command installs the backend dependencies (`uv sync`), applies the database migrations
(`alembic upgrade head`), seeds the demo data (`python -m src.seed`), then runs both processes:

- API — <http://localhost:8000> · health check <http://localhost:8000/health>
- UI — <http://localhost:3000>

The UI installs its own npm dependencies on first run. Press `Ctrl+C` to stop both. Useful
variants: `npm run dev:api` (API only), `npm run dev:ui` (UI only), `npm run migrate`
(install + migrate + seed, then exit).

### Demo users

There is no login: the API reads the actor from the `X-Actor-Id` and `X-Actor-Role` request
headers. The **role switcher** in the UI header sets both, so switching role instantly changes the
navigation and what the API will authorise.

| Role | `X-Actor-Id` | `X-Actor-Role` | Sees |
|------|--------------|----------------|------|
| Customer | `cust-001` | `CUSTOMER` | Get a Quote, My Policies |
| Underwriter | `uw-001` | `UNDERWRITER` | Workbench (manual-review queue) |
| Admin | `admin-001` | `ADMIN` | Product Catalog, Underwriting Review, Portfolio, End of day |

`cust-001` owns the whole lifecycle showcase, so the customer screens are never empty. Extra
seeded customers `cust-002` … `cust-005` own the remaining quotes and applications.

### Seeded demo data

The seed drives the real services — nothing is inserted directly — from a **fixed business date of
2026-07-01**, so the renewal and lapse dates are identical on every machine:

- 3 `PUBLISHED` v1 rule sets, one per product;
- 25 quotes and 25 applications, **21 `AUTO_BIND` (84 %)**, 3 `MANUAL_REVIEW` waiting in the
  underwriter workbench and 1 `DECLINE` waiting for an admin override;
- 7 policies covering every lifecycle status — 3 `ACTIVE` (Motor, Household and a renewal term),
  1 `ENDORSED`, 1 `RENEWED` with its successor, 1 `LAPSED` and 1 `CANCELLED` with its refund row;
- the matching state transitions, endorsement, premium payments and audit records.

All personal data is synthetic: names are `Test Customer NN`, Aadhaar numbers start `9999`, PANs
follow `AAAAA0001A`, and only **masked** values (`XXXX-XXXX-0001`, `XXXXX0001X`) are stored or
logged. Re-running `python -m src.seed` inserts nothing — it is idempotent.

## Guided tour

Start at <http://localhost:3000> and follow the seeded data:

1. **Get a quote** — as *Customer*, open **Get a Quote**, pick Motor, and price it. The premium
   comes from the active `MOTOR v1` rule file; nothing else can change it.
2. **Apply** — submit the quote with synthetic KYC (Aadhaar `999900000099`, PAN `AAAAA0099A`).
3. **See the decision** — a clean risk returns `AUTO_BIND`. Try a vehicle older than 10 years for
   `MANUAL_REVIEW` (`MO-UW-002`), or Term Life with age + term over 75 for a `DECLINE`
   (`TL-UW-001`).
4. **Underwrite** — switch to *Underwriter* and open **Workbench**: the 3 seeded manual-review
   cases are there. Approve or decline one with a reason code. As *Admin*, **Underwriting Review**
   lets you override the seeded declined case (`…-UW-901`), which is audited with your actor id.
5. **Issue** — back as *Customer*, issue an `AUTO_BIND` application. The policy number looks like
   `MO-2026-000007` and the first-term premium is recorded as paid.
6. **Endorse** — open the `ENDORSED` policy under **My Policies** and change the address or sum
   insured. Preview first: the pro-rata delta is stored on the endorsement, never collected.
7. **Renew** — the seeded `RENEWED` policy shows its successor term and the payment that unlocked
   it. On an `ACTIVE` policy the renewal quote opens 30 days before expiry.
8. **Cancel** — the seeded `CANCELLED` policy carries its free-look refund; try
   **cancellation preview** on an active one to see the pro-rata figure minus the admin fee.
9. **Admin catalog and portfolio** — as *Admin*, **Product Catalog** creates, replaces and
   publishes rule-set versions (a published version is immutable). **Portfolio** aggregates
   in-force cover, premium, the renewal pipeline and the lapse forecast.
10. **End of day** — **End of day** (or the CLI below) runs the renew / grace / lapse cycle for a
    chosen date. It is idempotent, so re-running the same date changes nothing.

## Running the tests

```bash
cd backend && uv run pytest          # unit, integration, AC and architecture tests
cd frontend && npm test              # Vitest component tests
npm run e2e                          # Playwright end-to-end (from the repo root)
```

Backend coverage is printed to the terminal (`--cov-report=term-missing`) and written to
`backend/coverage.xml`; the Playwright HTML report lands in `e2e/playwright-report`
(`npm run e2e:report`). Other checks:

```bash
cd backend  && uv run ruff check . && uv run mypy src/ && uv run lint-imports
cd frontend && npm run lint && npm run typecheck
```

Run the end-of-day cycle for an explicit business date:

```bash
cd backend && uv run python -m src.jobs.end_of_day --as-of 2026-07-02
```

That date is the one the seed uses to lapse its unpaid term. Any date works; the run acts as
`system-eod` and writes one audit row with the counts. To make the whole application believe it is
a different day, set `POLICYFORGE_BUSINESS_DATE=YYYY-MM-DD` — every layer reads "today" through
`backend/src/lib/clock.py`.

## Project structure

| Path | What lives there |
|------|------------------|
| `backend/src/types/` | Enums, typed errors, rule-set value objects |
| `backend/src/domain/` | Pure rules: premium, underwriting, state machine, refunds, renewal |
| `backend/src/config/` | Settings and rule-file loading / schema validation |
| `backend/src/repository/` | SQLAlchemy models and append-only repositories |
| `backend/src/service/` | Use cases: quote, application, underwriting, policy, endorsement, renewal, payment, cancellation, portfolio |
| `backend/src/api/` | FastAPI routers, dependencies, error envelope, DTOs |
| `backend/src/jobs/` | End-of-day renewal / lapse cycle |
| `backend/src/seed.py`, `backend/src/seed_data/` | Idempotent seed and its synthetic demo data |
| `backend/policy_rules/` | Versioned rule files plus `PUBLISHED.lock` |
| `backend/migrations/` | Append-only Alembic revisions |
| `backend/tests/` | `unit/`, `integration/`, `ac/`, `architecture/` |
| `frontend/src/` | React + TypeScript UI (`pages/`, `api/`, `app/` shell and role switcher) |
| `e2e/` | Playwright end-to-end suite |
| `specs/`, `docs/` | Specifications, stories, decisions and reviews |
| `scripts/start.mjs` | The cross-platform launcher behind `npm start` |

Dependencies run one way only: Types → Domain → Config → Repository → Service → API → UI, enforced
by import-linter and the tests in `backend/tests/architecture/`.

## Documentation

- [Business case](docs/business-case.md) — the problem, scope and success metrics
- [Application spec](specs/app_spec.md) — acceptance criteria and the story index
- [Architecture](docs/architecture.md) — layers, data flow and key decisions
- [Conventions](docs/conventions.md) — canonical names, paths, formats and endpoints
- [TDD guide](docs/tdd.md) — the red-green-refactor workflow this project follows

## How this project was built

All production code, tests and migrations in this repository were **generated by Claude Code
agents** under human supervision. Humans edit only the substrate — specs, `CLAUDE.md` files, agent
and skill definitions, commands, hooks and docs — and regenerate the code from it. When spec and
code disagree, the spec wins: update the spec, then regenerate. See `AGENTS.md` and
`.claude/program.md` for the pipeline and its control knobs.
