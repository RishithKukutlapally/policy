# Renewal & Cancellation Spec — PolicyForge

| | |
|---|---|
| **Owns** | AC-07, AC-08, AC-17, AC-18, AC-19 |
| **Epics / stories** | E7 — E7-S1, E7-S2, E7-S3, E7-S4 · E8 — E8-S1, E8-S2, E8-S3 |
| **Sprint** | 4 (Renewal + cancellation) |
| **Upstream** | `specs/brd/brd.md` §5.7–§5.8, §11, §14 (OQ-2, OQ-3, OQ-4) · `docs/conventions.md` · `specs/policy-issuance_spec.md` (state machine) · `specs/stories/dependency-graph.md` |

## Purpose

Run the back half of the policy lifecycle: quote and record simulated renewal premium payments, **renew**
paid policies at the cycle date into a new term (a new policy) with a premium refreshed from the active rule
set, **lapse** policies whose renewal premium stays unpaid beyond the configured grace period, and **cancel**
policies with a pro-rated refund (full refund inside the free-look period for new business) recorded
append-only. Renewal and lapse run in an idempotent end-of-day job.

## Scope

**In scope**

- Pure domain rules: `src/domain/renewal_rules.py` (renewal due date, grace end, `EndOfDayAction`, next-term
  dates) and `src/domain/refund_rules.py` (free-look, pro-rata, admin fee, `RefundType`).
- Renewal quote and simulated renewal premium payment ("mark premium paid") — append-only `premium_payments`.
- End-of-day job for an `as_of` date: renew / in-grace / lapse; idempotent and per-policy fault tolerant.
- Customer-initiated early renewal inside the renewal window.
- Cancellation with refund preview and append-only `refunds`.
- UI: Renew / Pay / Cancel (refund preview) on Policy Detail; admin "Run end-of-day" (E7-S4, E8-S3).

**Out of scope**

- Real payment gateway, partial payments, instalments, payment reversal.
- Re-underwriting at renewal; changing cover at renewal (use an endorsement first).
- Reinstatement of `LAPSED` policies; an `EXPIRED` status (not in the lifecycle — see A-RC-6).
- Distributed locking / concurrent job runs (single instance, BRD §5 out of scope).

## Assumptions

- **A-RC-1** Business dates are explicit inputs (`as_of`); domain functions never read the clock.
- **A-RC-2** The first-term premium is recorded as paid at issuance (policy-issuance A-PI-3). The **renewal
  premium is due on the new term's effective date** = `expiry_date + 1 day` (the renewal due date); grace end =
  due date + `renewal.grace_period_days`.
- **A-RC-3** The renewal premium is quoted by `GET …/renewal` with `src/domain/premium_calculator.py` on the
  product's **active** version, using the policy's rating inputs with ages and `vehicle_age_years` advanced by 1
  per completed 12-month term. A renewal payment records the amount and that `rule_version`; the successor term
  uses exactly that premium and version.
- **A-RC-4** A policy is renewable only if it is `ACTIVE`/`ENDORSED` and still meets `eligibility` of the active
  version with the advanced inputs (e.g. TERM_LIFE age ≤ `max_age` and cover `term_years` not exhausted).
  Otherwise the renewal quote reports `renewable: false`, payments are refused (422 `NOT_RENEWABLE`) and the
  end-of-day job lists it in `not_renewable` and leaves it unchanged.
- **A-RC-5** Renewal window: from `expiry_date − renewal_window_days` to grace end, with
  `renewal_window_days = 30` in `src/config/settings.py` (a scheduling setting, not a pricing rule). Renewal
  payments and customer renewals outside it return 409 `OUTSIDE_RENEWAL_WINDOW`.
- **A-RC-6** A non-renewable policy past `expiry_date` keeps its status; reporting treats it as expired.
  Adding `EXPIRED` is a future consideration (requires updating `docs/conventions.md` first).
- **A-RC-7** Renewal creates a **new Policy** with a new sequence number (format per AC-05, year of the new
  `effective_date`), `previous_policy_number` = the old number (unique), status `ACTIVE`; the old policy moves
  to `RENEWED`.
- **A-RC-8** Refund base (`premium_paid`) = the payment covering the current term: the issuance payment for new
  business, or the renewal payment (due date = this term's `effective_date`) for a renewal term. Endorsement
  premium deltas are not collected (see `specs/endorsement_spec.md`), so they do not change the refund base.
- **A-RC-9** Free look applies only to **new business** (`previous_policy_number` is null). Cancellation dates
  must lie within `effective_date … expiry_date`, else 422 `VALIDATION_ERROR` with `details[].code`
  `OUTSIDE_TERM`.

## Business Rules

### Rule-file fields used (exact names from `docs/conventions.md`)

| Field | Use |
|-------|-----|
| `renewal.term_months` | Length of the successor term |
| `renewal.grace_period_days` | Days after the renewal due date before an unpaid policy lapses (30 in v1, OQ-3) |
| `premium.base_rate`, `premium.minimum_premium`, `premium.factors` | Refreshed renewal premium (active version) |
| `eligibility.*` | Renewal eligibility (A-RC-4) |
| `cancellation.method` | `PRO_RATA` (only method in v1; any other value is rejected by schema) |
| `cancellation.free_look_days` | Free-look window (15 in v1, OQ-4) |
| `cancellation.admin_fee` | Flat fee deducted from pro-rata refunds (`"250.00"` in v1) |

Grace period and cancellation parameters come from the version recorded on the policy being lapsed/cancelled.

### End-of-day action (AC-07, `EndOfDayAction`)

For an `ACTIVE`/`ENDORSED`, renewable policy with renewal due date `due = expiry_date + 1 day`:

| Condition on `as_of` | Paid? | Action |
|----------------------|-------|--------|
| `as_of < due` | any | `NONE` |
| `as_of ≥ due` | yes | `RENEW` |
| `due ≤ as_of ≤ due + grace_period_days` | no | `IN_GRACE` (still covered, no change) |
| `as_of > due + grace_period_days` | no | `LAPSE` (reason `GRACE_PERIOD_EXPIRED`) |

Terminal policies (`LAPSED`, `CANCELLED`, `RENEWED`) always yield `NONE`. Example: expiry 2026-09-30 → due
2026-10-01, grace end 2026-10-31; unpaid lapses in the run for 2026-11-01 or later.

### Refund (AC-08, AC-19) — `Decimal`, quantized 0.01 `ROUND_HALF_UP` once at the end

```
term_days    = (expiry_date - effective_date).days + 1
days_elapsed = (cancellation_date - effective_date).days
unused_days  = term_days - days_elapsed
if previous_policy_number is null and days_elapsed <= free_look_days:
    refund = premium_paid                                                    (refund_type FREE_LOOK, admin_fee 0.00)
else:                                                                        # cancellation.method PRO_RATA
    refund = quantize(max(premium_paid * unused_days / term_days - admin_fee, 0), 0.01, ROUND_HALF_UP)   (refund_type PRO_RATA)
```

`days_elapsed <= free_look_days` means cancellation dates up to `effective_date + 15 days`
(effective 2026-10-01 → free look through 2026-10-16).

### End-of-day job (AC-07, AC-18)

For `as_of`, every `ACTIVE`/`ENDORSED` policy is evaluated with `renewal_action`; `RENEW` issues the successor
(A-RC-7), `LAPSE` moves the policy to `LAPSED`. Each policy is processed in its own transaction; a failure is
logged (JSON, correlation id, policy number, no PII) and reported in `failed`, and the job continues.
Idempotency is structural: `LAPSED` and `RENEWED` are terminal, so a re-run finds nothing to do; the unique
constraint on `policies.previous_policy_number` is the backstop against a second successor. Result:
`{as_of, renewed, lapsed, in_grace, not_renewable, failed}` counts plus `renewed_policies[{from, to}]`,
`lapsed_policies[]`, `failed_policies[]`. Each run appends one `AuditRecord` `RUN_END_OF_DAY` (actor = admin
or `system-eod`).

**Trigger (DEC-011).** The job has two entry points, both idempotent for the same `as_of`: the admin endpoint
`POST /api/admin/end-of-day` (actor = the admin) and the CLI composition root
`python -m src.jobs.end_of_day --as-of YYYY-MM-DD` (actor = `system-eod`, role `SYSTEM`, DEC-010). Both call
`run_end_of_day(as_of, actor_id)` in `src/service/end_of_day_service.py`; neither may run twice for a date to
any effect (AC-18).

## State Transitions Touched

Via `src/domain/policy_state_machine.py` (invalid → `InvalidPolicyStateException` → 409 `INVALID_POLICY_STATE`):

| Transition | Trigger |
|------------|---------|
| `ACTIVE`/`ENDORSED` → `LAPSED` | End-of-day `LAPSE` |
| `ACTIVE`/`ENDORSED` → `RENEWED` (+ successor *(new)* → `ACTIVE`) | End-of-day `RENEW` or customer renewal |
| `ACTIVE`/`ENDORSED` → `CANCELLED` | Cancellation |

Payments do not change status; paying a `LAPSED`/`CANCELLED`/`RENEWED` policy returns 409 `INVALID_POLICY_STATE`.

## API Endpoints

Auth stub headers `X-Actor-Id`, `X-Actor-Role`; missing actor → 401 `UNAUTHENTICATED`, wrong role → 403
`FORBIDDEN` (AC-22). Error envelope and codes: `docs/conventions.md`.

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| GET | `/api/policies/{policy_number}/renewal` | CUSTOMER (owner), ADMIN | 200 — `renewable`, `renewal_premium`, `rule_version`, `due_date`, `grace_end_date`, `paid` | 401, 403, 404, 409 `INVALID_POLICY_STATE` / `NO_PUBLISHED_VERSION` |
| POST | `/api/policies/{policy_number}/payments` (body `{amount}`) | CUSTOMER (owner) | 201 — payment id, amount, due date, `rule_version`, paid_at | 401, 403, 404, 409 `INVALID_POLICY_STATE` / `PREMIUM_ALREADY_PAID` / `OUTSIDE_RENEWAL_WINDOW`, 422 `VALIDATION_ERROR` (`AMOUNT_MISMATCH`, `NOT_RENEWABLE`, malformed) |
| POST | `/api/policies/{policy_number}/renew` | CUSTOMER (owner) | 201 — successor policy (number, dates, refreshed premium, `ACTIVE`, `previous_policy_number`) | 401, 403, 404, 409 `INVALID_POLICY_STATE` / `OUTSIDE_RENEWAL_WINDOW`, 422 `VALIDATION_ERROR` (`RENEWAL_PREMIUM_UNPAID`, `NOT_RENEWABLE`) |
| POST | `/api/admin/end-of-day` (body `{as_of}`) | ADMIN | 200 — job result | 401, 403, 422 malformed date |
| GET | `/api/policies/{policy_number}/cancellation-preview?date=YYYY-MM-DD` | CUSTOMER (owner), ADMIN | 200 — `refund_type`, `premium_paid`, `term_days`, `days_elapsed`, `unused_days`, `admin_fee`, `amount`; nothing persisted | 401, 403, 404, 409 `INVALID_POLICY_STATE`, 422 `VALIDATION_ERROR` (`date` detail code `OUTSIDE_TERM`) |
| POST | `/api/policies/{policy_number}/cancel` (body `{cancellation_date, reason}`; `reason` is non-blank free text ≤ 200 chars, e.g. "Vehicle sold") | CUSTOMER (owner), ADMIN | 200 — status `CANCELLED` + refund record | 401, 403, 404, 409 `INVALID_POLICY_STATE`, 422 `VALIDATION_ERROR` |

Admin cancellations append an `AuditRecord` `POLICY_CANCELLED`; end-of-day runs append `RUN_END_OF_DAY`.

## Data

| Table | Model | Append-only | Notes |
|-------|-------|-------------|-------|
| `premium_payments` | `PremiumPayment` | ✅ | policy id, due_date, amount `Numeric(12, 2)`, `rule_version`, actor id, paid_at; one per (policy, due_date) |
| `refunds` | `Refund` | ✅ | policy id, `refund_type` (`FREE_LOOK`/`PRO_RATA`), premium_paid, term_days, days_elapsed, unused_days, admin_fee, amount, `rule_version`, cancellation_date, reason, actor id, created_at |
| `policies` | `Policy` | — (current projection) | status; successor rows with `previous_policy_number` (unique) |
| `policy_state_transitions` | `PolicyStateTransition` | ✅ | one row per lapse / renewal (old + new) / cancellation |
| `audit_records` | `AuditRecord` | ✅ | `POLICY_CANCELLED` (admin), `RUN_END_OF_DAY` |
| `rule_set_versions` | `RuleSetVersion` | ✅ | read only |

## NFRs That Apply

- **NFR-01** premiums, payments and refunds are `Decimal`, quantized 0.01 `ROUND_HALF_UP`; no `float` in
  `renewal_rules.py` / `refund_rules.py` (hook `premium-precision-check`).
- **NFR-02** payments, refunds and transitions append-only; a refund is never edited — a correction would be a
  new row.
- **NFR-03 / NFR-06** job logs are JSON with correlation id and policy number only — no PII.
- **NFR-04** admin actions audited with actor ID; roles enforced at the API layer.

## Implementing Stories

| Story | Title | ACs |
|-------|-------|-----|
| E7-S1 | Renewal term + grace-period rules (Domain) | AC-07 |
| E7-S2 | Simulated premium payments (Service) | AC-17 |
| E7-S3 | End-of-day job: renew + lapse, idempotent (Service) | AC-07, AC-18 |
| E7-S4 | Renew API/UI + admin "run end-of-day" (UI) | AC-07, AC-18 (E2E) |
| E8-S1 | Refund rules: pro-rata, free-look, admin fee (Domain) | AC-08, AC-19 |
| E8-S2 | Cancellation service + append-only `Refund` (Service) | AC-08 |
| E8-S3 | Cancel API + UI with refund preview (UI) | AC-08, AC-19 (E2E) |

Money examples use the v1 values of `specs/stories/E2-S1.md`. MOTOR rating profile unless stated:
sum_insured 400000.00, engine_cc 998, zone `B`, ncb_percent `"0"` (v1 premium 400000.00 × 0.0310 = 12400.00 while
the vehicle is 0–5 years old). The hypothetical MOTOR v2 equals v1 except `premium.base_rate` `"0.0320"`.

## Acceptance Criteria

### AC-07 — Renewal cycle generates a new term with refreshed premium; the policy auto-lapses if premium remains unpaid beyond the configured grace period

```gherkin
Scenario: End-of-day run renews a paid policy at the cycle date with a refreshed premium
  Given policy "MO-2025-000210" is ACTIVE on MOTOR v1, premium 12400.00, vehicle_age_years 5 at issuance,
        effective_date 2025-10-01, expiry_date 2026-09-30
  And MOTOR v2 (base_rate "0.0320") is the active version
  And on 2026-09-15 GET /api/policies/MO-2025-000210/renewal quoted renewal_premium "14720.00", rule_version 2,
      due_date 2026-10-01, grace_end_date 2026-10-31
      # 400000.00 × 0.0320 × 1.15 (vehicle age advanced to 6, band 6–10) × 1.00 × 1.00 × (1 − 0.00) = 14720.00
  And customer "cust-001" paid "14720.00" on 2026-09-20 for due date 2026-10-01
  And the highest MOTOR policy number for 2026 is "MO-2026-000124"
  When admin "admin-001" POSTs /api/admin/end-of-day with as_of 2026-10-01
  Then "MO-2025-000210" moves ACTIVE -> RENEWED
  And successor "MO-2026-000125" is ACTIVE with previous_policy_number "MO-2025-000210",
      effective_date 2026-10-01, expiry_date 2027-09-30, rule_version 2 and premium 14720.00
  And the result has renewed 1 and renewed_policies [{from "MO-2025-000210", to "MO-2026-000125"}]
  And one audit_records row has action "RUN_END_OF_DAY" and actor_id "admin-001"

Scenario: Unpaid policy stays in grace, then lapses after the grace period
  Given policy "MO-2025-000300" is ACTIVE with expiry_date 2026-09-30, renewal due 2026-10-01 unpaid,
        and renewal.grace_period_days 30
  When the end-of-day job runs for 2026-10-31
  Then "MO-2025-000300" is still ACTIVE and counted in in_grace
  When the end-of-day job runs for 2026-11-01
  Then "MO-2025-000300" moves ACTIVE -> LAPSED with reason "GRACE_PERIOD_EXPIRED"
  And the result lists lapsed_policies ["MO-2025-000300"]

Scenario: Policy no longer eligible is not renewed
  Given policy "TL-2025-000002" is ACTIVE with expiry_date 2026-09-30 and insured age 60 at issuance
  And the active TERM_LIFE version has eligibility max_age 60, so the advanced age 61 is ineligible
  When the end-of-day job runs for 2026-10-01
  Then no successor is created, "TL-2025-000002" stays ACTIVE and is counted in not_renewable
  And GET /api/policies/TL-2025-000002/renewal returns "renewable" false

Scenario: Customer renews early inside the renewal window
  Given policy "TL-2025-000004" of customer "cust-004" is ACTIVE with expiry_date 2026-10-20 and TERM_LIFE term_years not exhausted
  And the business date is 2026-09-29 (window opens 2026-09-20 = expiry − 30 days)
  And the renewal premium for due date 2026-10-21 has been paid
  When customer "cust-004" POSTs /api/policies/TL-2025-000004/renew
  Then the response is 201 with a successor ACTIVE policy effective 2026-10-21 with the paid renewal premium and its rule_version
  And "TL-2025-000004" is RENEWED
  When customer "cust-004" POSTs /api/policies/TL-2025-000004/renew again
  Then the response is 409 with error code "INVALID_POLICY_STATE"

Scenario: Early renewal needs the renewal premium paid
  Given policy "TL-2025-000005" is ACTIVE with expiry_date 2026-10-20, business date 2026-09-29 and no renewal payment
  When its owner POSTs /api/policies/TL-2025-000005/renew
  Then the response is 422 with details {"field": "payment", "code": "RENEWAL_PREMIUM_UNPAID"}

Scenario: Renewal outside the window is refused
  Given policy "MO-2026-000125" has expiry_date 2027-09-30 and the business date is 2026-12-01
  When its owner POSTs /api/policies/MO-2026-000125/renew
  Then the response is 409 with error code "OUTSIDE_RENEWAL_WINDOW"
```

### AC-08 — Cancellation calculates a pro-rated refund per product rules; policy status moves to CANCELLED; the refund record is append-only

```gherkin
Scenario: Mid-term cancellation refunds pro-rata minus admin fee
  Given policy "MO-2026-000123" is ACTIVE (new business), premium 12400.00 paid at issuance,
        effective_date 2026-10-01, expiry_date 2027-09-30
  And its MOTOR v1 rule set has cancellation.method "PRO_RATA", free_look_days 15, admin_fee "250.00"
  When customer "cust-001" POSTs /api/policies/MO-2026-000123/cancel with cancellation_date 2027-04-01 and reason "Vehicle sold"
  Then term_days = 365, days_elapsed = 182, unused_days = 183
  And refund = 12400.00 × 183 / 365 − 250.00 = 5966.9863… → 5966.99 (ROUND_HALF_UP)
  And the response is 200 with status CANCELLED
  And one refunds row has refund_type PRO_RATA, premium_paid 12400.00, unused_days 183, admin_fee 250.00, amount 5966.99
  And one policy_state_transitions row ACTIVE -> CANCELLED is appended

Scenario: Refund preview matches the final refund and persists nothing
  Given the same policy
  When customer "cust-001" GETs /api/policies/MO-2026-000123/cancellation-preview?date=2027-04-01
  Then the response is 200 with amount "5966.99" and refund_type "PRO_RATA"
  And no refunds row and no transition row are added

Scenario: Admin fee never makes the refund negative
  Given the same policy and cancellation_date 2027-09-25
  Then days_elapsed = 359, unused_days = 6
  And refund = max(12400.00 × 6 / 365 − 250.00, 0) = max(203.8356… − 250.00, 0) → 0.00

Scenario: Refund records are append-only and cancellation is not repeatable
  Given "MO-2026-000123" is CANCELLED with refund row R9
  Then the refund repository exposes no update or delete operation
  When customer "cust-001" POSTs /api/policies/MO-2026-000123/cancel again
  Then the response is 409 with error code "INVALID_POLICY_STATE" and R9 is the only refund

Scenario: Admin cancellation is audited
  Given policy "MO-2026-000124" is ACTIVE
  When admin "admin-001" POSTs /api/policies/MO-2026-000124/cancel with a date inside the term
  Then one audit_records row has action "POLICY_CANCELLED", actor_id "admin-001", entity "MO-2026-000124"
```

### AC-17 — Simulated premium payment is recorded append-only; a paid policy does not lapse

```gherkin
Scenario: Paying the renewal premium records a payment and prevents lapse
  Given policy "MO-2025-000301" is ACTIVE on MOTOR v1 (active), vehicle_age_years 2 at issuance, expiry_date 2026-09-30
  And GET /api/policies/MO-2025-000301/renewal quotes renewal_premium "12400.00" (vehicle age 3, band 0–5), due 2026-10-01
  When customer "cust-001" POSTs /api/policies/MO-2025-000301/payments with amount "12400.00" on 2026-10-20 (inside grace)
  Then the response is 201
  And one premium_payments row has due_date 2026-10-01, amount 12400.00, rule_version 1, actor "cust-001"
  When the end-of-day job runs for 2026-11-01
  Then "MO-2025-000301" is RENEWED, not LAPSED, and is not in lapsed_policies

Scenario: Wrong amount and double payment are rejected
  Given policy "MO-2025-000302" has a renewal premium of 12400.00 due 2026-10-01, unpaid, business date 2026-09-25
  When its owner pays amount "12000.00"
  Then the response is 422 with details {"field": "amount", "code": "AMOUNT_MISMATCH"} and no premium_payments row is added
  Given the renewal premium for 2026-10-01 has been paid
  When its owner pays amount "12400.00" again
  Then the response is 409 with error code "PREMIUM_ALREADY_PAID"

Scenario: A lapsed policy cannot be paid
  Given policy "HH-2026-000004" is LAPSED
  When its owner pays its premium
  Then the response is 409 with error code "INVALID_POLICY_STATE"

Scenario: Payments are append-only
  Then the premium payment repository exposes add and read operations only
```

### AC-18 — End-of-day run is idempotent: re-running for the same date renews or lapses nothing twice

```gherkin
Scenario: Re-running the same date changes nothing
  Given on 2026-11-01 the end-of-day job renewed "MO-2025-000301" into "MO-2026-000126"
        and lapsed "MO-2025-000300"
  When admin "admin-001" POSTs /api/admin/end-of-day with as_of 2026-11-01 again
  Then the response is 200 with renewed 0, lapsed 0 and failed 0
  And exactly one policy has previous_policy_number "MO-2025-000301"
  And "MO-2025-000300" has exactly one transition to LAPSED
  And the policy_state_transitions row count is unchanged by the second run

Scenario: A failure for one policy does not stop the run and is picked up on re-run
  Given paid policies "MO-2025-000211" and "MO-2025-000212" are due for renewal on 2026-10-01
  And renewing "MO-2025-000211" fails with an injected repository error
  When the end-of-day job runs for 2026-10-01
  Then "MO-2025-000212" is renewed and "MO-2025-000211" is listed in failed_policies and remains ACTIVE
  And a JSON log line with the correlation id records the failure without PII
  When the error is removed and the job runs again for 2026-10-01
  Then "MO-2025-000211" is renewed once and "MO-2025-000212" is not renewed again

Scenario: Only admins can run end-of-day
  When underwriter "uw-001" POSTs /api/admin/end-of-day
  Then the response is 403 with error code "FORBIDDEN"
```

### AC-19 — Cancellation within the free-look period refunds the full premium; afterwards pro-rata minus admin fee

```gherkin
Scenario: Cancellation inside free look refunds the full premium
  Given policy "MO-2026-000123" is ACTIVE (new business), premium 12400.00 paid at issuance,
        effective_date 2026-10-01, expiry_date 2027-09-30, free_look_days 15, admin_fee "250.00"
  When its owner cancels with cancellation_date 2026-10-10 (days_elapsed 9 ≤ 15)
  Then the refund_type is FREE_LOOK and refund = 12400.00 (no admin fee)

Scenario: Last free-look day still refunds in full
  When its owner cancels with cancellation_date 2026-10-16 (days_elapsed 15 ≤ 15)
  Then the refund_type is FREE_LOOK and refund = 12400.00

Scenario: First day after free look is pro-rata minus admin fee
  When its owner cancels with cancellation_date 2026-10-17
  Then days_elapsed = 16, unused_days = 365 − 16 = 349
  And refund = 12400.00 × 349 / 365 − 250.00 = 11606.4383… → 11606.44 with refund_type PRO_RATA

Scenario: Renewal terms have no free look
  Given successor policy "MO-2026-000125" (previous_policy_number "MO-2025-000210"),
        renewal premium 14720.00 paid, effective_date 2026-10-01, expiry_date 2027-09-30
  When its owner cancels with cancellation_date 2026-10-05
  Then days_elapsed = 4, unused_days = 361
  And refund = 14720.00 × 361 / 365 − 250.00 = 14308.6849… → 14308.68 with refund_type PRO_RATA

Scenario: Cancellation date outside the term is rejected
  When the owner of "MO-2026-000123" cancels with cancellation_date 2027-10-01
  Then the response is 422 with details {"field": "cancellation_date", "code": "OUTSIDE_TERM"} and the policy is unchanged
```
