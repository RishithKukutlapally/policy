# PolicyForge — System Design

| | |
|---|---|
| **Produced by** | `/design` planner (part A) |
| **Inputs** | `specs/app_spec.md`, the six feature specs `specs/*_spec.md`, `specs/stories/dependency-graph.md`, `specs/brd/brd.md` §7–§8, `docs/conventions.md` (canonical), `docs/decisions.md`, `.claude/architecture.md` |
| **Companions** | `specs/design/api-contracts.md` + `api-contracts.schema.json` (API), `specs/design/deployment.md` (environments, CI), `docs/architecture.md` (C4, sequences, NFR enforcement) |

Names, paths, enums, error codes and audit actions are used **verbatim** from `docs/conventions.md`.
Spec is truth: if this document disagrees with a spec, the spec wins and this document is corrected.

---

## 1. Context

PolicyForge is a single-instance, locally run policy administration system for three products
(`TERM_LIFE`, `MOTOR`, `HOUSEHOLD`). It has four kinds of actor — Customer, Underwriter, Admin and the
end-of-day Scheduler (`system-eod`, `ActorRole.SYSTEM`, DEC-010) — and **no real external systems**: KYC,
payment and authentication are internal stubs (BRD §10, brief §6.3).

```
Browser (React SPA :3000) ──HTTP/JSON + X-Actor-* headers──▶ FastAPI app (:8000) ──SQLAlchemy 2──▶ SQLite file
                                                                  │
                                                                  └── reads ▶ backend/policy_rules/<product>/v<N>.json + PUBLISHED.lock (seed import)
Scheduler / Admin "Run end-of-day" ──▶ end-of-day service (same process / same DB)
```

---

## 2. Components

| # | Component | Location | Responsibility |
|---|-----------|----------|----------------|
| C1 | **React SPA** | `frontend/` (React + Vite + TypeScript) | Screens: Get a Quote, Apply, My Policies, Policy Detail, Endorse, Renew/Pay, Cancel (refund preview), Underwriter Workbench, Admin Underwriting Review, Product Catalog Manager, Portfolio Dashboard, Run end-of-day. Header **role switcher** sets `X-Actor-Id` / `X-Actor-Role` for the demo users `cust-001`, `uw-001`, `admin-001`. Money rendered from strings with `en-IN` formatting (₹). Responsive at 1280 px and 390 px (AC-24). |
| C2 | **FastAPI application** | `backend/src/main.py` → `src.main:app` | Wires middleware (correlation id, JSON logging, error envelope), mounts routers under `/api`, exposes un-prefixed `GET /health`. |
| C3 | **API layer** | `backend/src/api/` — `routers/<resource>.py`, `deps.py`, `middleware.py` | Request/response mapping (Pydantic), role-header auth stub (`Actor(actor_id, role)`), role checks per route (NFR-04, AC-22), owner scoping (other customer → 404), typed-error → HTTP mapping. Never imports `repository`. |
| C4 | **Service layer** | `backend/src/service/<use_case>_service.py` | Use cases and transactions: catalog, quote, application, underwriting, issuance, endorsement, payment, end-of-day, cancellation, portfolio. Writes `audit_records` for UNDERWRITER/ADMIN/`system-eod` actions. All status changes go through the domain state machine. |
| C5 | **Domain layer** | `backend/src/domain/` — `premium_calculator.py`, `application_validator.py`, `underwriting_rules.py`, `policy_state_machine.py`, `endorsement_rules.py`, `renewal_rules.py`, `refund_rules.py` | Pure `Decimal` functions of `(RuleSet, inputs, dates)`. No I/O, logging, clock, randomness or `float`. Deterministic (AC-01). |
| C6 | **Config layer** | `backend/src/config/` — `settings.py`, `rule_loader.py` | Typed `Settings` (`renewal_window_days` 30, `database_url` `sqlite:///./policyforge.db`, `api_port` 8000, `ui_port` 3000); rule-file parsing + JSON-schema validation (file/body → `RuleSet`). |
| C7 | **Repository layer** | `backend/src/repository/` — `models.py`, `<entity>_repository.py` | SQLAlchemy 2 models for the 11 canonical tables; append-only repositories expose `add(...)` + reads only, backed by a before-flush guard that rejects `UPDATE`/`DELETE` on append-only tables. |
| C8 | **Types layer** | `backend/src/types/` — `enums.py`, `errors.py`, `rules.py` | Enums (`ProductCode`, `PolicyStatus`, `ApplicationStatus`, `Decision`, `EndorsementType`, `ActorRole`, `RefundType`, `EndOfDayAction`, `UnderwriterDecision`), typed errors incl. `InvalidPolicyStateException`, `RuleSet` value objects. |
| C9 | **lib (cross-cutting)** | `backend/src/lib/` — `logging.py` (`get_logger`, `mask_pii`), `correlation.py` | Standard-library-only JSON logger with PII masking and correlation-id context. Importable by config/repository/service/api; **not** by types/domain. |
| C10 | **SQLite database** | `backend/policyforge.db` (from `database_url`, relative to the backend working dir) | Single file, single writer. Money `Numeric(12, 2)`, rates `Numeric(9, 6)`. |
| C11 | **Alembic migrations** | `backend/migrations/versions/*.py` | Append-only schema history (NFR-05); `alembic upgrade head` on every start. |
| C12 | **Rule files + ledger** | `backend/policy_rules/<term_life\|motor\|household>/v<N>.json`, `backend/policy_rules/schema/rule-file.schema.json`, `backend/policy_rules/PUBLISHED.lock` | Versioned product rules (money/rates as JSON strings). `PUBLISHED.lock` holds `<sha256>  <folder>/v<N>.json` per published file; append-only; re-hashed by the architecture test. Imported into `rule_set_versions` by `python -m src.seed`. |
| C13 | **Seed** | `backend/src/seed.py` (`python -m src.seed`) | Idempotent: imports the three v1 rule files, then creates synthetic demo data (≥ 20 applications through the services, ≥ 70 % `AUTO_BIND`, sample policies) — synthetic Aadhaar `9999…`, PAN `AAAAA####A`. |
| C14 | **End-of-day job** | `src/service/end_of_day_service.py` — `run_end_of_day(as_of, actor_id)` | Evaluates every `ACTIVE`/`ENDORSED` policy with `renewal_rules.renewal_action` → `RENEW` / `IN_GRACE` / `LAPSE` / `NONE`; one transaction per policy; idempotent; one `RUN_END_OF_DAY` audit row per run. Triggered by the admin endpoint `POST /api/admin/end-of-day` (actor = admin) or by the scheduler (actor `system-eod`, role `SYSTEM`; invocation path still to be specified — `api-contracts.md` OI-6). |

### 2.1 Router ↔ service map

| Router (`src/api/routers/`) | Endpoints | Service(s) |
|------|-----------|-----------|
| `health` (in `main.py` or `routers/health.py`) | `GET /health` | — |
| `products.py` | `/api/products…` (5) | `catalog_service` |
| `quotes.py` | `/api/quotes…` (3) | `quote_service` |
| `applications.py` | `POST /api/applications`, `GET /api/applications/{id}` | `application_service` |
| `underwriting.py` | `/api/underwriting/…` (4) | `underwriting_service` |
| `policies.py` | `POST /api/applications/{id}/issue`, `GET /api/policies`, `GET /api/policies/{n}` | `issuance_service`, `policy_query_service` |
| `endorsements.py` | `POST /api/policies/{n}/endorsements` | `endorsement_service` |
| `renewals.py` | `GET …/renewal`, `POST …/renew`, `POST …/payments` | `payment_service`, `renewal_service` |
| `cancellations.py` | `GET …/cancellation-preview`, `POST …/cancel` | `cancellation_service` |
| `admin.py` | `POST /api/admin/end-of-day`, `GET /api/admin/portfolio` | `end_of_day_service`, `portfolio_service` |

Router file names for `renewals.py` and the service names `policy_query_service` / `renewal_service` /
`payment_service` are design choices within the `src/api/routers/<resource>.py` and
`src/service/<use_case>_service.py` conventions.

### 2.2 Persistence

The 11 canonical tables (`docs/conventions.md` → Persistence): `rule_set_versions` ✅, `quotes`,
`applications` (status projection), `underwriting_decisions` ✅, `underwriting_overrides` ✅, `policies`
(current projection), `policy_state_transitions` ✅, `endorsements` ✅, `premium_payments` ✅, `refunds` ✅,
`audit_records` ✅ (✅ = append-only). Mutable rows are limited to the two projections (`applications.status`,
`policies.*`) — every change to them is accompanied, in the same transaction, by an append-only history row.

Key uniqueness constraints:

| Table | Constraint | Why |
|-------|-----------|-----|
| `rule_set_versions` | unique (`product`, `version`, `status`) + per-product "one open DRAFT" check in service | DRAFT → PUBLISHED inserts a new row; latest row = current state |
| `policies` | unique `policy_number`; unique `previous_policy_number` (nullable) | Number allocation; idempotent renewal backstop (AC-18) |
| `premium_payments` | unique (`policy_id`, `due_date`) | `PREMIUM_ALREADY_PAID` |
| `applications` | one policy per application (issued-once check + `policies.application_id` unique) | AC-05 "at most one policy" |

### 2.3 Business date

Domain functions never read the clock (NFR-08). The API/service composition provides a **business date**
(server local date by default, injectable in tests via FastAPI dependency override). Endpoints whose AC fixes
a date take it explicitly: `as_of` (end-of-day, portfolio), `date` (cancellation preview),
`cancellation_date` (cancel). Issuance, endorsement, payment and early renewal use the business date.

---

## 3. Data flows

### 3.1 Quote-to-bind (AC-01, AC-03, AC-04, AC-05, AC-13)

1. **Quote** — `POST /api/quotes {product, inputs}` (CUSTOMER).
   `catalog` resolves the product's **active version** (highest `PUBLISHED`); none → 409
   `NO_PUBLISHED_VERSION` (no fallback). Inputs validated against `eligibility` and factor tables → 422 with all
   failing fields. `premium_calculator` computes `raw` in full `Decimal`, `max(raw, minimum_premium)`,
   quantized once to `0.01` `ROUND_HALF_UP`. A `quotes` row stores `product`, `rule_version`, inputs,
   `sum_insured`, `premium`, `actor_id`. Response money as strings (`"14322.00"`).
2. **Application** — `POST /api/applications {quote_id, kyc, health_declaration?}` (CUSTOMER, quote owner).
   Quote's `rule_version` ≠ active → 409 `QUOTE_STALE`. KYC validated (Aadhaar 12 digits, PAN pattern), masked
   (`XXXX-XXXX-0001`, `XXXXX0001X`) before persistence; raw values never logged or stored.
   Application inserted `SUBMITTED` → `UNDERWRITING` (status history kept).
3. **Automatic underwriting** — `underwriting_rules` evaluates `underwriting.rules[].when` on quote inputs +
   derived fields; precedence `DECLINE` > `MANUAL_REVIEW` > `AUTO_BIND`; reason codes = all matching, sorted.
   Appends `underwriting_decisions` (`decided_by = "SYSTEM"`, `rule_version`) and moves the application to
   `AUTO_BIND` / `MANUAL_REVIEW` / `DECLINED` — same transaction.
4. **Manual decision / override** (only if referred or declined) — underwriter
   `POST /api/underwriting/applications/{id}/decision` (`APPROVE` → `AUTO_BIND`, `DECLINE` → `DECLINED`; audit
   `UW_APPROVE` / `UW_DECLINE`), or admin `POST …/override` on `DECLINED` → `AUTO_BIND` (append
   `underwriting_overrides` + audit `UW_OVERRIDE_DECLINE`). Reason codes must exist in the case's rule version.
5. **Issue** — `POST /api/applications/{id}/issue` (owner CUSTOMER or ADMIN). Application must be `AUTO_BIND`
   (else 409 `INVALID_APPLICATION_STATE`). In one transaction: allocate `<TL|MO|HH>-<YYYY>-<seq>`, insert
   `policies` (`ACTIVE`, premium = quote premium, `rule_version` = quote version, `expiry_date` =
   `effective_date + term_months − 1 day`), append `policy_state_transitions` (`null → ACTIVE`, reason `ISSUED`),
   append first-term `premium_payments` (`due_date = effective_date`), application → `ISSUED`, audit
   `POLICY_ISSUED` if ADMIN.

### 3.2 Endorsement (AC-06, AC-16)

`POST /api/policies/{n}/endorsements[?preview=true]` (owner CUSTOMER or ADMIN). Rules come from the policy's
own `rule_version`. `endorsement_rules` checks `type ∈ endorsement.allowed_types`, validates the payload
(address / nominee shares ≤ 100 / new sum insured within eligibility and changed), and for
`CHANGE_SUM_INSURED` recomputes the full-term premium and
`premium_delta = (new − old) × unused_days / term_days` (quantized once). Preview returns 200 and persists
nothing. Otherwise one transaction: state machine (`ACTIVE|ENDORSED → ENDORSED`), append `endorsements`
(before/after JSON, `premium_delta`), update `policies` projection, append `policy_state_transitions`
(reason `ENDORSEMENT:<type>`), audit `ENDORSEMENT_CREATED` if ADMIN. Any failure → full rollback.

### 3.3 Renewal payment and end-of-day (AC-07, AC-17, AC-18)

1. `GET …/renewal` quotes the renewal premium on the **active** version with advanced ages /
   `vehicle_age_years`; `due_date = expiry_date + 1`, `grace_end_date = due + grace_period_days`;
   `renewable` false if ineligible.
2. `POST …/payments {amount}` inside the renewal window (`expiry − renewal_window_days` … grace end) appends a
   `premium_payments` row with the quoted `rule_version`; amount must equal the quote (`AMOUNT_MISMATCH`), one
   per due date (`PREMIUM_ALREADY_PAID`).
3. `run_end_of_day(as_of, actor)` for each `ACTIVE`/`ENDORSED` policy, in its own transaction:
   `RENEW` (paid, `as_of ≥ due`) → old policy `RENEWED` + successor policy `ACTIVE` (new number,
   `previous_policy_number`, premium/version from the payment, two transition rows); `LAPSE` (unpaid,
   `as_of > grace end`) → `LAPSED` (reason `GRACE_PERIOD_EXPIRED`); `IN_GRACE` / `NONE` → no change;
   ineligible → `not_renewable`. A per-policy failure is logged (no PII) and reported in `failed`; the run
   continues. Idempotency is structural (terminal statuses + unique `previous_policy_number`). One
   `RUN_END_OF_DAY` audit row per run with `as_of` + counts.
4. `POST …/renew` is the customer's early renewal: same successor logic for one policy, only inside the
   window and only when the renewal premium is paid.

### 3.4 Cancellation (AC-08, AC-19)

`GET …/cancellation-preview?date=` and `POST …/cancel {cancellation_date, reason}` share `refund_rules` on the
policy's own version: `FREE_LOOK` (new business, `days_elapsed ≤ free_look_days`) refunds the premium paid in
full; otherwise `PRO_RATA = max(premium_paid × unused_days / term_days − admin_fee, 0.00)`. Date outside the
term → 422 (`OUTSIDE_TERM`). Cancel in one transaction: state machine (`→ CANCELLED`, terminal policies → 409
`INVALID_POLICY_STATE`), append `refunds`, update projection, append transition, audit `POLICY_CANCELLED` if
ADMIN. Preview persists nothing.

### 3.5 Rule-set publishing (AC-11)

Admin `POST /api/products/{p}/versions` (DRAFT, version = max + 1, one open DRAFT per product),
`PUT …/versions/{v}` (replace an open DRAFT by appending a new row, DEC-009), `POST …/versions/{v}/publish`
(re-validate, append a `PUBLISHED` row, audit). Active version = highest `PUBLISHED`. File-based rule versions
enter via a new `v<N>.json` + a new `PUBLISHED.lock` line + seed import; the architecture test re-hashes all
ledger entries.

---

## 4. Key decisions and rationale

| Decision | Rationale | Reference |
|----------|-----------|-----------|
| **Rules as versioned data** (JSON rule files + append-only `rule_set_versions`, interpreted by pure `Decimal` domain functions) | Only option meeting AC-01 (premium from a versioned rule file), AC-02 (distinct rule sets) and brief §6.2 (catalog changes without code) while staying deterministic and testable. | BRD §7 **Alternative A (chosen)** |
| Reject hard-coded product classes | Every rate change would be a code change and a deploy — violates AC-01 / §6.2. | BRD §7 **Alternative B (rejected)** |
| Reject a generic rules engine / DSL | Runtime expressions weaken `Decimal` and determinism guarantees and add complexity not needed for three products; instead a deliberately tiny `when` grammar (`<field> <op> <value>` joined by ` and `). | BRD §7 **Alternative C (rejected)** |
| **Stack: Python FastAPI + React (Vite) + SQLite**, local dev-server verification | SQLite keeps `npm start` dependency-free; FastAPI + Pydantic give typed request validation; Python `decimal` gives exact money. | **DEC-001** |
| **`PUT /api/products/{product}/versions/{version}` replaces an open DRAFT** by appending a new row; PUBLISHED stays immutable (409 `VERSION_IMMUTABLE`) | Without it a bad DRAFT would block every new draft (`DRAFT_ALREADY_OPEN`); delete-and-recreate would violate append-only. | **DEC-009** |
| **Internal `ActorRole.SYSTEM`** for the scheduler (`system-eod`), never accepted from `X-Actor-Role` (401) | Scheduler audit rows need a valid actor (NFR-04) without reusing ADMIN, which would blur accountability. | **DEC-010** |
| Strict one-way layering with a separate pure **Domain** layer and a stdlib-only **lib** | Makes premium/underwriting math deterministic and unit-testable; enforced by import-linter + architecture tests (NFR-08). | `.claude/architecture.md`, conventions "Layer import rules" |
| Append-only history + mutable projections (`applications`, `policies`) | Full reproducibility and audit (NFR-02) while keeping reads simple; every projection update is paired with an append-only row in one transaction. | NFR-02, BRD §9 |
| Role-header auth stub checked only in `src/api/deps.py` | Brief puts real auth out of scope; keeping the boundary at the controller layer is what the rubric/AC-22 test. | NFR-04, BRD §8 |
| Money as JSON strings, `Decimal`, quantize once `ROUND_HALF_UP` | Avoids float drift and banker's rounding (`3000.625 → 3000.63`). | NFR-01 |
| Idempotent end-of-day by **structure** (terminal states + unique `previous_policy_number`), not a run ledger | Simple, restart-safe, no distributed lock needed on a single instance (brief §6.3). | AC-18 |
| Renewal = new policy row, old → `RENEWED` | Keeps each term's premium/version immutable and cancellation/refund math term-local. | A-RC-7 |

---

## 5. Non-functional summary

| NFR | Mechanism (details in `docs/architecture.md` §6) |
|-----|------|
| NFR-01 money | `Decimal` + `Numeric(12,2)`; hook `premium-precision-check`; arch test "no float" |
| NFR-02 append-only | `add` + reads repositories; before-flush guard; hook `append-only-repository-check`, `policy-immutability-check` |
| NFR-03 PII | `mask_pii`, masked columns only; hook `pii-redaction-check`; log-capture tests |
| NFR-04 auth + audit | `deps.py` role dependencies; `audit_records` rows with actor id/role |
| NFR-05 migrations | new Alembic revisions only; new `v<N>.json` + `PUBLISHED.lock` lines |
| NFR-06 logs | JSON lines with `correlation_id`; `X-Correlation-ID` on every response |
| NFR-07 health | `GET /health` → `{"status": "ok"}` < 1 s after startup |
| NFR-08 arch tests | import-linter contracts + `backend/tests/architecture/`, CI `backend-test` |

Performance targets: `POST /api/quotes` < 2 s p95 (BRD M1); `GET /api/admin/portfolio` < 500 ms p95 on seed
data (E9-S1). Single instance; no rate limiting (local demo, brief §6.3).
