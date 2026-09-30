# Dependency Graph — PolicyForge

Produced by `/spec` from the approved BRD (`specs/brd/brd.md`). Stories are executed **sprint by sprint**;
inside a sprint, groups run in order and stories within a group are independent (parallelisable).
No story depends on a story in the same group or in a later sprint.

Layers: `Types | Domain | Config | Repository | Service | API | UI` (PolicyForge adds Domain).

## Global acceptance criteria (stable IDs)

AC-01…AC-10 are the brief's criteria verbatim in meaning; AC-11…AC-24 are added by this spec.

| AC | Criterion (short) | Owning spec | Stories |
|----|-------------------|-------------|---------|
| AC-01 | Deterministic premium for product + insured profile from the active versioned rule file | quote-engine | E3-S1, E3-S2 |
| AC-02 | ≥ 3 products (TERM_LIFE, MOTOR, HOUSEHOLD) with distinct rule sets | product-catalog | E2-S1, E2-S2 |
| AC-03 | Application captures KYC stub + risk inputs, validates vs product rules, progresses to underwriting | underwriting | E4-S1, E4-S2 |
| AC-04 | Underwriting returns AUTO_BIND / MANUAL_REVIEW / DECLINE with reason codes from the active version | underwriting | E4-S1, E4-S2 |
| AC-05 | Issuance: unique policy number, effective date, sum insured, premium, status ACTIVE | policy-issuance | E5-S2 |
| AC-06 | Endorsement: immutable record linked to policy + atomic policy attribute update | endorsement | E6-S2 |
| AC-07 | Renewal: new term with refreshed premium; auto-lapse when unpaid beyond grace period | renewal-cancellation | E7-S1, E7-S3 |
| AC-08 | Cancellation: pro-rated refund per product rules; status CANCELLED; refund append-only | renewal-cancellation | E8-S1, E8-S2 |
| AC-09 | Admin reviews the manual queue and overrides DECLINE with reason code + comment; audited | underwriting | E4-S4 |
| AC-10 | ACTIVE → ENDORSED / LAPSED / CANCELLED / RENEWED enforced; invalid → `InvalidPolicyStateException` | policy-issuance | E5-S1 |
| AC-11 | Admin creates a DRAFT version and publishes it; PUBLISHED versions are immutable; only one active version per product | product-catalog | E2-S3 |
| AC-12 | Invalid quote input → 422 with field errors; no PUBLISHED version → quote refused (no fallback) | quote-engine | E3-S2 |
| AC-13 | Every quote records product + rule version; re-quoting the same input on that version reproduces the premium | quote-engine | E3-S2 |
| AC-14 | Underwriter approves/declines a MANUAL_REVIEW case with reason codes; decision audited with actor ID | underwriting | E4-S3 |
| AC-15 | Customer sees own policies with premium due date, lifecycle status and endorsement history | policy-issuance | E5-S3 |
| AC-16 | Endorsement types CHANGE_ADDRESS / ADD_NOMINEE / CHANGE_SUM_INSURED validated vs rule set; sum-insured change recomputes premium delta | endorsement | E6-S1 |
| AC-17 | Simulated premium payment is recorded append-only; a paid policy does not lapse | renewal-cancellation | E7-S2 |
| AC-18 | End-of-day run is idempotent: re-running for the same date renews/lapses nothing twice | renewal-cancellation | E7-S3 |
| AC-19 | Cancellation within the free-look period refunds the full premium; afterwards pro-rata minus admin fee | renewal-cancellation | E8-S1 |
| AC-20 | Admin dashboard: active policies by product, premium collected, renewal pipeline, lapse forecast | app_spec | E9-S1, E9-S2 |
| AC-21 | `GET /health` returns 200 within 1 s of startup | app_spec | E1-S1 |
| AC-22 | API enforces roles at the controller layer: missing actor → 401, wrong role → 403 | app_spec | E1-S3 |
| AC-23 | Every response echoes `X-Correlation-ID`; logs are JSON lines with it and contain no PII | app_spec | E1-S2 |
| AC-24 | UI is responsive: usable at 1280 px and 390 px (nav collapses, tables stack) | app_spec | E1-S5, E9-S4 |

NFR mapping: NFR-01 → E3-S1, E6-S1, E7-S1, E8-S1 · NFR-02 → E1-S3, E2-S2, E4-S2, E5-S2, E6-S2, E7-S2, E8-S2 ·
NFR-03 → E1-S2, E4-S2 · NFR-04 → E1-S3, E4-S3, E4-S4 · NFR-05 → E1-S1, E2-S2 · NFR-06 → E1-S2 ·
NFR-07 → E1-S1 · NFR-08 → E1-S4.

## Epics

| Epic | Title | Stories | Sprint |
|------|-------|---------|--------|
| E1 | Platform foundation | 5 | 1 |
| E2 | Product catalog & rule versions | 4 | 1 |
| E3 | Quote engine | 3 | 2 |
| E4 | Application & underwriting | 5 | 2 |
| E5 | Policy issuance & lifecycle | 3 | 3 |
| E6 | Endorsements | 3 | 3 |
| E7 | Renewal, lapse & payments | 4 | 4 |
| E8 | Cancellation & refunds | 3 | 4 |
| E9 | Portfolio dashboard, seed & end-to-end | 4 | 4 |

**34 stories · 24 ACs · 4 sprints.**

## Sprint 1 — Product catalog (harness group set `S1`)

| Group | Story | Title | Layer | Depends on |
|-------|-------|-------|-------|------------|
| S1-A | E1-S1 | Backend skeleton: settings, DB session, Alembic baseline, `/health`, `npm start` | API | — |
| S1-A | E2-S1 | Rule-set types, JSON schema and three v1 rule files + `PUBLISHED.lock` | Types | — |
| S1-B | E1-S2 | Structured JSON logging, correlation-id middleware, PII masking | Config | E1-S1 |
| S1-B | E1-S3 | Auth stub at controller layer + append-only `AuditRecord` | API | E1-S1 |
| S1-B | E1-S4 | Architecture tests + import-linter contracts | Types | E1-S1 |
| S1-C | E2-S2 | Rule loader, `RuleSetVersion` model/repository, seed import | Repository | E1-S1, E1-S3, E2-S1 |
| S1-C | E1-S5 | Frontend shell: routing, role switcher, responsive layout | UI | E1-S3 |
| S1-D | E2-S3 | Catalog service: list, active version, create draft, publish | Service | E2-S2, E1-S3 |
| S1-E | E2-S4 | Catalog API + Product Catalog Manager UI | UI | E2-S3, E1-S5 |

## Sprint 2 — Quote + underwriting (`S2`)

| Group | Story | Title | Layer | Depends on |
|-------|-------|-------|-------|------------|
| S2-A | E3-S1 | Premium calculator (three products, Decimal) | Domain | E2-S1 |
| S2-A | E4-S1 | Application validator + underwriting decision rules | Domain | E2-S1 |
| S2-B | E3-S2 | Quote service + `Quote` persistence | Service | E3-S1, E2-S3 |
| S2-C | E3-S3 | Quote API + Get-a-Quote UI | UI | E3-S2, E1-S5 |
| S2-C | E4-S2 | Application submit → decide: `Application` + `UnderwritingDecision` | Service | E4-S1, E3-S2 |
| S2-D | E4-S3 | Manual review queue: underwriter approve/decline, audited | Service | E4-S2, E1-S3 |
| S2-E | E4-S4 | Admin queue review + DECLINE override, audited | API | E4-S3 |
| S2-F | E4-S5 | Apply UI + Underwriter Workbench UI | UI | E4-S4, E1-S5 |

## Sprint 3 — Issuance + endorsement (`S3`)

| Group | Story | Title | Layer | Depends on |
|-------|-------|-------|-------|------------|
| S3-A | E5-S1 | Policy state machine + `InvalidPolicyStateException` | Domain | — |
| S3-B | E6-S1 | Endorsement rules: types, eligibility, premium delta | Domain | E3-S1, E5-S1 |
| S3-B | E5-S2 | Policy issuance service + transition log | Service | E5-S1, E4-S2 |
| S3-C | E5-S3 | Policy views API + My Policies / Policy Detail UI | UI | E5-S2, E1-S5 |
| S3-C | E6-S2 | Endorsement service: atomic, immutable | Service | E6-S1, E5-S2 |
| S3-D | E6-S3 | Endorsement API + Endorse UI | UI | E6-S2, E5-S3 |

## Sprint 4 — Renewal + cancellation (`S4`)

| Group | Story | Title | Layer | Depends on |
|-------|-------|-------|-------|------------|
| S4-A | E7-S1 | Renewal term + grace-period rules | Domain | E5-S1, E3-S1 |
| S4-A | E8-S1 | Refund rules: pro-rata, free-look, admin fee | Domain | E5-S1 |
| S4-B | E7-S2 | Simulated premium payments | Service | E5-S2, E7-S1 |
| S4-B | E8-S2 | Cancellation service + append-only `Refund` | Service | E8-S1, E5-S2 |
| S4-C | E7-S3 | End-of-day job: renew + lapse, idempotent | Service | E7-S1, E7-S2 |
| S4-C | E8-S3 | Cancel API + UI with refund preview | UI | E8-S2, E5-S3 |
| S4-D | E7-S4 | Renew API/UI + admin "run end-of-day" | UI | E7-S3, E5-S3 |
| S4-D | E9-S1 | Portfolio dashboard service + API | Service | E7-S3, E8-S2 |
| S4-D | E9-S3 | Seed data (3 products + sample policies, ≥ 70 % auto-bind) + README quick-start | Config | E5-S2, E6-S2, E7-S3, E8-S2 |
| S4-E | E9-S2 | Admin Portfolio Dashboard UI | UI | E9-S1 |
| S4-F | E9-S4 | Playwright end-to-end journeys + snapshots at 1280 / 390 px | UI | E9-S2, E8-S3, E7-S4, E6-S3, E4-S5 |

Only one story per group may add an Alembic migration (single head).

Validation: no cycles; every dependency points to an earlier group or sprint.
