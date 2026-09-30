# PolicyForge — API Contracts

> **Authority.** This file **supersedes the "API endpoints" table in `docs/conventions.md` for paths, roles and
> shapes** (as that table anticipates). It contains exactly the 26 endpoints of that table — no more, no fewer.
> A new endpoint is added here (and to `api-contracts.schema.json`) before any code uses it. Error codes,
> detail codes, audit actions, enums and formulas remain owned by `docs/conventions.md` and are used verbatim.
> Machine-readable twin: `specs/design/api-contracts.schema.json` (OpenAPI 3.0.3).

---

## 0. Common conventions

### 0.1 Base URL and prefix

- API: `http://localhost:8000`. All routes are under `/api`; `GET /health` is the only un-prefixed route.
- JSON only (`Content-Type: application/json`). Unknown body fields → 422 `UNKNOWN_FIELD`.

### 0.2 Headers

| Header | Direction | Required | Notes |
|--------|-----------|----------|-------|
| `X-Actor-Id` | request | every `/api/*` route | Opaque id, e.g. `cust-001`, `uw-001`, `admin-001`. Missing/blank → 401 `UNAUTHENTICATED`. |
| `X-Actor-Role` | request | every `/api/*` route | `CUSTOMER` \| `UNDERWRITER` \| `ADMIN`. Missing, unknown (`ROOT`, `SUPERUSER`) **or `SYSTEM`** → 401 `UNAUTHENTICATED` (DEC-010: `SYSTEM` is internal to the scheduler `system-eod`). |
| `X-Correlation-ID` | request (optional) / response (always) | — | Echoed if supplied, else a UUID4 is generated; present on **every** response including errors and `/health` (AC-23). |

Role check order (in `src/api/deps.py`): headers → 401; role not allowed on route → 403 `FORBIDDEN`; then
request validation → 422; then resource lookup / owner scoping → 404; then business rules → 409.
(403 is decided before the service runs; AC-22.)

### 0.3 Ownership

"owner" = the CUSTOMER whose `X-Actor-Id` created the quote / application / policy (a renewal successor
inherits the owner). A CUSTOMER addressing another customer's resource gets **404 `NOT_FOUND`** — identical to
an unknown id (no existence leak).

### 0.4 Value formats

| Type | Format | Example |
|------|--------|---------|
| Money | JSON **string**, two decimals, `^-?\d+\.\d{2}$`; a JSON number → 422 `MONEY_MUST_BE_STRING` | `"14322.00"`, `"-1554.25"` |
| Date | ISO `YYYY-MM-DD` | `"2026-10-01"` |
| Timestamp | ISO 8601 UTC | `"2026-10-01T09:30:00Z"` |
| `quote_id`, `application_id` | UUID4 string | `"3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04"` |
| Policy number | `<TL\|MO\|HH>-<YYYY>-<6-digit seq>` | `"MO-2026-000123"` |
| Product | `TERM_LIFE` \| `MOTOR` \| `HOUSEHOLD` | |
| Currency | `"INR"` | |

### 0.5 Error envelope (every non-2xx)

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed",
             "details": [ { "field": "kyc.pan", "code": "INVALID_FORMAT" } ] } }
```

- 422: `details` = list of **all** failing fields `{field, code}` (`field` may be a dotted path).
- `INVALID_POLICY_STATE`: `details` = `{"current": "<PolicyStatus>", "target": "<PolicyStatus>"}`.
- `INVALID_APPLICATION_STATE`: `details` = `{"current": "<ApplicationStatus>", "required": "<ApplicationStatus>"}`.
- Otherwise `details` = `null`.

| Code | HTTP | Raised when |
|------|------|-------------|
| `VALIDATION_ERROR` | 422 | Body/query/rule-file validation fails (field errors in `details`) |
| `UNAUTHENTICATED` | 401 | `X-Actor-Id` or `X-Actor-Role` missing, or role not in `ActorRole` (incl. `SYSTEM` from a header) |
| `FORBIDDEN` | 403 | Role not allowed on the route |
| `NOT_FOUND` | 404 | Unknown product, version, quote, application or policy — or another customer's |
| `NO_PUBLISHED_VERSION` | 409 | Product has no PUBLISHED rule version (quote/renewal refused, no fallback) |
| `VERSION_IMMUTABLE` | 409 | Publishing or changing an already PUBLISHED version |
| `DRAFT_ALREADY_OPEN` | 409 | Creating a DRAFT while the product already has an open DRAFT |
| `INVALID_POLICY_STATE` | 409 | `InvalidPolicyStateException` — disallowed transition or action on a terminal policy |
| `INVALID_APPLICATION_STATE` | 409 | Application not in the status the action needs |
| `QUOTE_STALE` | 409 | Quote's rule version is no longer the product's active version |
| `PREMIUM_ALREADY_PAID` | 409 | A payment already exists for that due date |
| `OUTSIDE_RENEWAL_WINDOW` | 409 | Renewal payment/renew before `expiry_date − renewal_window_days` or after grace end |

Detail codes (`details[].code`): `REQUIRED`, `OUT_OF_RANGE`, `INVALID_FORMAT`, `UNKNOWN_CODE`, `UNKNOWN_FIELD`,
`MONEY_MUST_BE_STRING`, `NOT_ALLOWED`, `UNCHANGED`, `SHARE_EXCEEDS_100`, `AMOUNT_MISMATCH`, `OUTSIDE_TERM`,
`NOT_RENEWABLE`, `RENEWAL_PREMIUM_UNPAID`, `UNKNOWN_REASON_CODE`, `SCHEMA_VIOLATION`.

Unhandled failures (e.g. the injected repository error in AC-06) return **HTTP 500** with the same envelope and
roll the transaction back. The conventions error table defines `INTERNAL_ERROR` (500) for this case (OI-3 RESOLVED).

### 0.6 Rate limits and auth

No rate limiting (single-instance local demo; production concerns are out of scope, brief §6.3).
Authentication is the documented role-header stub — no tokens, no sessions.

### 0.7 Endpoint index (26)

| # | Method | Path | Roles | Audit action |
|---|--------|------|-------|--------------|
| 1 | GET | `/health` | public | — |
| 2 | GET | `/api/products` | CUSTOMER, UNDERWRITER, ADMIN | — |
| 3 | GET | `/api/products/{product}/versions` | CUSTOMER, UNDERWRITER, ADMIN | — |
| 4 | POST | `/api/products/{product}/versions` | ADMIN | `RULE_VERSION_DRAFT_CREATED` |
| 5 | PUT | `/api/products/{product}/versions/{version}` | ADMIN | `RULE_VERSION_DRAFT_REPLACED` |
| 6 | POST | `/api/products/{product}/versions/{version}/publish` | ADMIN | `RULE_VERSION_PUBLISHED` |
| 7 | POST | `/api/quotes` | CUSTOMER | — |
| 8 | GET | `/api/quotes/{quote_id}` | CUSTOMER (owner), UNDERWRITER, ADMIN | — |
| 9 | GET | `/api/quotes/{quote_id}/reprice` | CUSTOMER (owner), UNDERWRITER, ADMIN | — |
| 10 | POST | `/api/applications` | CUSTOMER | — |
| 11 | GET | `/api/applications/{application_id}` | CUSTOMER (owner), UNDERWRITER, ADMIN | — |
| 12 | GET | `/api/underwriting/queue` | UNDERWRITER (MANUAL_REVIEW only), ADMIN | — |
| 13 | POST | `/api/underwriting/applications/{application_id}/decision` | UNDERWRITER | `UW_APPROVE` / `UW_DECLINE` |
| 14 | POST | `/api/underwriting/applications/{application_id}/override` | ADMIN | `UW_OVERRIDE_DECLINE` |
| 15 | GET | `/api/underwriting/applications/{application_id}/audit` | UNDERWRITER, ADMIN | — |
| 16 | POST | `/api/applications/{application_id}/issue` | CUSTOMER (owner), ADMIN | `POLICY_ISSUED` (ADMIN only) |
| 17 | GET | `/api/policies` | CUSTOMER (own), UNDERWRITER, ADMIN | — |
| 18 | GET | `/api/policies/{policy_number}` | CUSTOMER (owner), UNDERWRITER, ADMIN | — |
| 19 | POST | `/api/policies/{policy_number}/endorsements` | CUSTOMER (owner), ADMIN | `ENDORSEMENT_CREATED` (ADMIN, non-preview) |
| 20 | GET | `/api/policies/{policy_number}/renewal` | CUSTOMER (owner), ADMIN | — |
| 21 | POST | `/api/policies/{policy_number}/renew` | CUSTOMER (owner) | — |
| 22 | POST | `/api/policies/{policy_number}/payments` | CUSTOMER (owner) | — |
| 23 | GET | `/api/policies/{policy_number}/cancellation-preview` | CUSTOMER (owner), ADMIN | — |
| 24 | POST | `/api/policies/{policy_number}/cancel` | CUSTOMER (owner), ADMIN | `POLICY_CANCELLED` (ADMIN only) |
| 25 | POST | `/api/admin/end-of-day` | ADMIN | `RUN_END_OF_DAY` |
| 26 | GET | `/api/admin/portfolio` | ADMIN | — |

Customer actions are not written to `audit_records`; they are traced by the append-only domain rows
(`quotes`, `underwriting_decisions`, `policy_state_transitions`, `endorsements`, `premium_payments`, `refunds`).
The end-of-day scheduler (`system-eod`, `SYSTEM`) calls the service directly, not this API.

---

## 1. Shared response objects

**PolicySummary**

```json
{ "policy_number": "MO-2026-000123", "product": "MOTOR", "status": "ACTIVE", "rule_version": 1,
  "sum_insured": "400000.00", "premium": "12400.00", "currency": "INR",
  "effective_date": "2026-10-01", "expiry_date": "2027-09-30",
  "premium_due_date": "2026-10-01", "next_premium_due_date": "2027-10-01",
  "previous_policy_number": null }
```

`next_premium_due_date` = `expiry_date + 1 day` (renewal due date). `premium_due_date` = `effective_date`.

**RuleVersion** — `{product, version, status: "DRAFT"|"PUBLISHED", effective_from, is_active, created_at, rules}`
where `rules` is the full rule-file body (money/rates as strings).

**Decision** — `{decision_id, decision: "AUTO_BIND"|"MANUAL_REVIEW"|"DECLINE", reason_codes: [string],
reasons: [{code, description}], rule_version, decided_by, comment, created_at}` (`decided_by` = `"SYSTEM"` for
automatic decisions).

**Override** — `{override_id, overridden_decision_id, from_status: "DECLINED", to_status: "AUTO_BIND",
reason_code, comment, actor_id, created_at}`.

**RefundBreakdown** — `{policy_number, cancellation_date, refund_type: "FREE_LOOK"|"PRO_RATA", premium_paid,
term_days, days_elapsed, unused_days, admin_fee, amount, rule_version}`.

---

## 2. Endpoints

### 2.1 `GET /health`

| | |
|---|---|
| Roles | public — no `X-Actor-*` headers required |
| Owner spec / story | app_spec · E1-S1 (AC-21, NFR-07) |
| Audit | — |

**Success 200**
```json
{ "status": "ok" }
```
Within 1 s of startup; carries `X-Correlation-ID`.
**Errors** — none.

---

### 2.2 `GET /api/products`

| | |
|---|---|
| Roles | CUSTOMER, UNDERWRITER, ADMIN |
| Owner | product-catalog · E2-S4 (AC-02) |
| Audit | — |

**Success 200** — array, ordered `TERM_LIFE`, `MOTOR`, `HOUSEHOLD`:
```json
[ { "product": "TERM_LIFE", "name": "Term Life", "active_version": 1, "currency": "INR" },
  { "product": "MOTOR", "name": "Motor", "active_version": 1, "currency": "INR" },
  { "product": "HOUSEHOLD", "name": "Household", "active_version": 1, "currency": "INR" } ]
```
`active_version` is `null` when the product has no PUBLISHED version.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |

---

### 2.3 `GET /api/products/{product}/versions`

| | |
|---|---|
| Roles | CUSTOMER, UNDERWRITER, ADMIN |
| Path | `product` — `ProductCode` |
| Owner | product-catalog · E2-S4 (AC-11) |
| Audit | — |

**Success 200** — one entry per version (current = latest `rule_set_versions` row), ascending `version`;
exactly one `is_active: true` when any version is PUBLISHED.
```json
[ { "product": "MOTOR", "version": 1, "status": "PUBLISHED", "effective_from": "2026-01-01",
    "is_active": false, "created_at": "2026-01-01T00:00:00Z",
    "rules": { "product": "MOTOR", "version": 1, "status": "PUBLISHED", "premium": { "base_rate": "0.0310", "...": "..." } } },
  { "product": "MOTOR", "version": 2, "status": "PUBLISHED", "effective_from": "2026-11-01",
    "is_active": true, "created_at": "2026-10-20T10:00:00Z",
    "rules": { "product": "MOTOR", "version": 2, "status": "PUBLISHED", "premium": { "base_rate": "0.0320", "...": "..." } } } ]
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `NOT_FOUND` | 404 | unknown product code |

---

### 2.4 `POST /api/products/{product}/versions` — create DRAFT

| | |
|---|---|
| Roles | ADMIN |
| Path | `product` — `ProductCode` |
| Owner | product-catalog · E2-S3, E2-S4 (AC-11) |
| Audit | `RULE_VERSION_DRAFT_CREATED`, entity `RULE_SET_VERSION`, `entity_id` `"<product>:v<version>"` |

**Request body** — a full rule-file JSON (shape in `docs/conventions.md` → Rule-file shape; validated against
`backend/policy_rules/schema/rule-file.schema.json`). `product` must equal the path product. The server assigns
`version` = highest existing + 1 and `status` = `DRAFT`; if the body includes `version`/`status` they must equal
those values.
```json
{ "product": "MOTOR", "version": 2, "status": "DRAFT", "effective_from": "2026-11-01", "currency": "INR",
  "premium": { "base_rate": "0.0320", "minimum_premium": "2500.00", "factors": { "vehicle_age_bands": [ { "min": 0, "max": 5, "multiplier": "1.00" } ], "engine_cc_bands": [], "ncb_discounts": {}, "zone_rates": {} } },
  "eligibility": { "min_age": 18, "max_age": 75, "min_sum_insured": "100000.00", "max_sum_insured": "5000000.00" },
  "underwriting": { "rules": [ { "when": "vehicle_age_years > 15", "decision": "DECLINE", "reason_code": "MO-UW-001" } ],
                    "reason_codes": { "MO-UW-001": "Vehicle older than 15 years" } },
  "endorsement": { "allowed_types": ["CHANGE_ADDRESS", "ADD_NOMINEE", "CHANGE_SUM_INSURED"] },
  "renewal": { "term_months": 12, "grace_period_days": 30 },
  "cancellation": { "method": "PRO_RATA", "free_look_days": 15, "admin_fee": "250.00" } }
```

**Success 201**
```json
{ "product": "MOTOR", "version": 2, "status": "DRAFT" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER |
| `NOT_FOUND` | 404 | unknown product code |
| `DRAFT_ALREADY_OPEN` | 409 | product already has an open DRAFT |
| `VALIDATION_ERROR` | 422 | schema violation (`SCHEMA_VIOLATION`, dotted path e.g. `premium.factors.zone_rates`), money as number (`MONEY_MUST_BE_STRING`), `min_age > max_age` (`OUT_OF_RANGE` on `eligibility.min_age`), foreign factor keys / reason-code prefix, product mismatch |

---

### 2.5 `PUT /api/products/{product}/versions/{version}` — replace an open DRAFT (DEC-009)

| | |
|---|---|
| Roles | ADMIN |
| Path | `product` — `ProductCode`; `version` — int ≥ 1 |
| Owner | product-catalog · E2-S3, E2-S4 (DEC-009) |
| Audit | `RULE_VERSION_DRAFT_REPLACED`, entity `RULE_SET_VERSION`, `entity_id` `"<product>:v<version>"` (OI-1 RESOLVED) |

**Request body** — full rule-file JSON as in 2.4; `product` = path product, `version` = path version, `status`
`DRAFT` (or omitted). Appends a **new** `rule_set_versions` row for the same (`product`, `version`); nothing is
updated or deleted.

**Success 200**
```json
{ "product": "MOTOR", "version": 2, "status": "DRAFT" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER |
| `NOT_FOUND` | 404 | unknown product or version |
| `VERSION_IMMUTABLE` | 409 | the version is PUBLISHED |
| `VALIDATION_ERROR` | 422 | as in 2.4 |

---

### 2.6 `POST /api/products/{product}/versions/{version}/publish`

| | |
|---|---|
| Roles | ADMIN |
| Path | `product`, `version` |
| Body | none |
| Owner | product-catalog · E2-S3, E2-S4 (AC-11, AC-22) |
| Audit | `RULE_VERSION_PUBLISHED`, entity `RULE_SET_VERSION` |

Re-validates the DRAFT body, appends a `PUBLISHED` row (only `status` changes); the version becomes the active
one (highest PUBLISHED).

**Success 200**
```json
{ "product": "MOTOR", "version": 2, "status": "PUBLISHED", "is_active": true }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER (no row written) |
| `NOT_FOUND` | 404 | unknown product or version |
| `VERSION_IMMUTABLE` | 409 | version already PUBLISHED |
| `VALIDATION_ERROR` | 422 | DRAFT body no longer schema-valid |

---

### 2.7 `POST /api/quotes`

| | |
|---|---|
| Roles | CUSTOMER |
| Owner | quote-engine · E3-S2, E3-S3 (AC-01, AC-12, AC-13) |
| Audit | — (the `quotes` row records `actor_id`) |

**Request body** — `{product, inputs}`; fields per `docs/conventions.md` → Quote input fields:

| Product | `inputs` |
|---------|----------|
| all | `sum_insured` money string |
| `TERM_LIFE` | `age` int, `term_years` int 5–30, `smoker` bool |
| `MOTOR` | `owner_age` int, `vehicle_age_years` int ≥ 0, `engine_cc` int > 0, `zone` `A`\|`B`, `ncb_percent` `"0"`\|`"20"`\|`"25"`\|`"35"`\|`"45"`\|`"50"` |
| `HOUSEHOLD` | `proposer_age` int, `construction_type` `CONCRETE`\|`BRICK`\|`TIMBER`\|`THATCH`, `in_flood_zone` bool, `has_security_system` bool |

```json
{ "product": "MOTOR",
  "inputs": { "sum_insured": "500000.00", "owner_age": 30, "vehicle_age_years": 3, "engine_cc": 1200, "zone": "A", "ncb_percent": "20" } }
```

**Success 201**
```json
{ "quote_id": "3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04", "product": "MOTOR", "rule_version": 1,
  "sum_insured": "500000.00", "premium": "14322.00", "currency": "INR", "created_at": "2026-10-01T09:30:00Z" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER or ADMIN |
| `NOT_FOUND` | 404 | unknown product code |
| `NO_PUBLISHED_VERSION` | 409 | product has no PUBLISHED version (nothing persisted) |
| `VALIDATION_ERROR` | 422 | every failing field: `REQUIRED`, `OUT_OF_RANGE`, `UNKNOWN_CODE`, `UNKNOWN_FIELD`, `MONEY_MUST_BE_STRING`, `INVALID_FORMAT` |

---

### 2.8 `GET /api/quotes/{quote_id}`

| | |
|---|---|
| Roles | CUSTOMER (owner), UNDERWRITER, ADMIN |
| Path | `quote_id` — UUID4 |
| Owner | quote-engine · E3-S3 (AC-13) |
| Audit | — |

**Success 200**
```json
{ "quote_id": "3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04", "product": "MOTOR", "rule_version": 1,
  "inputs": { "sum_insured": "500000.00", "owner_age": 30, "vehicle_age_years": 3, "engine_cc": 1200, "zone": "A", "ncb_percent": "20" },
  "sum_insured": "500000.00", "premium": "14322.00", "currency": "INR",
  "actor_id": "cust-001", "created_at": "2026-10-01T09:30:00Z" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `NOT_FOUND` | 404 | unknown/malformed id, or another customer's quote |

---

### 2.9 `GET /api/quotes/{quote_id}/reprice`

| | |
|---|---|
| Roles | CUSTOMER (owner), UNDERWRITER, ADMIN |
| Path | `quote_id` — UUID4 |
| Owner | quote-engine · E3-S2 (AC-13) |
| Audit | — (read-only; never mutates the quote) |

Recomputes the stored inputs on the **recorded** `rule_version` (not the current active version).

**Success 200**
```json
{ "quote_id": "3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04", "rule_version": 1,
  "stored_premium": "14322.00", "recomputed_premium": "14322.00", "matches": true }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `NOT_FOUND` | 404 | unknown id or another customer's quote |

---

### 2.10 `POST /api/applications`

| | |
|---|---|
| Roles | CUSTOMER (must own the quote) |
| Owner | underwriting · E4-S2 (AC-03, AC-04, AC-23) |
| Audit | — (automatic decision row has `decided_by = "SYSTEM"`) |

**Request body**
```json
{ "quote_id": "3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04",
  "kyc": { "full_name": "Test Customer 01", "date_of_birth": "1996-04-01", "aadhaar": "999900000001",
           "pan": "AAAAA0001A", "address": "1 Sample Street, Testville" },
  "health_declaration": { "has_pre_existing_condition": false, "details": "Synthetic condition: none declared" } }
```
- `kyc.aadhaar` 12 digits; `kyc.pan` `^[A-Z]{5}[0-9]{4}[A-Z]$`; all KYC fields required.
- `health_declaration` **required for TERM_LIFE** (`REQUIRED`), rejected for other products (`UNKNOWN_FIELD`).
- Raw Aadhaar/PAN/health details are never logged, stored or returned.

**Success 201** — application after synchronous underwriting:
```json
{ "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21", "quote_id": "3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04",
  "product": "MOTOR", "rule_version": 1, "status": "MANUAL_REVIEW", "decision": "MANUAL_REVIEW",
  "reason_codes": ["MO-UW-002"],
  "reasons": [ { "code": "MO-UW-002", "description": "Vehicle older than 10 years" } ],
  "kyc": { "full_name": "Test Customer 01", "date_of_birth": "1996-04-01", "aadhaar_masked": "XXXX-XXXX-0001",
           "pan_masked": "XXXXX0001X", "address": "1 Sample Street, Testville" },
  "status_history": [ { "status": "SUBMITTED", "at": "2026-10-01T09:31:00Z" },
                      { "status": "UNDERWRITING", "at": "2026-10-01T09:31:00Z" },
                      { "status": "MANUAL_REVIEW", "at": "2026-10-01T09:31:00Z" } ],
  "created_at": "2026-10-01T09:31:00Z" }
```
`AUTO_BIND` carries `reason_codes: []`; `MANUAL_REVIEW`/`DECLINE` carry ≥ 1 code (sorted). Application status
for a `DECLINE` decision is `DECLINED`.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER or ADMIN |
| `NOT_FOUND` | 404 | unknown quote or another customer's quote |
| `QUOTE_STALE` | 409 | quote's `rule_version` ≠ product's active version |
| `VALIDATION_ERROR` | 422 | KYC format (`kyc.pan`/`kyc.aadhaar` `INVALID_FORMAT`), missing fields (`REQUIRED`), eligibility (`owner_age` `OUT_OF_RANGE`), `health_declaration` rules; nothing persisted |

---

### 2.11 `GET /api/applications/{application_id}`

| | |
|---|---|
| Roles | CUSTOMER (owner), UNDERWRITER, ADMIN |
| Path | `application_id` — UUID4 |
| Owner | underwriting · E4-S2 (AC-03) |
| Audit | — |

**Success 200** — the 2.10 object plus `decisions: [Decision]` (oldest first), `overrides: [Override]` and, once
issued, `policy_number` (else `null`).

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `NOT_FOUND` | 404 | unknown id or another customer's application |

---

### 2.12 `GET /api/underwriting/queue`

| | |
|---|---|
| Roles | UNDERWRITER (`MANUAL_REVIEW` only), ADMIN (both) |
| Query | `status` — `MANUAL_REVIEW` \| `DECLINED`, optional. Default: UNDERWRITER → `MANUAL_REVIEW`; ADMIN → both |
| Owner | underwriting · E4-S3, E4-S4 (AC-04, AC-09, AC-14) |
| Audit | — |

**Success 200** — oldest first:
```json
[ { "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21", "product": "MOTOR", "status": "DECLINED",
    "rule_version": 1, "reason_codes": ["MO-UW-001", "MO-UW-002"],
    "sum_insured": "2000000.00", "premium": "99200.00", "submitted_at": "2026-10-01T09:31:00Z",
    "decisions": [ { "decision_id": 41, "decision": "DECLINE", "reason_codes": ["MO-UW-001", "MO-UW-002"],
                     "reasons": [ { "code": "MO-UW-001", "description": "Vehicle older than 15 years" },
                                  { "code": "MO-UW-002", "description": "Vehicle older than 10 years" } ],
                     "rule_version": 1, "decided_by": "SYSTEM", "comment": null, "created_at": "2026-10-01T09:31:00Z" } ] } ]
```
No KYC is included in queue items.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER; UNDERWRITER with `status=DECLINED` |
| `VALIDATION_ERROR` | 422 | `status` not in the allowed values (`UNKNOWN_CODE`) |

---

### 2.13 `POST /api/underwriting/applications/{application_id}/decision`

| | |
|---|---|
| Roles | UNDERWRITER |
| Path | `application_id` — UUID4 |
| Owner | underwriting · E4-S3 (AC-14) |
| Audit | `UW_APPROVE` (APPROVE) / `UW_DECLINE` (DECLINE), entity `APPLICATION` |

**Request body**
```json
{ "decision": "APPROVE", "reason_codes": ["MO-UW-900"], "comment": "Vehicle inspected, condition good" }
```
`decision` ∈ `UnderwriterDecision` (`APPROVE` → application `AUTO_BIND`, stored `Decision.AUTO_BIND`; `DECLINE`
→ `DECLINED`, stored `Decision.DECLINE`); `reason_codes` ≥ 1, each a key of the case's rule-version
`underwriting.reason_codes`; `comment` optional string ≤ 500.

**Success 200**
```json
{ "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21", "status": "AUTO_BIND",
  "decision": { "decision_id": 52, "decision": "AUTO_BIND", "reason_codes": ["MO-UW-900"],
                "reasons": [ { "code": "MO-UW-900", "description": "Underwriter approved" } ],
                "rule_version": 1, "decided_by": "uw-001", "comment": "Vehicle inspected, condition good",
                "created_at": "2026-10-02T11:00:00Z" } }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or ADMIN |
| `NOT_FOUND` | 404 | unknown application |
| `INVALID_APPLICATION_STATE` | 409 | application ≠ `MANUAL_REVIEW` |
| `VALIDATION_ERROR` | 422 | `reason_codes` empty (`REQUIRED`), unknown code (`UNKNOWN_REASON_CODE`), bad `decision` (`UNKNOWN_CODE`), comment too long (`OUT_OF_RANGE`) |

---

### 2.14 `POST /api/underwriting/applications/{application_id}/override`

| | |
|---|---|
| Roles | ADMIN |
| Path | `application_id` — UUID4 |
| Owner | underwriting · E4-S4 (AC-09) |
| Audit | `UW_OVERRIDE_DECLINE`, entity `APPLICATION`, comment in `detail` (same transaction as the override row) |

**Request body**
```json
{ "reason_code": "MO-UW-901", "comment": "Vehicle restored; valid fitness certificate seen" }
```
Exactly one `reason_code` (key of the case's rule-version `reason_codes`); `comment` 10–500 characters.

**Success 200**
```json
{ "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21", "status": "AUTO_BIND",
  "override": { "override_id": 7, "overridden_decision_id": 41, "from_status": "DECLINED", "to_status": "AUTO_BIND",
                "reason_code": "MO-UW-901", "comment": "Vehicle restored; valid fitness certificate seen",
                "actor_id": "admin-001", "created_at": "2026-10-02T12:00:00Z" } }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER |
| `NOT_FOUND` | 404 | unknown application |
| `INVALID_APPLICATION_STATE` | 409 | application ≠ `DECLINED` |
| `VALIDATION_ERROR` | 422 | `comment` length (`OUT_OF_RANGE`), missing fields (`REQUIRED`), `reason_code` not in version (`UNKNOWN_REASON_CODE`) |

---

### 2.15 `GET /api/underwriting/applications/{application_id}/audit`

| | |
|---|---|
| Roles | UNDERWRITER, ADMIN |
| Path | `application_id` — UUID4 |
| Owner | underwriting · E4-S3, E4-S5 |
| Audit | — |

**Success 200** — all lists oldest first:
```json
{ "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21",
  "decisions": [ { "decision_id": 41, "decision": "DECLINE", "reason_codes": ["MO-UW-001"], "reasons": [], "rule_version": 1, "decided_by": "SYSTEM", "comment": null, "created_at": "2026-10-01T09:31:00Z" } ],
  "overrides": [ { "override_id": 7, "overridden_decision_id": 41, "from_status": "DECLINED", "to_status": "AUTO_BIND", "reason_code": "MO-UW-901", "comment": "Vehicle restored; valid fitness certificate seen", "actor_id": "admin-001", "created_at": "2026-10-02T12:00:00Z" } ],
  "audit_records": [ { "action": "UW_OVERRIDE_DECLINE", "actor_id": "admin-001", "actor_role": "ADMIN",
                       "entity_type": "APPLICATION", "entity_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21",
                       "detail": { "reason_code": "MO-UW-901", "comment": "Vehicle restored; valid fitness certificate seen" },
                       "correlation_id": "corr-7f3a-0003", "created_at": "2026-10-02T12:00:00Z" } ] }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER |
| `NOT_FOUND` | 404 | unknown application |

---

### 2.16 `POST /api/applications/{application_id}/issue`

| | |
|---|---|
| Roles | CUSTOMER (owner), ADMIN |
| Path | `application_id` — UUID4 |
| Body | none |
| Owner | policy-issuance · E5-S2, E5-S3 (AC-05) |
| Audit | `POLICY_ISSUED`, entity `POLICY` — only when the actor is ADMIN |

One transaction: policy number allocation, `policies` row `ACTIVE`, transition `null → ACTIVE` (reason `ISSUED`),
first-term `premium_payments` row (`due_date = effective_date`), application → `ISSUED`.

**Success 201** — `PolicySummary` (business date 2026-10-01):
```json
{ "policy_number": "MO-2026-000123", "product": "MOTOR", "status": "ACTIVE", "rule_version": 1,
  "sum_insured": "400000.00", "premium": "12400.00", "currency": "INR",
  "effective_date": "2026-10-01", "expiry_date": "2027-09-30",
  "premium_due_date": "2026-10-01", "next_premium_due_date": "2027-10-01", "previous_policy_number": null }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER |
| `NOT_FOUND` | 404 | unknown application or another customer's |
| `INVALID_APPLICATION_STATE` | 409 | application ≠ `AUTO_BIND` (incl. already `ISSUED`); no number consumed |

---

### 2.17 `GET /api/policies`

| | |
|---|---|
| Roles | CUSTOMER (own only), UNDERWRITER, ADMIN (all) |
| Query | `product` — `ProductCode`, optional; `status` — `PolicyStatus`, optional |
| Owner | policy-issuance · E5-S3 (AC-15) |
| Audit | — |

**Success 200** — array of `PolicySummary`, ordered by `effective_date` then `policy_number`.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `VALIDATION_ERROR` | 422 | unknown `product`/`status` filter (`UNKNOWN_CODE`) |

---

### 2.18 `GET /api/policies/{policy_number}`

| | |
|---|---|
| Roles | CUSTOMER (owner), UNDERWRITER, ADMIN |
| Path | `policy_number` |
| Owner | policy-issuance · E5-S3 (AC-15) |
| Audit | — |

**Success 200** — `PolicySummary` plus:
```json
{ "policy_number": "MO-2026-000123", "product": "MOTOR", "status": "ENDORSED", "rule_version": 1,
  "sum_insured": "400000.00", "premium": "12400.00", "currency": "INR",
  "effective_date": "2026-10-01", "expiry_date": "2027-09-30",
  "premium_due_date": "2026-10-01", "next_premium_due_date": "2027-10-01", "previous_policy_number": null,
  "successor_policy_number": null, "application_id": "7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21",
  "insured": { "full_name": "Test Customer 01", "address": "7 Example Road, Demotown",
               "aadhaar_masked": "XXXX-XXXX-0001", "pan_masked": "XXXXX0001X", "nominees": [] },
  "transitions": [ { "from_status": null, "to_status": "ACTIVE", "reason": "ISSUED", "actor_id": "cust-001", "occurred_at": "2026-10-01T09:40:00Z" },
                   { "from_status": "ACTIVE", "to_status": "ENDORSED", "reason": "ENDORSEMENT:CHANGE_ADDRESS", "actor_id": "cust-001", "occurred_at": "2026-11-15T10:00:00Z" } ],
  "endorsements": [ { "endorsement_id": 17, "type": "CHANGE_ADDRESS",
                      "before": { "address": "1 Sample Street, Testville" }, "after": { "address": "7 Example Road, Demotown" },
                      "premium_delta": "0.00", "rule_version": 1, "endorsement_date": "2026-11-15",
                      "actor_id": "cust-001", "created_at": "2026-11-15T10:00:00Z" } ],
  "payments": [ { "payment_id": 1, "due_date": "2026-10-01", "amount": "12400.00", "rule_version": 1, "actor_id": "cust-001", "paid_at": "2026-10-01T09:40:00Z" } ],
  "refunds": [] }
```
`nominees[]` items: `{nominee_name, relationship, share_percent}` (share as decimal string). `successor_policy_number`
is set once the policy is `RENEWED` (link to the new term).

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `NOT_FOUND` | 404 | unknown number or another customer's policy |

---

### 2.19 `POST /api/policies/{policy_number}/endorsements`

| | |
|---|---|
| Roles | CUSTOMER (owner), ADMIN |
| Path / query | `policy_number`; `preview` — bool, default `false` |
| Owner | endorsement · E6-S3 (AC-06, AC-16, AC-10) |
| Audit | `ENDORSEMENT_CREATED`, entity `POLICY` — ADMIN actor, non-preview only |

**Request body** — discriminated by `type` (`EndorsementType`), validated on the policy's own `rule_version`:

| `type` | Fields |
|--------|--------|
| `CHANGE_ADDRESS` | `address` — non-blank, ≤ 300 chars, ≠ current |
| `ADD_NOMINEE` | `nominee_name` non-blank; `relationship` `SPOUSE`\|`CHILD`\|`PARENT`\|`SIBLING`\|`OTHER`; `share_percent` decimal string 1–100; total ≤ 100 |
| `CHANGE_SUM_INSURED` | `new_sum_insured` money string within eligibility, ≠ current |

```json
{ "type": "CHANGE_SUM_INSURED", "new_sum_insured": "500000.00" }
```

**Success 201** (business date 2027-04-01):
```json
{ "endorsement_id": 18, "policy_number": "MO-2026-000123", "type": "CHANGE_SUM_INSURED",
  "before": { "sum_insured": "400000.00", "premium": "12400.00" },
  "after": { "sum_insured": "500000.00", "premium": "15500.00" },
  "new_premium": "15500.00", "premium_delta": "1554.25", "rule_version": 1,
  "endorsement_date": "2027-04-01", "created_at": "2027-04-01T10:00:00Z",
  "policy": { "policy_number": "MO-2026-000123", "product": "MOTOR", "status": "ENDORSED", "rule_version": 1,
              "sum_insured": "500000.00", "premium": "15500.00", "currency": "INR",
              "effective_date": "2026-10-01", "expiry_date": "2027-09-30",
              "premium_due_date": "2026-10-01", "next_premium_due_date": "2027-10-01", "previous_policy_number": null } }
```

**Success 200 (`?preview=true`)** — nothing persisted:
```json
{ "policy_number": "MO-2026-000123", "type": "CHANGE_SUM_INSURED", "preview": true,
  "before": { "sum_insured": "400000.00", "premium": "12400.00" },
  "after": { "sum_insured": "300000.00", "premium": "9300.00" },
  "new_premium": "9300.00", "premium_delta": "-1554.25", "rule_version": 1, "endorsement_date": "2027-04-01" }
```
For `CHANGE_ADDRESS` / `ADD_NOMINEE`, `new_premium` = current premium and `premium_delta` = `"0.00"`.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | policy `LAPSED`/`CANCELLED`/`RENEWED`; `details {current, target: "ENDORSED"}` |
| `VALIDATION_ERROR` | 422 | `type` `NOT_ALLOWED`/`UNKNOWN_CODE`; `UNCHANGED`; `OUT_OF_RANGE`; `SHARE_EXCEEDS_100`; `REQUIRED`; `INVALID_FORMAT`; `MONEY_MUST_BE_STRING`; business date outside term (`endorsement_date` `OUTSIDE_TERM`) |

---

### 2.20 `GET /api/policies/{policy_number}/renewal`

| | |
|---|---|
| Roles | CUSTOMER (owner), ADMIN |
| Path | `policy_number` |
| Owner | renewal-cancellation · E7-S4 (AC-07, AC-17) |
| Audit | — |

Renewal quote on the product's **active** version with ages / `vehicle_age_years` advanced by 1 per completed
12-month term.

**Success 200**
```json
{ "policy_number": "MO-2025-000210", "renewable": true, "renewal_premium": "14720.00", "rule_version": 2,
  "currency": "INR", "due_date": "2026-10-01", "grace_end_date": "2026-10-31",
  "renewal_window_opens": "2026-08-31", "paid": false }
```
When not renewable: `renewable: false`, `renewal_premium: null`, `rule_version` = active version.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | policy `LAPSED`/`CANCELLED`/`RENEWED` |
| `NO_PUBLISHED_VERSION` | 409 | product has no PUBLISHED version |

---

### 2.21 `POST /api/policies/{policy_number}/renew`

| | |
|---|---|
| Roles | CUSTOMER (owner) |
| Path | `policy_number` |
| Body | none |
| Owner | renewal-cancellation · E7-S4 (AC-07) |
| Audit | — (transition rows record the actor) |

Early renewal on the business date inside the window: old policy → `RENEWED`, successor `ACTIVE` with the paid
renewal premium and its `rule_version`, `effective_date = old expiry + 1 day`.

**Success 201** — successor `PolicySummary`:
```json
{ "policy_number": "TL-2026-000011", "product": "TERM_LIFE", "status": "ACTIVE", "rule_version": 1,
  "sum_insured": "5000000.00", "premium": "9900.00", "currency": "INR",
  "effective_date": "2026-10-21", "expiry_date": "2027-10-20",
  "premium_due_date": "2026-10-21", "next_premium_due_date": "2027-10-21",
  "previous_policy_number": "TL-2025-000004" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER or ADMIN |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | policy already `RENEWED` / `LAPSED` / `CANCELLED` |
| `OUTSIDE_RENEWAL_WINDOW` | 409 | business date before `expiry − renewal_window_days` or after grace end |
| `VALIDATION_ERROR` | 422 | `{"field": "payment", "code": "RENEWAL_PREMIUM_UNPAID"}`; `{"field": "policy_number", "code": "NOT_RENEWABLE"}` |

---

### 2.22 `POST /api/policies/{policy_number}/payments`

| | |
|---|---|
| Roles | CUSTOMER (owner) |
| Path | `policy_number` |
| Owner | renewal-cancellation · E7-S2, E7-S4 (AC-17) |
| Audit | — (append-only `premium_payments` row records `actor_id`) |

Pays the renewal premium due on `expiry_date + 1 day`; amount must equal the current renewal quote.

**Request body**
```json
{ "amount": "12400.00" }
```

**Success 201**
```json
{ "payment_id": 311, "policy_number": "MO-2025-000301", "amount": "12400.00", "due_date": "2026-10-01",
  "rule_version": 1, "actor_id": "cust-001", "paid_at": "2026-10-20T08:15:00Z" }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER or ADMIN |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | policy `LAPSED`/`CANCELLED`/`RENEWED` |
| `OUTSIDE_RENEWAL_WINDOW` | 409 | business date outside window |
| `PREMIUM_ALREADY_PAID` | 409 | payment exists for that due date |
| `NO_PUBLISHED_VERSION` | 409 | renewal cannot be quoted |
| `VALIDATION_ERROR` | 422 | `amount` `AMOUNT_MISMATCH` / `REQUIRED` / `INVALID_FORMAT` / `MONEY_MUST_BE_STRING`; `{"field": "policy_number", "code": "NOT_RENEWABLE"}` |

---

### 2.23 `GET /api/policies/{policy_number}/cancellation-preview`

| | |
|---|---|
| Roles | CUSTOMER (owner), ADMIN |
| Path / query | `policy_number`; `date` — `YYYY-MM-DD`, required |
| Owner | renewal-cancellation · E8-S3 (AC-08, AC-19) |
| Audit | — (nothing persisted) |

**Success 200** — `RefundBreakdown`:
```json
{ "policy_number": "MO-2026-000123", "cancellation_date": "2027-04-01", "refund_type": "PRO_RATA",
  "premium_paid": "12400.00", "term_days": 365, "days_elapsed": 182, "unused_days": 183,
  "admin_fee": "250.00", "amount": "5966.99", "rule_version": 1 }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | policy terminal; `details {current, target: "CANCELLED"}` |
| `VALIDATION_ERROR` | 422 | `date` `REQUIRED` / `INVALID_FORMAT` / `OUTSIDE_TERM` |

---

### 2.24 `POST /api/policies/{policy_number}/cancel`

| | |
|---|---|
| Roles | CUSTOMER (owner), ADMIN |
| Path | `policy_number` |
| Owner | renewal-cancellation · E8-S2, E8-S3 (AC-08, AC-19, AC-10) |
| Audit | `POLICY_CANCELLED`, entity `POLICY` — only when the actor is ADMIN |

**Request body**
```json
{ "cancellation_date": "2027-04-01", "reason": "Vehicle sold" }
```
`reason` — non-blank free text ≤ 200 chars (OI-5 RESOLVED; no enum).

**Success 200**
```json
{ "policy_number": "MO-2026-000123", "status": "CANCELLED",
  "refund": { "refund_id": 9, "policy_number": "MO-2026-000123", "cancellation_date": "2027-04-01",
              "refund_type": "PRO_RATA", "premium_paid": "12400.00", "term_days": 365, "days_elapsed": 182,
              "unused_days": 183, "admin_fee": "250.00", "amount": "5966.99", "rule_version": 1,
              "reason": "Vehicle sold", "actor_id": "cust-001", "created_at": "2027-04-01T10:00:00Z" } }
```

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | UNDERWRITER |
| `NOT_FOUND` | 404 | unknown policy or another customer's |
| `INVALID_POLICY_STATE` | 409 | already `CANCELLED` / `LAPSED` / `RENEWED`; `details {current, target: "CANCELLED"}` |
| `VALIDATION_ERROR` | 422 | `cancellation_date` `REQUIRED` / `INVALID_FORMAT` / `OUTSIDE_TERM`; `reason` `REQUIRED` / `OUT_OF_RANGE` |

---

### 2.25 `POST /api/admin/end-of-day`

| | |
|---|---|
| Roles | ADMIN |
| Owner | renewal-cancellation · E7-S4 (AC-07, AC-18) |
| Audit | `RUN_END_OF_DAY`, entity `END_OF_DAY`, `entity_id` = `as_of`, `detail` = `as_of` + counts (one row per run, actor = admin) |

**Request body**
```json
{ "as_of": "2026-10-01" }
```

**Success 200**
```json
{ "as_of": "2026-10-01", "renewed": 1, "lapsed": 0, "in_grace": 0, "not_renewable": 0, "failed": 0,
  "renewed_policies": [ { "from": "MO-2025-000210", "to": "MO-2026-000125" } ],
  "lapsed_policies": [], "failed_policies": [] }
```
Re-running the same `as_of` returns zero `renewed`/`lapsed` (AC-18).

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER |
| `VALIDATION_ERROR` | 422 | `as_of` `REQUIRED` / `INVALID_FORMAT` |

---

### 2.26 `GET /api/admin/portfolio`

| | |
|---|---|
| Roles | ADMIN |
| Query | `as_of` — `YYYY-MM-DD`, optional (default business date) |
| Owner | app_spec · E9-S1 (AC-20) |
| Audit | — |

**Success 200**
```json
{ "as_of": "2026-10-15",
  "active_by_product": { "TERM_LIFE": 1, "MOTOR": 2, "HOUSEHOLD": 0 },
  "premium_collected": "29422.00", "refunds_paid": "0.00",
  "renewal_pipeline": [ { "policy_number": "MO-2026-000001", "product": "MOTOR", "due_date": "2026-11-02",
                          "renewal_premium": "14322.00", "paid": false } ],
  "lapse_forecast": { "count": 1, "premium_at_risk": "3100.00",
                      "policies": [ { "policy_number": "MO-2025-000003", "product": "MOTOR", "due_date": "2026-10-01",
                                      "grace_end_date": "2026-10-31", "premium": "3100.00" } ] } }
```
Definitions in `specs/app_spec.md` §9 (window `renewal_window_days` = 30). `renewal_premium` is `null` for a
non-renewable policy.

| Error | HTTP | When |
|-------|------|------|
| `UNAUTHENTICATED` | 401 | missing/invalid actor headers |
| `FORBIDDEN` | 403 | CUSTOMER or UNDERWRITER |
| `VALIDATION_ERROR` | 422 | malformed `as_of` (`INVALID_FORMAT`) |

---

## 3. Open issues (spec ↔ conventions conflicts found by `/design`) — all RESOLVED

Decided by the lead; `docs/conventions.md` carries the canonical error code, audit action and DEC-011 trigger.

| ID | Conflict | Status — resolution applied |
|----|----------|------------------------------|
| OI-1 | `PUT …/versions/{version}` (DEC-009) had no audit action and was missing from the catalog spec/stories. | **RESOLVED** — `RULE_VERSION_DRAFT_REPLACED` added to conventions; PUT added to `product-catalog_spec.md` (endpoints table + two AC-11 scenarios) and to E2-S3 criterion 6. |
| OI-2 | `renewal-cancellation_spec.md` listed "422 `OUTSIDE_TERM`" as an error code. | **RESOLVED** — spec now says 422 `VALIDATION_ERROR` with `details[].code = OUTSIDE_TERM` (A-RC-9 and the cancellation-preview row); E8-S3 AC-3 already matched. |
| OI-3 | AC-06 expected HTTP 500 with no code defined. | **RESOLVED** — `INTERNAL_ERROR` (500) in conventions; named in `endorsement_spec.md` AC-06 rollback scenario and E6-S2 criterion 3. |
| OI-4 | `app_spec.md` NFR-05 named `backend/alembic/versions/`. | **RESOLVED** — `backend/migrations/versions/` is canonical; app_spec NFR-05 fixed. |
| OI-5 | Cancel `reason`: free text vs code `NO_LONGER_NEEDED`. | **RESOLVED** — free text ≤ 200 chars everywhere; E8-S3 AC-1 now uses "Vehicle sold" and the renewal-cancellation API table states the constraint. |
| OI-6 | Scheduler actor `system-eod` had no invocation path. | **RESOLVED** — DEC-011: `POST /api/admin/end-of-day` and `python -m src.jobs.end_of_day --as-of`, both idempotent, documented in `renewal-cancellation_spec.md` and E7-S3 criterion 3. |
| OI-7 | `GET /api/products` item shape and portfolio pipeline "totals" disagreed. | **RESOLVED** — contract is authoritative: E2-S4 AC-1 now uses `{product, name, active_version, currency}`; E9-S1 AC-3 drops "totals" (app_spec §9 shape unchanged, UI sums client-side). |
