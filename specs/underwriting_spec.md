# Underwriting Spec — PolicyForge

| | |
|---|---|
| **Owns** | AC-03, AC-04, AC-09, AC-14 |
| **Epic / stories** | E4 — E4-S1, E4-S2, E4-S3, E4-S4, E4-S5 |
| **Sprint** | 2 (Quote + underwriting) |
| **Upstream** | `specs/brd/brd.md` §5.3–§5.4, §11 · `docs/conventions.md` · `specs/stories/dependency-graph.md` |

## Purpose

Turn a priced quote into an **application** (KYC stub + risk inputs), validate it against the product's
**active** rule set, and return an underwriting **decision** — `AUTO_BIND`, `MANUAL_REVIEW` or `DECLINE` —
whose reason codes come from that rule set. Give underwriters a manual review queue to approve or decline
referred cases, and give admins the ability to review the queue and override a `DECLINE`. Every
underwriter/admin action is audited with the actor ID.

## Scope

**In scope**

- Application submission from an existing quote, with KYC stub (name, date of birth, Aadhaar, PAN,
  address), plus a health declaration for TERM_LIFE. Risk inputs are the quote's validated inputs.
- Validation against `eligibility` of the active rule-set version (422 with field errors on failure).
- Automatic decision from `underwriting.rules[]` of the active version; reason codes and descriptions from
  `underwriting.reason_codes`.
- Manual review queue (`MANUAL_REVIEW` cases) and underwriter `APPROVE` / `DECLINE` with reason codes.
- Admin queue review (manual + declined cases) and admin override `DECLINED → AUTO_BIND` with reason code +
  comment.
- Audit of every underwriter/admin action (`audit_records`) with actor ID.
- UI: Apply screen (status + reason codes), Underwriter Workbench, Admin Underwriting Review (E4-S5).

**Out of scope**

- Real KYC document verification, bureau / health-record / vehicle-record lookups (stubs only).
- Overriding `MANUAL_REVIEW` or `AUTO_BIND` outcomes (only `DECLINE` is overridable).
- Policy issuance itself (see `specs/policy-issuance_spec.md`); this spec ends at `AUTO_BIND`.
- Editing a submitted application (a new application must be submitted).

## Assumptions

- **A-UW-1** An application is always created from a `quote_id` (UUID4). If the quote's `rule_version` is no
  longer the active version for the product, submission is rejected with 409 `QUOTE_STALE` and the customer
  must re-quote (keeps premium and underwriting on the same version).
- **A-UW-2** Eligibility failures (age, sum insured bounds, missing/invalid fields) are **validation errors
  (422 `VALIDATION_ERROR`)**, not `DECLINE` decisions; nothing is persisted.
- **A-UW-3** `AUTO_BIND` carries an empty reason-code list; `MANUAL_REVIEW` and `DECLINE` carry ≥ 1 code.
- **A-UW-4** Underwriter decision and admin override reason codes must be keys of `underwriting.reason_codes`
  in the rule-set version the application was decided on. Each v1 rule file carries the manual codes
  `<P>-UW-900` "Underwriter approved", `<P>-UW-901` "Admin override: risk accepted" and `<P>-UW-902`
  "Underwriter declined" (E2-S1); automatic codes may also be cited.
- **A-UW-5** Decision and submission are synchronous in one request: `SUBMITTED → UNDERWRITING → <outcome>`.
- **A-UW-6** Applicant age for eligibility is the age on the quote (`age` / `owner_age` / `proposer_age`),
  passed into the pure domain as an int (the domain never reads the clock).

## Business Rules

### Rule-file fields used (exact names from `docs/conventions.md`)

| Field | Use |
|-------|-----|
| `product`, `version`, `status` | Only the single `PUBLISHED` active version for the product is used |
| `eligibility.min_age`, `eligibility.max_age` | Applicant age must be within bounds |
| `eligibility.min_sum_insured`, `eligibility.max_sum_insured` | Quote sum insured must be within bounds (Decimal compare) |
| `underwriting.rules[].when` | `<field> <op> <value>` clauses joined by ` and ` (conventions), evaluated by `src/domain/underwriting_rules.py` |
| `underwriting.rules[].decision` | `MANUAL_REVIEW` or `DECLINE` (an unmatched application is `AUTO_BIND`) |
| `underwriting.rules[].reason_code` | Must be a key of `underwriting.reason_codes`; prefix `TL-UW-` / `MO-UW-` / `HH-UW-` |
| `underwriting.reason_codes` | Code → human-readable description returned to the caller |

### Decision algorithm (pure domain, E4-S1)

1. Evaluate every rule in `underwriting.rules[]` against the validated inputs (quote inputs plus derived
   `age_at_term_end` and, for TERM_LIFE, `has_pre_existing_condition` from the health declaration).
2. Collect all matching rules. Outcome precedence: any `DECLINE` → `DECLINE`; else any `MANUAL_REVIEW` →
   `MANUAL_REVIEW`; else `AUTO_BIND`.
3. `reason_codes` = codes of **all** matching rules, de-duplicated and sorted ascending.
4. The decision records `rule_version`; descriptions are resolved from that version's
   `underwriting.reason_codes` (never hard-coded). A rule citing an undefined code raises `UnknownReasonCodeError`.
5. Deterministic: same inputs + same version → same decision and codes.

v1 MOTOR rules (E2-S1): `vehicle_age_years > 15` → `DECLINE` `MO-UW-001`; `vehicle_age_years > 10` →
`MANUAL_REVIEW` `MO-UW-002`; `sum_insured > 2500000` → `MANUAL_REVIEW` `MO-UW-003`.

### Application inputs

- KYC stub: `full_name`, `date_of_birth`, `aadhaar` (12 digits), `pan` (pattern `^[A-Z]{5}[0-9]{4}[A-Z]$`),
  `address`. Synthetic only (Aadhaar `999900000001`, PAN `AAAAA0001A`).
- TERM_LIFE only: `health_declaration` {`has_pre_existing_condition` (bool), `details` (string)}.
- Risk inputs are the quote's inputs (canonical names in `docs/conventions.md`), not re-entered.
- Aadhaar, PAN and `health_declaration` are **never logged**; stored and returned only masked
  (`aadhaar_masked` `XXXX-XXXX-0001`, `pan_masked` `XXXXX0001X`).

### Manual review and override

- Underwriter decision on a `MANUAL_REVIEW` application: body `{decision: APPROVE | DECLINE, reason_codes, comment}`
  with ≥ 1 reason code. Appends an `UnderwritingDecision` (`AUTO_BIND` for `APPROVE`, `DECLINE` for `DECLINE`)
  with `decided_by = X-Actor-Id`, moves the application to `AUTO_BIND` / `DECLINED`, and appends an
  `AuditRecord` (`action = UW_APPROVE` / `UW_DECLINE`).
- Admin override of a `DECLINED` application: body `{reason_code, comment}` — exactly one reason code + a
  comment of 10–500 characters. Appends an `UnderwritingOverride` (links the overridden decision, `from_status`
  `DECLINED`, `to_status` `AUTO_BIND`), moves the application to `AUTO_BIND`, and appends an `AuditRecord`
  (`action = UW_OVERRIDE_DECLINE`, comment in `detail`). Override and audit rows are written in one transaction.

## State Transitions Touched

`ApplicationStatus` (from `docs/conventions.md`):

| From | To | Trigger |
|------|----|---------|
| — | `SUBMITTED` | Valid application submitted |
| `SUBMITTED` | `UNDERWRITING` | Immediately after persistence |
| `UNDERWRITING` | `AUTO_BIND` / `MANUAL_REVIEW` / `DECLINED` | Automatic decision |
| `MANUAL_REVIEW` | `AUTO_BIND` / `DECLINED` | Underwriter decision (AC-14) |
| `DECLINED` | `AUTO_BIND` | Admin override (AC-09) |

`AUTO_BIND → ISSUED` belongs to `specs/policy-issuance_spec.md`. Any other transition returns 409
`INVALID_APPLICATION_STATE` and changes nothing. No `PolicyStatus` transitions are touched.

## API Endpoints

Auth stub headers `X-Actor-Id`, `X-Actor-Role`; missing actor → 401 `UNAUTHENTICATED`, wrong role → 403
`FORBIDDEN` (AC-22). Error envelope and codes: `docs/conventions.md`.

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| POST | `/api/applications` | CUSTOMER | 201 — `application_id`, status, decision, reason codes (+ descriptions), `rule_version`, masked KYC | 401, 403, 404 `NOT_FOUND` (unknown quote), 409 `QUOTE_STALE`, 422 `VALIDATION_ERROR` |
| GET | `/api/applications/{application_id}` | CUSTOMER (owner), UNDERWRITER, ADMIN | 200 — status, `status_history`, decisions, reason codes, masked KYC | 401, 404 (incl. another customer's application) |
| GET | `/api/underwriting/queue` (`?status=MANUAL_REVIEW\|DECLINED`) | UNDERWRITER (`MANUAL_REVIEW` only), ADMIN (both; default both) | 200 — cases oldest first with status, reason codes, rule version, decision history | 401, 403 (UNDERWRITER asking for `DECLINED`), 422 bad status |
| POST | `/api/underwriting/applications/{application_id}/decision` | UNDERWRITER | 200 — new decision + application status | 401, 403, 404, 409 `INVALID_APPLICATION_STATE`, 422 `VALIDATION_ERROR` (unknown reason code, empty list, bad decision value) |
| POST | `/api/underwriting/applications/{application_id}/override` | ADMIN | 200 — override + application status `AUTO_BIND` | 401, 403, 404, 409 `INVALID_APPLICATION_STATE`, 422 `VALIDATION_ERROR` (comment length, unknown reason code) |
| GET | `/api/underwriting/applications/{application_id}/audit` | UNDERWRITER, ADMIN | 200 — decisions, overrides and audit rows | 401, 403, 404 |

## Data

| Table | Model | Append-only | Notes |
|-------|-------|-------------|-------|
| `applications` | `Application` | — (status projection) | quote id, product, customer id, masked KYC (`aadhaar_masked`, `pan_masked`), status, status history |
| `underwriting_decisions` | `UnderwritingDecision` | ✅ | application id, `Decision`, reason codes JSON, product, `rule_version`, `decided_by` (`SYSTEM` for automatic), comment, created_at |
| `underwriting_overrides` | `UnderwritingOverride` | ✅ | application id, overridden decision id, from_status, to_status, reason code, comment, actor id, created_at |
| `audit_records` | `AuditRecord` | ✅ | actor id, role, action, entity type/id, detail (no PII), correlation id, created_at |
| `quotes`, `rule_set_versions` | read only | — / ✅ | Owned by quote-engine / product-catalog specs |

## NFRs That Apply

- **NFR-02** decisions, overrides and audit rows are append-only (repositories expose `add` + reads only).
- **NFR-03** Aadhaar, PAN and health declarations never reach logs; use `src/lib/logging.py` `mask_pii`.
- **NFR-04** role checks in `src/api/deps.py`; every underwriter/admin action writes an `AuditRecord` with actor ID.
- **NFR-06** decision logs are JSON lines carrying `X-Correlation-ID`.
- **NFR-08** domain modules (`application_validator.py`, `underwriting_rules.py`) are pure — no I/O, logging or clock.

## Implementing Stories

| Story | Title | ACs |
|-------|-------|-----|
| E4-S1 | Application validator + underwriting decision rules (Domain) | AC-03, AC-04 |
| E4-S2 | Application submit → decide: `Application` + `UnderwritingDecision` (Service) | AC-03, AC-04 |
| E4-S3 | Manual review queue: underwriter approve/decline, audited (Service) | AC-14 |
| E4-S4 | Admin queue review + DECLINE override, audited (API) | AC-09 |
| E4-S5 | Apply UI + Underwriter Workbench UI (UI) | AC-03, AC-04, AC-09, AC-14 (E2E) |

## Acceptance Criteria

### AC-03 — Application captures KYC stub + risk inputs, validates them against the product rule set, and progresses the case to underwriting

```gherkin
Scenario: Valid MOTOR application progresses to underwriting
  Given MOTOR v1 is the active PUBLISHED version with eligibility min_age 18, max_age 75,
        min_sum_insured "100000.00" and max_sum_insured "5000000.00"
  And quote Q1 exists for MOTOR v1 with inputs sum_insured "500000.00", owner_age 30, vehicle_age_years 3,
      engine_cc 1200, zone "A", ncb_percent "20" and premium "14322.00"
  When customer "cust-001" POSTs /api/applications with quote_id Q1 and
       kyc { full_name "Test Customer 01", date_of_birth "1996-04-01", aadhaar "999900000001",
             pan "AAAAA0001A", address "1 Sample Street, Testville" }
  Then the response is 201
  And the application passed through SUBMITTED and UNDERWRITING and now has status AUTO_BIND
  And the response shows aadhaar "XXXX-XXXX-0001" and pan "XXXXX0001X" and never the raw values
  And no log line contains "999900000001" or "AAAAA0001A"

Scenario: Applicant outside eligibility is rejected with field errors and nothing is persisted
  Given MOTOR v1 is active with eligibility max_age 75
  When customer "cust-002" submits an application whose quote carries owner_age 76
  Then the response is 422 with error code "VALIDATION_ERROR" and details {"field": "owner_age", "code": "OUT_OF_RANGE"}
  And no row is added to applications or underwriting_decisions

Scenario: Malformed KYC stub is rejected
  When customer "cust-003" submits an application with pan "12345" and aadhaar "99990000"
  Then the response is 422 with details {"field": "kyc.pan", "code": "INVALID_FORMAT"} and {"field": "kyc.aadhaar", "code": "INVALID_FORMAT"}
  And no row is added to applications

Scenario: Quote priced on a superseded version must be re-quoted
  Given quote Q2 was priced on MOTOR v1 and MOTOR v2 has since been published as active
  When customer "cust-001" submits an application for quote Q2
  Then the response is 409 with error code "QUOTE_STALE"
```

### AC-04 — Underwriting returns AUTO_BIND / MANUAL_REVIEW / DECLINE with reason codes referenced from the active policy version

```gherkin
Background:
  Given MOTOR v1 is active with underwriting.rules
    | when                   | decision      | reason_code |
    | vehicle_age_years > 15 | DECLINE       | MO-UW-001   |
    | vehicle_age_years > 10 | MANUAL_REVIEW | MO-UW-002   |
    | sum_insured > 2500000  | MANUAL_REVIEW | MO-UW-003   |
  And underwriting.reason_codes describes MO-UW-001 as "Vehicle older than 15 years"

Scenario: No rule matches -> AUTO_BIND
  When an application is submitted for a quote with vehicle_age_years 3 and sum_insured "500000.00"
  Then the decision is AUTO_BIND with reason_codes []
  And the application status is AUTO_BIND
  And the underwriting_decisions row records product MOTOR, rule_version 1 and decided_by "SYSTEM"

Scenario: Referral rule matches -> MANUAL_REVIEW
  When an application is submitted for a quote with vehicle_age_years 12 and sum_insured "500000.00"
  Then the decision is MANUAL_REVIEW with reason_codes ["MO-UW-002"]
  And the response describes MO-UW-002 with its v1 description
  And the application appears in GET /api/underwriting/queue for underwriter "uw-001"

Scenario: Decline beats referral -> DECLINE with every matching code
  When an application is submitted for a quote with vehicle_age_years 16 and sum_insured "3000000.00"
  Then the decision is DECLINE with reason_codes ["MO-UW-001", "MO-UW-002", "MO-UW-003"]
  And the application status is DECLINED

Scenario: Reason codes follow the active version
  Given MOTOR v2 is published and active, with "MO-UW-002" described as "Vehicle older than 10 years (v2 wording)"
  When a new application with vehicle_age_years 12 is decided
  Then its decision references MOTOR v2 and uses the v2 description of MO-UW-002
  And an earlier decision made on MOTOR v1 still shows the v1 description

Scenario: Decision is deterministic
  Given identical KYC and quote inputs submitted twice on MOTOR v1
  Then both decisions have the same outcome and the same reason_codes
```

### AC-09 — Admin can review the manual underwriting queue and override a DECLINE decision with reason code and comment; the override is audited

```gherkin
Scenario: Admin reviews the queue and overrides a DECLINE
  Given application A45 (MOTOR v1) is DECLINED with reason_codes ["MO-UW-001", "MO-UW-002"]
  And MOTOR v1 underwriting.reason_codes contains "MO-UW-901": "Admin override: risk accepted"
  When admin "admin-001" GETs /api/underwriting/queue?status=DECLINED
  Then the response is 200 and includes A45 with reason code MO-UW-001 and its decision history
  When admin "admin-001" POSTs /api/underwriting/applications/A45/override
       with reason_code "MO-UW-901" and comment "Vehicle restored; valid fitness certificate seen"
  Then the response is 200 and A45 has status AUTO_BIND
  And one underwriting_overrides row links A45, the DECLINE decision, "MO-UW-901",
      the comment and actor "admin-001"
  And one audit_records row has action "UW_OVERRIDE_DECLINE", actor_id "admin-001", actor_role "ADMIN", entity A45
  And the original DECLINE row in underwriting_decisions is unchanged

Scenario: Override requires a valid comment and a known reason code
  Given application A46 is DECLINED
  When admin "admin-001" overrides it with reason_code "MO-UW-901" and comment "ok"
  Then the response is 422 with details {"field": "comment", "code": "OUT_OF_RANGE"}
  When admin "admin-001" overrides it with reason_code "MO-UW-999" and comment "Evidence reviewed in full"
  Then the response is 422 with details {"field": "reason_code", "code": "UNKNOWN_REASON_CODE"}
  And A46 remains DECLINED and no override or audit row is added

Scenario: Only a DECLINE can be overridden
  Given application A47 is MANUAL_REVIEW
  When admin "admin-001" POSTs /api/underwriting/applications/A47/override
  Then the response is 409 with error code "INVALID_APPLICATION_STATE" and A47 remains MANUAL_REVIEW

Scenario: Non-admin cannot override
  When underwriter "uw-001" POSTs /api/underwriting/applications/A45/override
  Then the response is 403 with error code "FORBIDDEN"
  When a request without X-Actor-Id POSTs the same override
  Then the response is 401 with error code "UNAUTHENTICATED"
```

### AC-14 — Underwriter approves or declines a MANUAL_REVIEW case with reason codes; the decision is audited with actor ID

```gherkin
Scenario: Underwriter approves a referred case
  Given application A52 (MOTOR v1) is MANUAL_REVIEW with reason_codes ["MO-UW-002"]
  And MOTOR v1 underwriting.reason_codes contains "MO-UW-900": "Underwriter approved"
  When underwriter "uw-001" POSTs /api/underwriting/applications/A52/decision
       with decision "APPROVE", reason_codes ["MO-UW-900"], comment "Vehicle inspected, condition good"
  Then the response is 200 and A52 has status AUTO_BIND
  And a new underwriting_decisions row has decision AUTO_BIND, decided_by "uw-001", reason_codes ["MO-UW-900"]
  And the earlier MANUAL_REVIEW decision row is unchanged
  And one audit_records row has action "UW_APPROVE", actor_id "uw-001", actor_role "UNDERWRITER", entity A52

Scenario: Underwriter declines a referred case
  Given application A53 is MANUAL_REVIEW
  When underwriter "uw-002" decides "DECLINE" with reason_codes ["MO-UW-902"]
  Then A53 has status DECLINED and the decision and audit rows (action "UW_DECLINE") carry actor "uw-002"

Scenario: Decision must carry at least one valid reason code
  Given application A54 is MANUAL_REVIEW
  When underwriter "uw-001" decides "DECLINE" with reason_codes []
  Then the response is 422 with details {"field": "reason_codes", "code": "REQUIRED"}
  When underwriter "uw-001" decides "DECLINE" with reason_codes ["HH-UW-001"]
  Then the response is 422 with details {"field": "reason_codes", "code": "UNKNOWN_REASON_CODE"} because HH-UW-001 is not in MOTOR v1 underwriting.reason_codes
  And A54 remains MANUAL_REVIEW

Scenario: Only MANUAL_REVIEW cases can be decided, only by underwriters
  Given application A55 is AUTO_BIND
  When underwriter "uw-001" POSTs a decision for A55
  Then the response is 409 with error code "INVALID_APPLICATION_STATE"
  When customer "cust-001" POSTs a decision for A52
  Then the response is 403 with error code "FORBIDDEN"
```
