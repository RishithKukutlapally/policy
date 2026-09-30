# Policy Issuance Spec — PolicyForge

| | |
|---|---|
| **Owns** | AC-05, AC-10, AC-15 |
| **Epic / stories** | E5 — E5-S1, E5-S2, E5-S3 |
| **Sprint** | 3 (Issuance + endorsement) |
| **Upstream** | `specs/brd/brd.md` §5.5, §5.10, §11, §14 (OQ-1, OQ-2, OQ-5) · `docs/conventions.md` · `specs/stories/dependency-graph.md` |

## Purpose

Issue a policy from an `AUTO_BIND` application — unique policy number, effective and expiry dates, sum
insured, premium and initial status `ACTIVE` — and own the **policy lifecycle state machine** that every other
feature (endorsement, renewal, lapse, cancellation) must go through. Give customers a view of their policies
with premium due date, lifecycle status and endorsement history.

## Scope

**In scope**

- Pure domain state machine `src/domain/policy_state_machine.py` raising `InvalidPolicyStateException`
  (`src/types/errors.py`) on any disallowed transition.
- Issuance service: policy number generation, dates, premium from the quote, initial transition, application
  `AUTO_BIND → ISSUED`.
- Append-only transition log `policy_state_transitions` written for every status change (including issuance).
- Policy views: list and detail (premium due date, payment status, lifecycle history, endorsement history).
- UI: My Policies, Policy Detail (E5-S3).

**Out of scope**

- Endorsement, renewal, lapse, payment and cancellation behaviour (they *use* this state machine; see
  `specs/endorsement_spec.md`, `specs/renewal-cancellation_spec.md`).
- Policy documents / PDF schedules, e-mail notifications.
- Back-dated or future-dated issuance.

## Assumptions

- **A-PI-1** Issuance is an explicit call on an `AUTO_BIND` application (customer owner or admin), not a side
  effect of the decision, so sprint 2 and sprint 3 stay independent.
- **A-PI-2** `effective_date` = business date of issuance; `expiry_date` = `effective_date` +
  `renewal.term_months` months − 1 day (12 months for all v1 products; for TERM_LIFE this is the annual premium
  term inside the `term_years` cover chosen at quote — OQ-2).
- **A-PI-3** `premium` = the quote's premium (already computed from the version the application was decided
  on); `premium_due_date` = `effective_date`, and the **first-term premium is recorded as paid at issuance** (one
  `PremiumPayment` row, `due_date = effective_date`, `amount = premium`). The next premium (renewal) is due on
  `expiry_date + 1 day` (`next_premium_due_date`). Currency INR, displayed with `en-IN` formatting (OQ-1).
- **A-PI-4** Policy number = `<PREFIX>-<YYYY>-<6-digit sequence>` (OQ-5): prefix `TL` / `MO` / `HH`, `YYYY`
  = year of `effective_date`, sequence per prefix + year starting at `000001`, allocated inside the issuing
  transaction and protected by a unique constraint on `policies.policy_number`.
- **A-PI-5** A customer requesting another customer's policy gets 404 (no existence leak).

## Business Rules

### Rule-file fields used (exact names from `docs/conventions.md`)

| Field | Use |
|-------|-----|
| `product` | Selects policy-number prefix (`TERM_LIFE → TL`, `MOTOR → MO`, `HOUSEHOLD → HH`) |
| `renewal.term_months` | Term length used to compute `expiry_date` |
| `currency` | Recorded on the policy (`INR`) |

The policy stores the `rule_version` its quote and decision used; premium is never
recomputed at issuance (NFR-01: `Decimal`, `Numeric(12, 2)`).

### Issuance rules

1. Application must be `AUTO_BIND` (after automatic decision, underwriter approval or admin override); otherwise
   409 `INVALID_APPLICATION_STATE`. An application issues **at most one** policy (`ISSUED` → 409 on repeat).
2. In one transaction: allocate policy number, insert `policies` row with status `ACTIVE`, append
   `policy_state_transitions` (`from_status = null`, `to_status = ACTIVE`, actor, reason `ISSUED`), append the
   first-term `PremiumPayment`, set application `ISSUED`, append `AuditRecord` (`POLICY_ISSUED`) when actor is ADMIN.
3. Any failure rolls the whole transaction back (no policy number consumed, no payment row, application stays `AUTO_BIND`).

### State machine (E5-S1)

`transition(current: PolicyStatus, target: PolicyStatus) -> PolicyStatus` is the only way services change
status. Every allowed change appends one `policy_state_transitions` row; a disallowed change raises
`InvalidPolicyStateException(current, target)`, which the API maps to **409 `INVALID_POLICY_STATE`** and which leaves the policy,
the transition log and any dependent rows (endorsements, refunds, payments) unchanged.

## State Transitions Touched

From `docs/conventions.md` Lifecycle (this spec is authoritative for enforcement):

| From | Allowed targets |
|------|-----------------|
| *(new)* | `ACTIVE` (issuance) |
| `ACTIVE` | `ENDORSED`, `LAPSED`, `CANCELLED`, `RENEWED` |
| `ENDORSED` | `ENDORSED`, `LAPSED`, `CANCELLED`, `RENEWED` |
| `LAPSED`, `CANCELLED`, `RENEWED` | none — terminal (renewal issues a **new** term policy that starts `ACTIVE`) |

Everything else (e.g. `ACTIVE → ACTIVE`, `CANCELLED → ENDORSED`, `LAPSED → RENEWED`, anything `→ ACTIVE` on
an existing policy) raises `InvalidPolicyStateException`. Application: `AUTO_BIND → ISSUED`.

## API Endpoints

Auth stub headers `X-Actor-Id`, `X-Actor-Role`; missing actor → 401 `UNAUTHENTICATED`, wrong role → 403
`FORBIDDEN` (AC-22). Error envelope and codes: `docs/conventions.md`.

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| POST | `/api/applications/{application_id}/issue` | CUSTOMER (application owner), ADMIN | 201 — policy number, product, effective/expiry dates, sum insured, premium, `premium_due_date`, `next_premium_due_date`, status `ACTIVE` | 401, 403, 404 `NOT_FOUND` (unknown/other customer's application), 409 `INVALID_APPLICATION_STATE` |
| GET | `/api/policies` | CUSTOMER (own), UNDERWRITER, ADMIN (all, filter `product`, `status`) | 200 — list with number, product, status, sum insured, premium, effective/expiry dates, `next_premium_due_date` | 401, 403, 422 `VALIDATION_ERROR` (bad filter) |
| GET | `/api/policies/{policy_number}` | CUSTOMER (owner), UNDERWRITER, ADMIN | 200 — detail incl. `transitions[]`, `endorsements[]`, `payments[]`, `refunds[]`, masked KYC, `previous_policy_number` | 401, 403, 404 `NOT_FOUND` |

Every state-changing endpoint in other specs that hits a disallowed transition returns **409** with
`{"error": {"code": "INVALID_POLICY_STATE", "message": "…", "details": {"current": "<status>", "target": "<status>"}}}`.

## Data

| Table | Model | Append-only | Notes |
|-------|-------|-------------|-------|
| `policies` | `Policy` | — (current projection) | policy_number (unique), product, application id, customer id, `rule_version`, rating inputs (JSON), sum_insured, premium (`Numeric(12, 2)`), currency, effective_date, expiry_date, premium_due_date, status, insured attributes (address, nominees), previous_policy_number |
| `policy_state_transitions` | `PolicyStateTransition` | ✅ | policy id, from_status (nullable), to_status, actor id, reason, occurred_at |
| `applications` | `Application` | — | status `AUTO_BIND → ISSUED` |
| `premium_payments` | `PremiumPayment` | ✅ | first-term payment appended at issuance |
| `audit_records` | `AuditRecord` | ✅ | admin issuance (`POLICY_ISSUED`) |
| `endorsements`, `refunds` | read only here | ✅ | shown on Policy Detail |

## NFRs That Apply

- **NFR-01** premium and sum insured are `Decimal` quantized to 0.01 `ROUND_HALF_UP`; never `float`.
- **NFR-02** `policy_state_transitions` append-only; `policies` is the only mutable projection.
- **NFR-03** Policy Detail shows masked Aadhaar/PAN only; no PII in logs.
- **NFR-04** role checks at the API layer; admin actions audited.
- **NFR-08** architecture test: `policy_state_machine.py` is pure and every service status change goes through it.

## Implementing Stories

| Story | Title | ACs |
|-------|-------|-----|
| E5-S1 | Policy state machine + `InvalidPolicyStateException` (Domain) | AC-10 |
| E5-S2 | Policy issuance service + transition log (Service) | AC-05 |
| E5-S3 | Policy views API + My Policies / Policy Detail UI (UI) | AC-15 |

## Acceptance Criteria

### AC-05 — Policy issuance generates a unique policy number, effective date, sum insured, premium, and sets initial status to ACTIVE

```gherkin
Scenario: Issue a MOTOR policy from an AUTO_BIND application
  Given application A45 for customer "cust-001" is AUTO_BIND on MOTOR v1
  And its quote has sum_insured "400000.00", vehicle_age_years 2, engine_cc 998, zone "B", ncb_percent "0" and premium "12400.00"
      (400000.00 × 0.0310 × 1.00 × 1.00 × 1.00 × (1 − 0.00) = 12400.00 from the E2-S1 v1 values)
  And the highest existing MOTOR policy number for 2026 is "MO-2026-000122"
  And the business date is 2026-10-01
  When customer "cust-001" POSTs /api/applications/A45/issue
  Then the response is 201
  And the policy number is "MO-2026-000123"
  And effective_date is 2026-10-01 and expiry_date is 2027-09-30 (renewal.term_months 12)
  And sum_insured is 400000.00 and premium is 12400.00 (Decimal, not float)
  And premium_due_date is 2026-10-01, next_premium_due_date is 2027-10-01 and status is ACTIVE
  And one premium_payments row has due_date 2026-10-01 and amount 12400.00 (first term paid at issuance)
  And one policy_state_transitions row has from_status null, to_status ACTIVE, actor "cust-001"
  And application A45 has status ISSUED

Scenario: Policy numbers are unique per product prefix and year
  Given "TL-2026-000009" and "MO-2026-000123" exist
  When a TERM_LIFE and a MOTOR application are issued on 2026-10-02
  Then they receive "TL-2026-000010" and "MO-2026-000124"
  When the first HOUSEHOLD policy of 2027 is issued on 2027-01-04
  Then it receives "HH-2027-000001"

Scenario: An application issues at most one policy
  Given application A45 has status ISSUED
  When customer "cust-001" POSTs /api/applications/A45/issue again
  Then the response is 409 with error code "INVALID_APPLICATION_STATE" and no policy row is added

Scenario: Non-bindable applications cannot be issued
  Given application A53 is DECLINED
  When admin "admin-001" POSTs /api/applications/A53/issue
  Then the response is 409 with error code "INVALID_APPLICATION_STATE" and no policy number is consumed
```

### AC-10 — Policy state transitions ACTIVE → ENDORSED / LAPSED / CANCELLED / RENEWED are enforced; invalid transitions raise InvalidPolicyStateException

```gherkin
Scenario Outline: Allowed transitions succeed and are logged
  Given a policy in status <from>
  When the state machine transitions it to <to>
  Then the new status is <to>
  And one policy_state_transitions row is appended with from_status <from> and to_status <to>
  Examples:
    | from     | to        |
    | ACTIVE   | ENDORSED  |
    | ACTIVE   | LAPSED    |
    | ACTIVE   | CANCELLED |
    | ACTIVE   | RENEWED   |
    | ENDORSED | ENDORSED  |
    | ENDORSED | CANCELLED |

Scenario Outline: Invalid transitions raise InvalidPolicyStateException
  Given a policy in status <from>
  When the state machine transitions it to <to>
  Then InvalidPolicyStateException is raised naming <from> and <to>
  And the status stays <from> and no policy_state_transitions row is appended
  Examples:
    | from      | to        |
    | ACTIVE    | ACTIVE    |
    | CANCELLED | ENDORSED  |
    | CANCELLED | CANCELLED |
    | LAPSED    | RENEWED   |
    | LAPSED    | ACTIVE    |
    | RENEWED   | CANCELLED |

Scenario: Invalid transition through the API returns 409 and changes nothing
  Given policy "MO-2026-000123" is CANCELLED with 1 refund row
  When customer "cust-001" POSTs /api/policies/MO-2026-000123/cancel
  Then the response is 409 with error code "INVALID_POLICY_STATE" and details current "CANCELLED", target "CANCELLED"
  And the policy still has exactly 1 refund row and no new transition row
  When customer "cust-001" POSTs /api/policies/MO-2026-000123/endorsements with type CHANGE_ADDRESS
  Then the response is 409 with error code "INVALID_POLICY_STATE" and no endorsements row is added
```

### AC-15 — Customer sees own policies with premium due date, lifecycle status and endorsement history

```gherkin
Scenario: Customer lists own policies only
  Given customer "cust-001" owns "MO-2026-000123" (ENDORSED, effective 2026-10-01, expiry 2027-09-30)
        and "TL-2026-000010" (ACTIVE, effective 2026-10-02, expiry 2027-10-01), both first-term premiums paid at issuance
  And customer "cust-002" owns "HH-2026-000004"
  When customer "cust-001" GETs /api/policies
  Then the response is 200 with exactly "MO-2026-000123" and "TL-2026-000010"
  And each item shows status, premium and next_premium_due_date (2027-10-01 and 2027-10-02)

Scenario: Policy detail shows lifecycle and endorsement history
  Given "MO-2026-000123" was issued 2026-10-01 and endorsed CHANGE_ADDRESS on 2026-11-15
  When customer "cust-001" GETs /api/policies/MO-2026-000123
  Then the response is 200 with status ENDORSED, premium_due_date 2026-10-01 and one payment of 12400.00
  And transitions lists [null -> ACTIVE on 2026-10-01, ACTIVE -> ENDORSED on 2026-11-15] in order
  And endorsements lists 1 CHANGE_ADDRESS record with before and after address and premium_delta 0.00
  And Aadhaar is shown as "XXXX-XXXX-0001"

Scenario: Another customer's policy is not visible
  When customer "cust-002" GETs /api/policies/MO-2026-000123
  Then the response is 404 with error code "NOT_FOUND"
  When a request without X-Actor-Id GETs /api/policies
  Then the response is 401 with error code "UNAUTHENTICATED"
```
