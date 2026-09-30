# Endorsement Spec — PolicyForge

| | |
|---|---|
| **Owns** | AC-06, AC-16 |
| **Epic / stories** | E6 — E6-S1, E6-S2, E6-S3 |
| **Sprint** | 3 (Issuance + endorsement) |
| **Upstream** | `specs/brd/brd.md` §5.6, §11 · `docs/conventions.md` · `specs/policy-issuance_spec.md` (state machine) · `specs/stories/dependency-graph.md` |

## Purpose

Let a customer (or an admin on their behalf) change an in-force policy mid-term — change address, add a
nominee, change sum insured — by creating an **immutable endorsement record** linked to the policy and
updating the policy's attributes **atomically**. Endorsement types are validated against the product's rule
set, and a sum-insured change recomputes the premium and records the pro-rated premium delta.

## Scope

**In scope**

- Endorsement types `CHANGE_ADDRESS`, `ADD_NOMINEE`, `CHANGE_SUM_INSURED` (`EndorsementType` in
  `src/types/enums.py`).
- Pure domain rules `src/domain/endorsement_rules.py`: type eligibility, payload validation, premium delta.
- Endorsement service: one transaction for endorsement row + policy projection update + state transition.
- Premium-delta preview via `POST /api/policies/{policy_number}/endorsements?preview=true` (nothing persisted).
- UI: Endorse screen and endorsement history on Policy Detail (E6-S3).

**Out of scope**

- Collecting an additional premium or paying a return premium for the delta (recorded on the `Endorsement`
  row and displayed only; collection is a future consideration).
- Removing a nominee, changing insured person, vehicle or construction details, back-dated endorsements.
- Reversing / cancelling an endorsement (endorsements are append-only; a correction is a new endorsement).

## Assumptions

- **A-EN-1** Endorsements are validated and priced against the rule-set version recorded on the policy
  (`policies.rule_version`, the version active at issuance or renewal) so a term stays internally consistent;
  renewal re-prices on the then-active version (`specs/renewal-cancellation_spec.md`).
- **A-EN-2** Endorsement date = business date of the request; it must satisfy
  `effective_date <= endorsement_date <= expiry_date`.
- **A-EN-3** `CHANGE_ADDRESS` and `ADD_NOMINEE` have `premium_delta = 0.00`.
- **A-EN-4** After `CHANGE_SUM_INSURED`, `policies.sum_insured` and `policies.premium` hold the new
  full-term values; the pro-rated difference is stored on the endorsement as `premium_delta` (not collected,
  so it does not change the refund base — see renewal-cancellation A-RC-8).

## Business Rules

### Rule-file fields used (exact names from `docs/conventions.md`)

| Field | Use |
|-------|-----|
| `endorsement.allowed_types` | Requested type must be listed, else 422 `VALIDATION_ERROR` with details `{field: "type", code: "NOT_ALLOWED"}` |
| `eligibility.min_sum_insured`, `eligibility.max_sum_insured` | Bounds for a new sum insured |
| `premium.base_rate`, `premium.minimum_premium`, `premium.factors` | Full-term premium recomputed by `src/domain/premium_calculator.py` with the new sum insured |
| `renewal.term_months` | Defines the term used for day counts (via policy `effective_date` / `expiry_date`) |

### Validation per type

| Type | Payload | Rules |
|------|---------|-------|
| `CHANGE_ADDRESS` | `address` | Non-blank, ≤ 300 chars, different from current address |
| `ADD_NOMINEE` | `nominee_name`, `relationship`, `share_percent` | Non-blank name; relationship in `SPOUSE`, `CHILD`, `PARENT`, `SIBLING`, `OTHER`; `share_percent` `Decimal` 1–100; total shares of all nominees ≤ 100 (`SHARE_EXCEEDS_100`) |
| `CHANGE_SUM_INSURED` | `new_sum_insured` | `Decimal` string, 2 dp; within eligibility bounds (`OUT_OF_RANGE`); different from current (`UNCHANGED`) |

### Premium delta (NFR-01, `Decimal`, quantized 0.01 `ROUND_HALF_UP` once at the end)

```
term_days     = (expiry_date - effective_date).days + 1
days_elapsed  = (endorsement_date - effective_date).days
unused_days   = term_days - days_elapsed
new_premium   = premium_calculator(policy rating inputs with new_sum_insured, policy's own rule version)
premium_delta = quantize((new_premium - old_premium) * unused_days / term_days, 0.01, ROUND_HALF_UP)
```

Positive delta = additional premium; negative = return premium. Only the final value is quantized. The delta
is recorded on the `Endorsement` row and is not collected.

### Atomicity (AC-06)

In **one database transaction**:

1. Validate status via the state machine (`ACTIVE → ENDORSED` or `ENDORSED → ENDORSED`).
2. Append `endorsements` row: policy id, type, `before` and `after` JSON, `premium_delta`,
   `rule_version`, endorsement date, actor id, created_at.
3. Update the `policies` projection (address / nominees / sum_insured + premium) and status `ENDORSED`.
4. Append `policy_state_transitions` row (reason `ENDORSEMENT:<type>`).
5. Append `AuditRecord` (`ENDORSEMENT_CREATED`) when the actor is ADMIN.

Any exception in steps 1–5 rolls everything back: no endorsement row, no transition row, policy unchanged.
Endorsement rows are never updated or deleted.

## State Transitions Touched

`ACTIVE → ENDORSED`, `ENDORSED → ENDORSED` (via `src/domain/policy_state_machine.py`). Endorsing a
`LAPSED`, `CANCELLED` or `RENEWED` policy raises `InvalidPolicyStateException` → 409 `INVALID_POLICY_STATE`.

## API Endpoints

Auth stub headers `X-Actor-Id`, `X-Actor-Role`; missing actor → 401 `UNAUTHENTICATED`, wrong role → 403
`FORBIDDEN` (AC-22). Error envelope and codes: `docs/conventions.md`.

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| POST | `/api/policies/{policy_number}/endorsements` | CUSTOMER (owner), ADMIN | 201 — endorsement id, type, before/after, `premium_delta`, updated policy summary | 401, 403, 404 `NOT_FOUND`, 409 `INVALID_POLICY_STATE`, 422 `VALIDATION_ERROR` |
| POST | `/api/policies/{policy_number}/endorsements?preview=true` | CUSTOMER (owner), ADMIN | 200 — validated `after` values, new premium, `premium_delta`; nothing persisted | same as above |

Endorsement history is returned by `GET /api/policies/{policy_number}` (`endorsements[]`, oldest first).
UNDERWRITER cannot create endorsements (403 `FORBIDDEN`).

## Data

| Table | Model | Append-only | Notes |
|-------|-------|-------------|-------|
| `endorsements` | `Endorsement` | ✅ | see Atomicity step 2; `premium_delta` `Numeric(12, 2)` |
| `policies` | `Policy` | — (current projection) | address, nominees, sum_insured, premium, status updated in the same transaction |
| `policy_state_transitions` | `PolicyStateTransition` | ✅ | one row per endorsement |
| `audit_records` | `AuditRecord` | ✅ | admin-initiated endorsements (`ENDORSEMENT_CREATED`) |
| `rule_set_versions` | `RuleSetVersion` | ✅ | read only |

## NFRs That Apply

- **NFR-01** delta and new premium in `Decimal`, quantized 0.01 `ROUND_HALF_UP`; no `float` anywhere in
  `endorsement_rules.py`.
- **NFR-02** endorsements and transitions append-only; the repository exposes `add` + reads only.
- **NFR-03** nominee names and addresses are not logged verbatim; no Aadhaar/PAN in endorsement payloads.
- **NFR-04** role check at the API; admin endorsements audited with actor ID.

## Implementing Stories

| Story | Title | ACs |
|-------|-------|-----|
| E6-S1 | Endorsement rules: types, eligibility, premium delta (Domain) | AC-16 |
| E6-S2 | Endorsement service: atomic, immutable (Service) | AC-06 |
| E6-S3 | Endorsement API + Endorse UI (UI) | AC-06, AC-16 (E2E) |

Money examples below use the MOTOR v1 values of `specs/stories/E2-S1.md` with the rating profile
vehicle_age_years 2, engine_cc 998, zone `B`, ncb_percent `"0"` (all factor multipliers 1.00), so
premium = sum_insured × 0.0310.

## Acceptance Criteria

### AC-06 — Endorsement creates an immutable endorsement record linked to the policy and updates relevant policy attributes atomically

```gherkin
Scenario: Address change creates a linked endorsement and updates the policy
  Given policy "MO-2026-000123" of customer "cust-001" is ACTIVE with address "1 Sample Street, Testville"
  And the business date is 2026-11-15
  When customer "cust-001" POSTs /api/policies/MO-2026-000123/endorsements
       with type CHANGE_ADDRESS and address "7 Example Road, Demotown"
  Then the response is 201
  And one endorsements row links policy "MO-2026-000123" with before address "1 Sample Street, Testville",
      after address "7 Example Road, Demotown" and premium_delta 0.00
  And the policy address is "7 Example Road, Demotown" and its status is ENDORSED
  And one policy_state_transitions row ACTIVE -> ENDORSED with reason "ENDORSEMENT:CHANGE_ADDRESS" is appended

Scenario: Failure mid-way rolls back the whole endorsement
  Given policy "MO-2026-000124" is ACTIVE with sum_insured 400000.00 and premium 12400.00
  And appending the policy_state_transitions row is made to fail (injected repository error)
  When customer "cust-001" POSTs a CHANGE_SUM_INSURED endorsement with new_sum_insured "500000.00"
  Then the response is 500 with error code "INTERNAL_ERROR"
  And no endorsements row exists for "MO-2026-000124"
  And the policy still has sum_insured 400000.00, premium 12400.00 and status ACTIVE
  And no policy_state_transitions row was appended

Scenario: Endorsement records are immutable
  Given endorsement E17 exists for policy "MO-2026-000123"
  When any code path attempts to update or delete endorsement E17
  Then the endorsement repository exposes no update or delete operation
  And the append-only architecture test and the append-only-repository-check hook fail such a change

Scenario: Terminal policies cannot be endorsed
  Given policy "HH-2026-000004" is LAPSED
  When its owner POSTs a CHANGE_ADDRESS endorsement
  Then the response is 409 with error code "INVALID_POLICY_STATE" and no endorsement row is added
```

### AC-16 — Endorsement types CHANGE_ADDRESS / ADD_NOMINEE / CHANGE_SUM_INSURED are validated against the rule set; a sum-insured change recomputes the premium delta

```gherkin
Scenario: Sum-insured increase recomputes premium and pro-rated delta
  Given policy "MO-2026-000123" on MOTOR v1 has sum_insured 400000.00, premium 12400.00,
        effective_date 2026-10-01 and expiry_date 2027-09-30 (rating profile above)
  And MOTOR v1 has eligibility max_sum_insured "5000000.00" and endorsement.allowed_types containing CHANGE_SUM_INSURED
  And the business date is 2027-04-01
  When customer "cust-001" POSTs a CHANGE_SUM_INSURED endorsement with new_sum_insured "500000.00"
  Then new_premium = 500000.00 × 0.0310 = 15500.00
  And term_days = 365, days_elapsed = 182, unused_days = 183
  And premium_delta = (15500.00 − 12400.00) × 183 / 365 = 1554.2465… → 1554.25 (ROUND_HALF_UP)
  And the policy now has sum_insured 500000.00 and premium 15500.00
  And the endorsement records premium_delta 1554.25

Scenario: Sum-insured decrease gives a negative delta
  Given the same policy and business date 2027-04-01
  When the customer POSTs CHANGE_SUM_INSURED with new_sum_insured "300000.00" and preview=true
  Then the response is 200 with new_premium 9300.00 (300000.00 × 0.0310)
  And premium_delta = (9300.00 − 12400.00) × 183 / 365 = −1554.2465… → −1554.25
  And nothing is persisted

Scenario: Type not allowed by the rule set is rejected
  Given a HOUSEHOLD rule set whose endorsement.allowed_types is ["CHANGE_ADDRESS", "CHANGE_SUM_INSURED"]
  And policy "HH-2026-000005" is ACTIVE on that version
  When its owner POSTs an ADD_NOMINEE endorsement
  Then the response is 422 with error code "VALIDATION_ERROR" and details {"field": "type", "code": "NOT_ALLOWED"}

Scenario: Sum insured outside eligibility is rejected
  Given MOTOR v1 eligibility max_sum_insured "5000000.00"
  When the owner of "MO-2026-000123" requests CHANGE_SUM_INSURED with new_sum_insured "6000000.00"
  Then the response is 422 with details {"field": "new_sum_insured", "code": "OUT_OF_RANGE"}

Scenario: Nominee validation
  Given policy "TL-2026-000010" is ACTIVE with one nominee holding share_percent 60
  When its owner adds nominee "Test Nominee 02", relationship "CHILD", share_percent "40"
  Then the response is 201 and premium_delta is 0.00
  When its owner then adds nominee "Test Nominee 03", relationship "SPOUSE", share_percent "10"
  Then the response is 422 with details {"field": "share_percent", "code": "SHARE_EXCEEDS_100"} because total nominee share would be 110
```
