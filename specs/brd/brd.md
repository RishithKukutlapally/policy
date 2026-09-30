# Business Requirements Document — PolicyForge

| | |
|---|---|
| **Business case** | BC-AINE-004 · Policy Issuance & Lifecycle Management Platform |
| **Client** | Horizon Insurance (fictional) · Domain: Insurance — General / Life |
| **Produced by** | `/brd` (claude-harness-engine) — five-dimension interview, answers confirmed by Rishith Kukutlapally, 2026-09-29 |
| **Status** | Awaiting human approval (gate before `/spec`) |

---

## 1. Executive Summary

PolicyForge is a multi-product policy administration platform for **Term Life, Motor and Household**
insurance. It runs the complete **quote → application → underwriting → issuance → endorsement →
renewal / lapse → cancellation** lifecycle on one system. Every price, eligibility check, underwriting
decision and refund is computed from a **versioned, immutable product rule set**, so the business can
change rates and rules without code changes while every past quote and policy stays reproducible.
Underwriter and admin actions are audited, money is fixed-point, history is append-only and PII never
reaches logs.

## 2. Problem Statement

Horizon Insurance administers its products through fragmented, largely manual processes:

- Quotes are slow and inconsistent; the same risk can be priced differently depending on who quotes it.
- Rate or rule changes require developer effort and redeployment.
- Underwriting decisions and overrides are not traceably linked to the rules in force or to the person
  who made them.
- Policy changes (endorsements), renewals, lapses and cancellations are handled ad hoc, producing
  premium and refund errors and no reliable history.

**Cost of not solving it:** lost customers from slow quoting, financial leakage from premium/refund
mistakes, audit and compliance exposure from untracked overrides and PII in logs, and engineering time
consumed by every product change.

## 3. Target Users

| User | Role / context | Primary needs |
|------|----------------|---------------|
| **Customer** (policyholder / applicant) | Non-technical, web browser on desktop or phone | Get a quote, apply, see policies and due dates, request changes, renew or cancel |
| **Underwriter** | Insurance professional, desktop | Work the manual review queue, approve/decline with reason codes, see case history |
| **Admin** (product / operations manager) | Business power user, desktop | Manage products and rule versions without code, review the manual underwriting queue and override declines with reason code + comment (audited), monitor the portfolio, run end-of-day processing |
| **System scheduler** | Automated job | Run the end-of-day renewal cycle and grace-period lapse processing |

## 4. Success Metrics (90 days)

| # | Metric | Target |
|---|--------|--------|
| M1 | Quote response time (API) | < 2 s p95 |
| M2 | Quote determinism | 100 % identical premium for identical input + rule version |
| M3 | Straight-through processing | ≥ 70 % of applications AUTO_BIND without manual review (on seed data) |
| M4 | Rule change lead time | New rule version published with **0** code changes |
| M5 | Audit coverage | 100 % of underwriter/admin actions recorded with actor ID |
| M6 | PII in logs | 0 occurrences |
| M7 | Lifecycle automation | End-of-day renewal/lapse runs daily with 0 duplicate renewals or lapses |
| M8 | Engineering quality | ≥ 80 % test coverage; every AC-01…AC-10 has ≥ 1 tagged test |

## 5. Scope

### In scope

1. **Product catalog** — 3 products (TERM_LIFE, MOTOR, HOUSEHOLD) with distinct, versioned rule sets;
   admins create a draft version and publish it; published versions are immutable.
2. **Quote engine** — product + insured-profile/risk inputs → deterministic premium from the active version.
3. **Application** — KYC stub and risk inputs validated against the product rule set; progresses to underwriting.
4. **Underwriting** — AUTO_BIND / MANUAL_REVIEW / DECLINE with reason codes from the active version;
   manual review queue; admin override of DECLINE with reason code + comment, audited.
5. **Policy issuance** — unique policy number, effective date, sum insured, premium, status ACTIVE.
6. **Endorsements** — change address, add nominee, change sum insured: immutable endorsement record +
   atomic policy update.
7. **Renewal** — new term with refreshed premium at the cycle date; auto-lapse after the grace period
   if premium is unpaid (end-of-day job); simulated premium payment.
8. **Cancellation** — pro-rated refund per product rules; status CANCELLED; append-only refund record.
9. **Admin portfolio dashboard** — active policies by product, premium collected, renewal pipeline, lapse forecast.
10. **Lifecycle state machine** — ACTIVE → ENDORSED / LAPSED / CANCELLED / RENEWED enforced;
    invalid transitions raise `InvalidPolicyStateException`.

### Out of scope

Real KYC document verification · real bureau, health-record or vehicle-record integrations · real payment
gateway (payments are a "mark premium paid" simulation) · reinsurance, distribution channels, broker
commission · production deployment, secret management, multi-region, distributed locking · real
identity provider (a documented role-header auth stub is used).

## 6. MVP Definition

The smallest valuable slice is **one product end to end**: catalog → quote → apply → AUTO_BIND → issued
ACTIVE policy. The full scope is delivered in four harness sprints:

| Sprint | Group | Delivers |
|--------|-------|----------|
| 1 | Product catalog | Rule-file schema, 3 products v1, catalog API/UI, publish flow, app skeleton, health, auth stub, logging |
| 2 | Quote + underwriting | Quote engine, application + KYC stub, decision matrix, manual queue, admin override |
| 3 | Issuance + endorsement | Policy issuance, state machine, endorsements, policy views |
| 4 | Renewal + cancellation | End-of-day renewal and lapse, payments, cancellation refunds, admin dashboard |

## 7. Alternatives Considered

| Option | Summary | Decision |
|--------|---------|----------|
| **A. Rules as versioned data** | JSON rule files per product/version (seed + source of truth) interpreted by pure Decimal domain functions; admin-published versions stored append-only in `rule_set_versions` | **Chosen** — only option meeting AC-01 (versioned rule file), AC-02 (distinct rule sets) and §6.2 (no-code catalog changes) while staying deterministic and testable |
| B. Hard-coded product classes | One class per product with rates in code | Rejected — every rate change is a code change (violates §6.2 / AC-01) |
| C. Generic rules engine / DSL | Runtime-evaluated expressions (e.g. JSON-logic) | Rejected — high complexity, weaker determinism and Decimal guarantees, hard to test; unnecessary for three products |

## 8. Technical Architecture

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · SQLite · uv.
- **Frontend:** React · Vite · TypeScript.
- **Quality:** pytest + pytest-cov, import-linter + architecture tests, ruff, mypy (strict), vitest, Playwright
  (UI validation with snapshots) and Playwright MCP for the harness evaluator.
- **Layering (one-way):** types → domain → config → repository → service → api → UI; `lib` cross-cutting
  (logger with PII masking, correlation id). Domain is pure (no I/O, logging or clock).
- **Run:** single command `npm start` — installs, migrates, seeds (3 products + sample policies), starts API
  (:8000) and UI (:3000).
- **CI:** GitLab CI — test (backend, frontend, e2e, hook self-test) → build → Claude Code review on MRs.
- **Performance:** `/health` 200 within 1 s of startup (NFR-07); quote < 2 s; single instance.
- **Observability:** structured JSON logs with `X-Correlation-ID` (NFR-06).
- **Security boundary:** authentication/authorisation is enforced at the **controller (API) layer** via a
  role-header auth stub (`X-Actor-Id`, `X-Actor-Role`); services receive the actor id and audit every
  underwriter/admin action (NFR-04).

## 9. Data Model Overview

| Entity | Purpose | Mutability |
|--------|---------|------------|
| RuleSetVersion | Product rule set version (DRAFT/PUBLISHED) | Append-only |
| Quote | Priced quote with product + rule version | Insert |
| Application | Applicant, KYC stub, risk inputs, status | Status projection |
| UnderwritingDecision | Decision + reason codes + rule version | Append-only |
| UnderwritingOverride | Admin override of a DECLINE (actor, reason, comment) | Append-only |
| Policy | Current policy projection (number, dates, sum insured, premium, status) | Projection |
| PolicyStateTransition | Every lifecycle transition (from, to, actor, at) | Append-only |
| Endorsement | Endorsement type, before/after values, premium delta | Append-only |
| PremiumPayment | Simulated premium payments | Append-only |
| Refund | Pro-rated cancellation refund | Append-only |
| AuditRecord | Actor-attributed audit of underwriter/admin actions | Append-only |

Money: `Numeric(12, 2)` ↔ `Decimal`, quantized to 0.01 ROUND_HALF_UP. Canonical names: `docs/conventions.md`.

## 10. External Integrations

None real. KYC, payments and authentication are internal stubs. Playwright MCP is used only by the
harness evaluator for UI verification.

## 11. Edge Cases & Constraints

| Scenario | Behaviour |
|----------|-----------|
| Invalid quote / application input | 422 with field-level errors; nothing persisted |
| Underwriting cannot auto-decide | MANUAL_REVIEW with reason codes → underwriter queue |
| Invalid lifecycle transition | `InvalidPolicyStateException` → 409; no change (AC-10) |
| Endorsement failure mid-way | Whole transaction rolls back; no partial endorsement (AC-06) |
| Renewal job fails for one policy | Logged and skipped; job continues; re-runnable without duplicates |
| No PUBLISHED version for a product | Quote refused with a clear error; no silent fallback |
| Publishing a malformed rule file | Rejected by schema validation |

**Constraints:** runs locally with no paid services; synthetic data only (§3.4); PII (Aadhaar, PAN, health
declarations) never logged and masked in the UI (NFR-03); underwriter/admin actions audited with actor ID
(NFR-04); money fixed-point (NFR-01); versions, endorsements, transitions and refunds append-only (NFR-02);
migrations append-only (NFR-05); architecture rules enforced by tests (NFR-08).

**Top risks (6 months):** premium/refund rounding mismatches · edits to published rule versions · PII in
logs · duplicate renewal/lapse · malformed rule files — each mapped to a guard (golden tests, immutability
hooks + hash ledger, redaction hook + logger, idempotent job, schema validation).

## 12. UI Context

| Role | Screens |
|------|---------|
| Customer | Get a Quote · Apply (KYC stub, status + reason codes) · My Policies · Policy Detail (endorsement history, lifecycle) · Endorse · Renew / Cancel (refund preview) |
| Underwriter | Workbench — manual queue, case detail, approve / decline with reason codes, audit trail |
| Admin | Product Catalog Manager (versions, draft → publish) · Underwriting queue review + DECLINE override (reason code + comment) · Portfolio Dashboard · Run end-of-day |
| All | Header role switcher (Customer / Underwriter / Admin demo users) driving the auth-stub headers |

- **Style:** clean functional internal tool; neutral palette; text status badges. Mockups by `ui-designer` in `/design`.
- **Viewports:** desktop 1280 px and mobile 390 px; responsive layout (side nav collapses, tables stack as cards).
- **Accessibility:** WCAG 2.1 AA basics — labelled inputs, keyboard navigation, visible focus, contrast,
  status not by colour alone; accessible names on all interactive elements.

## 13. Requirements Traceability (brief §5)

| ID | Requirement (brief) | Covered in BRD | Sprint |
|----|---------------------|----------------|--------|
| AC-01 | Deterministic premium for product + insured profile, from a versioned policy rule file | §5.2, §7 (option A), M2 | 2 |
| AC-02 | ≥ 3 products with distinct rule sets | §5.1, §7 | 1 |
| AC-03 | Application captures KYC stub + risk inputs, validates vs product rules, progresses to underwriting | §5.3, §11 | 2 |
| AC-04 | Underwriting returns AUTO_BIND / MANUAL_REVIEW / DECLINE with reason codes from the active version | §5.4, §11 | 2 |
| AC-05 | Issuance: unique policy number, effective date, sum insured, premium, status ACTIVE | §5.5, OQ-5 | 3 |
| AC-06 | Endorsement: immutable record linked to policy + atomic attribute update | §5.6, §11 | 3 |
| AC-07 | Renewal: new term, refreshed premium; auto-lapse after grace period if unpaid | §5.7, §11, OQ-3 | 4 |
| AC-08 | Cancellation: pro-rated refund per product rules, status CANCELLED, append-only refund | §5.8, OQ-4 | 4 |
| AC-09 | Admin reviews manual queue and overrides DECLINE with reason code + comment; audited | §3, §5.4, §12 | 2 |
| AC-10 | ACTIVE → ENDORSED / LAPSED / CANCELLED / RENEWED enforced; invalid → `InvalidPolicyStateException` | §5.10, §11 | 3 |
| NFR-01 | Premium/refund in fixed-point (Decimal), never float | §9, §11 | all |
| NFR-02 | Policy versions, endorsements, state transitions append-only | §9, §11 | all |
| NFR-03 | PII (Aadhaar, PAN, health) never logged | §11, §12 | all |
| NFR-04 | Auth enforced at controller layer; underwriter/admin actions audited with actor ID | §8 (security boundary), §9, §11 | 1–2 |
| NFR-05 | Database and policy migrations append-only | §11 | all |
| NFR-06 | Structured JSON logs with request correlation IDs | §8 | 1 |
| NFR-07 | Health endpoint 200 within 1 s of startup | §8 | 1 |
| NFR-08 | Architecture rules as automated tests (immutable versions, no float in premium code) | §8, §11 | 1 |

## 14. Open Questions

| # | Question | Proposed default (used unless changed) |
|---|----------|----------------------------------------|
| OQ-1 | Currency and locale | INR, `en-IN` number formatting |
| OQ-2 | Policy term | 12 months for Motor/Household; Term Life term chosen at quote (5–30 years) with annual premium |
| OQ-3 | Grace period | 30 days (per product rule set, configurable) |
| OQ-4 | Cancellation refund | PRO_RATA on unused days minus a flat admin fee; full refund inside a 15-day free-look period |
| OQ-5 | Policy number format | `<PRODUCT_PREFIX>-<YYYY>-<6-digit sequence>`, e.g. `MO-2026-000123` |
| OQ-6 | Auto-bind target data | Seed applications designed so ≥ 70 % auto-bind (M3) |
