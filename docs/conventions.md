# PolicyForge Canonical Conventions

Single source of truth for names, paths and formats. Agents, skills, commands, hooks, specs and code
**must** use exactly these. If a spec needs something new, add it here first (spec-is-truth applies).

## Products and rule files

| Product | Code (`product` field, enums) | Folder | Reason-code prefix |
|---------|-------------------------------|--------|--------------------|
| Term Life | `TERM_LIFE` | `backend/policy_rules/term_life/` | `TL-UW-###` |
| Motor | `MOTOR` | `backend/policy_rules/motor/` | `MO-UW-###` |
| Household | `HOUSEHOLD` | `backend/policy_rules/household/` | `HH-UW-###` |

- Folders are **lower snake_case**; files are `v<N>.json` (`v1.json`, `v2.json`, …).
- Schema: `backend/policy_rules/schema/rule-file.schema.json`.
- Published-version ledger: `backend/policy_rules/PUBLISHED.lock` — one line per published file,
  `<sha256>  <path relative to backend/policy_rules/>` (e.g. `…  motor/v1.json`), exactly the output of
  `cd backend/policy_rules && sha256sum motor/v1.json`; verify with `sha256sum -c PUBLISHED.lock` from that
  folder. Append-only (hooks `policy-immutability-check`, `shell-immutability-check`). The architecture test
  recomputes hashes and fails if a PUBLISHED file changed.
- No publish timestamp inside rule files — the publish time is the commit that flips `status` and the
  `rule_set_versions.created_at` of the imported row. Publishing changes `status` only.
- `cancellation.method` values: `PRO_RATA` (only method in v1; add others here before using them).

### Rule-file shape (all money/rates are JSON strings → `Decimal`)

```json
{
  "product": "MOTOR",
  "version": 1,
  "status": "PUBLISHED",
  "effective_from": "2026-01-01",
  "currency": "INR",
  "premium": { "base_rate": "0.0310", "minimum_premium": "2500.00", "factors": { "...": "..." } },
  "eligibility": { "min_age": 18, "max_age": 75, "min_sum_insured": "100000.00", "max_sum_insured": "5000000.00" },
  "underwriting": {
    "rules": [ { "when": "...", "decision": "MANUAL_REVIEW", "reason_code": "MO-UW-002" } ],
    "reason_codes": { "MO-UW-001": "Vehicle older than 15 years", "MO-UW-002": "..." }
  },
  "endorsement": { "allowed_types": ["CHANGE_ADDRESS", "ADD_NOMINEE", "CHANGE_SUM_INSURED"] },
  "renewal": { "term_months": 12, "grace_period_days": 30 },
  "cancellation": { "method": "PRO_RATA", "free_look_days": 15, "admin_fee": "250.00" }
}
```

### Product-specific `premium.factors` keys

| Product | Required factor keys |
|---------|----------------------|
| `TERM_LIFE` | `age_bands`, `smoker_loading`, `term_years_bands` |
| `MOTOR` | `vehicle_age_bands`, `engine_cc_bands`, `ncb_discounts`, `zone_rates` |
| `HOUSEHOLD` | `construction_type_rates`, `flood_zone_loading`, `security_discount` |

Bands are arrays of `{ "min": int, "max": int, "multiplier": "<decimal string>" }`; maps are
`{ "<code>": "<decimal string>" }`.

## Backend modules (`backend/src/`, imported as `src.<layer>`)

| Concept | Location |
|---------|----------|
| Enums (`ProductCode`, `PolicyStatus`, `ApplicationStatus`, `Decision`, `EndorsementType`, `ActorRole`, `RefundType`, `EndOfDayAction`, `UnderwriterDecision`) | `src/types/enums.py` |
| Typed errors incl. `InvalidPolicyStateException` | `src/types/errors.py` |
| Rule-set value objects (`RuleSet`, …) | `src/types/rules.py` |
| Domain rules | `src/domain/premium_calculator.py`, `application_validator.py`, `underwriting_rules.py`, `policy_state_machine.py`, `endorsement_rules.py`, `renewal_rules.py`, `refund_rules.py` |
| Settings | `src/config/settings.py` |
| Rule-file parsing + schema validation (file → `RuleSet`) | `src/config/rule_loader.py` |
| Models / repositories | `src/repository/models.py`, `src/repository/<entity>_repository.py` |
| Services | `src/service/<use_case>_service.py` |
| Routers | `src/api/routers/<resource>.py`; deps `src/api/deps.py`; middleware `src/api/middleware.py` |
| App entry point | `src.main:app` (`backend/src/main.py`) |
| Seed | `python -m src.seed` (`backend/src/seed.py`) |
| Logger / correlation / PII masking | `src/lib/logging.py` (`get_logger`, `mask_pii`), `src/lib/correlation.py` |
| Business date (`today()`, DEC-012) | `src/lib/clock.py` |
| Value objects (Money helpers) | `src/types/values.py` |
| Rule `when` evaluator · term-day maths | `src/domain/condition.py` · `src/domain/term_days.py` |
| Engine/session · append-only repository base | `src/repository/database.py` · `src/repository/append_only.py` |
| Transaction boundary · policy read models | `src/service/unit_of_work.py` · `src/service/policy_query_service.py` |
| API error handlers · request/response DTOs | `src/api/errors.py` · `src/api/schemas/<resource>.py` |
| End-of-day job entry point | `src/jobs/end_of_day.py` |

## Persistence

| Model | Table | Append-only |
|-------|-------|-------------|
| `RuleSetVersion` | `rule_set_versions` | ✅ (DEC-013: PK `id`; columns `product`, `version`, `revision`, `status`; unique `(product, version, revision)` and a partial unique on `(product, version)` where `status = 'PUBLISHED'` — a DRAFT replace appends `revision + 1`, publishing appends the final row) |
| `Quote` | `quotes` | — |
| `Application` | `applications` | — (status projection) |
| `UnderwritingDecision` | `underwriting_decisions` | ✅ |
| `UnderwritingOverride` | `underwriting_overrides` | ✅ |
| `Policy` | `policies` | — (current projection) |
| `PolicyStateTransition` | `policy_state_transitions` | ✅ |
| `Endorsement` | `endorsements` | ✅ |
| `PremiumPayment` | `premium_payments` | ✅ |
| `Refund` | `refunds` | ✅ |
| `AuditRecord` | `audit_records` | ✅ |

- Tables are **plural snake_case**; append-only repositories expose `add(...)` + reads only.
- Money columns `Numeric(12, 2)`; rates `Numeric(9, 6)`.

## Lifecycle

- `PolicyStatus`: `ACTIVE`, `ENDORSED`, `LAPSED`, `CANCELLED`, `RENEWED`.
  Allowed: `ACTIVE → ENDORSED | LAPSED | CANCELLED | RENEWED`; `ENDORSED → ENDORSED | LAPSED | CANCELLED | RENEWED`.
  `LAPSED`, `CANCELLED`, `RENEWED` are terminal (renewal issues a new term policy that starts `ACTIVE`).
- `ApplicationStatus`: `SUBMITTED → UNDERWRITING → AUTO_BIND | MANUAL_REVIEW | DECLINED → ISSUED`
  (`MANUAL_REVIEW → AUTO_BIND | DECLINED`; admin override `DECLINED → AUTO_BIND`).
- `Decision`: `AUTO_BIND`, `MANUAL_REVIEW`, `DECLINE`.

## Tests and traceability

- Python: `test_acNN_<behaviour>` **and** `@pytest.mark.ac("AC-NN")`; the marker is what counts.
- Playwright: `AC-NN` in the `test(...)` title.
- One deterministic report: `uv run scripts/ac_audit_agent.py` → `specs/reviews/ac-audit.md`
  (`/ac-coverage` is the interactive equivalent). The marker counts whether written as a decorator or as a
  module-level `pytestmark`.
  `scripts/ac_audit_agent.py` adds an agent quality review → `specs/reviews/ac-audit.md`.

## Reports (`specs/reviews/`)

`evaluator-report.md` (ends `VERDICT: PASS|FAIL`), `security-review-<scope>.md`,
`clean-code-review-<scope>.md`, `ac-audit.md`, `premium-calc-report.md`,
`policy-version-validation.md`, `endorsement-validation.md`, `migration-coherence-<date>.md`,
`performance-audit-<date>.md`, `doc-sync-<date>.md`, `janitor-<date>.md`.
Every verdict is the report's **last line**, exactly:

| Report | Last line |
|--------|-----------|
| evaluator, AC coverage/audit, validators, quote-check | `VERDICT: PASS` / `VERDICT: FAIL` |
| security-review-* | `VERDICT: CLEAR` / `VERDICT: WARN` / `VERDICT: BLOCK` |
| clean-code-review-* | `VERDICT: APPROVE` / `VERDICT: APPROVE_WITH_NITS` / `VERDICT: CHANGES_REQUIRED` |

## API / auth stub

- All routes are under the `/api` prefix (e.g. `POST /api/quotes`, `POST /api/policies/{policy_number}/cancel`);
  `GET /health` is the only un-prefixed route. The **API endpoints** table below is authoritative for paths
  until `specs/design/api-contracts.md` (from `/design`) supersedes it.
- Headers `X-Actor-Id`, `X-Actor-Role` (`CUSTOMER` | `UNDERWRITER` | `ADMIN`), `X-Correlation-ID`.
- Demo users: `cust-001` (CUSTOMER), `uw-001` (UNDERWRITER), `admin-001` (ADMIN); extra test actors follow the
  same pattern (`cust-002`, `uw-002`). The end-of-day scheduler acts as `system-eod` with
  `ActorRole.SYSTEM` (DEC-010) — an internal role that is **never accepted from the `X-Actor-Role` header**
  (401 `UNAUTHENTICATED`); it exists only so scheduler audit rows carry a valid actor.
- **How end-of-day is triggered** (DEC-011): there is no OS cron (out of scope, brief §6.3). The cycle runs
  either from `POST /api/admin/end-of-day` (ADMIN, actor = the admin) or from
  `uv run python -m src.jobs.end_of_day --as-of YYYY-MM-DD` (actor = `system-eod` / `ActorRole.SYSTEM`).
  Both call the same idempotent service (AC-18).
- `quote_id` and `application_id` are UUID4 strings; policy numbers are `<TL|MO|HH>-<YYYY>-<6-digit seq>`
  (e.g. `MO-2026-000123`). Short labels such as "application 45" in Gherkin are illustrative aliases.
- Money is a JSON **string** with two decimals (`"14322.00"`), never a JSON number.
- A CUSTOMER addressing another customer's quote, application or policy gets **404 `NOT_FOUND`** (no existence leak).

## API endpoints

_Authoritative until `specs/design/api-contracts.md` supersedes it._ Roles are checked in `src/api/deps.py`.
"owner" = the CUSTOMER whose `X-Actor-Id` owns the resource.

| Method | Path | Roles | Owner spec / stories |
|--------|------|-------|----------------------|
| GET | `/health` (no prefix, no auth) | public | app_spec · E1-S1 |
| GET | `/api/products` | CUSTOMER, UNDERWRITER, ADMIN | product-catalog · E2-S4 |
| GET | `/api/products/{product}/versions` | CUSTOMER, UNDERWRITER, ADMIN | product-catalog · E2-S4 |
| POST | `/api/products/{product}/versions` (create DRAFT, body = rule-file JSON) | ADMIN | product-catalog · E2-S3, E2-S4 |
| PUT | `/api/products/{product}/versions/{version}` (replace an open **DRAFT** only; appends a new `rule_set_versions` row; PUBLISHED → 409 `VERSION_IMMUTABLE`) | ADMIN | product-catalog · E2-S3, E2-S4 (DEC-009) |
| POST | `/api/products/{product}/versions/{version}/publish` | ADMIN | product-catalog · E2-S3, E2-S4 |
| POST | `/api/quotes` (body `{product, inputs}`) | CUSTOMER | quote-engine · E3-S2, E3-S3 |
| GET | `/api/quotes/{quote_id}` | CUSTOMER (owner), UNDERWRITER, ADMIN | quote-engine · E3-S3 |
| GET | `/api/quotes/{quote_id}/reprice` | CUSTOMER (owner), UNDERWRITER, ADMIN | quote-engine · E3-S2 |
| POST | `/api/applications` (body `{quote_id, kyc, health_declaration?}`) | CUSTOMER | underwriting · E4-S2 |
| GET | `/api/applications/{application_id}` | CUSTOMER (owner), UNDERWRITER, ADMIN | underwriting · E4-S2 |
| GET | `/api/underwriting/queue` (`?status=MANUAL_REVIEW\|DECLINED`) | UNDERWRITER (MANUAL_REVIEW only), ADMIN (both) | underwriting · E4-S3, E4-S4 |
| POST | `/api/underwriting/applications/{application_id}/decision` (body `{decision: APPROVE\|DECLINE, reason_codes, comment}`) | UNDERWRITER | underwriting · E4-S3 |
| POST | `/api/underwriting/applications/{application_id}/override` (body `{reason_code, comment}`) | ADMIN | underwriting · E4-S4 |
| GET | `/api/underwriting/applications/{application_id}/audit` | UNDERWRITER, ADMIN | underwriting · E4-S3, E4-S5 |
| POST | `/api/applications/{application_id}/issue` | CUSTOMER (owner), ADMIN | policy-issuance · E5-S3 |
| GET | `/api/policies` | CUSTOMER (own), UNDERWRITER, ADMIN (all) | policy-issuance · E5-S3 |
| GET | `/api/policies/{policy_number}` | CUSTOMER (owner), UNDERWRITER, ADMIN | policy-issuance · E5-S3 |
| POST | `/api/policies/{policy_number}/endorsements` (`?preview=true` → 200, nothing persisted) | CUSTOMER (owner), ADMIN | endorsement · E6-S3 |
| GET | `/api/policies/{policy_number}/renewal` (renewal quote) | CUSTOMER (owner), ADMIN | renewal-cancellation · E7-S4 |
| POST | `/api/policies/{policy_number}/renew` | CUSTOMER (owner) | renewal-cancellation · E7-S4 |
| POST | `/api/policies/{policy_number}/payments` (body `{amount}`) | CUSTOMER (owner) | renewal-cancellation · E7-S2, E7-S4 |
| GET | `/api/policies/{policy_number}/cancellation-preview?date=YYYY-MM-DD` | CUSTOMER (owner), ADMIN | renewal-cancellation · E8-S3 |
| POST | `/api/policies/{policy_number}/cancel` (body `{cancellation_date, reason}`) | CUSTOMER (owner), ADMIN | renewal-cancellation · E8-S3 |
| GET | `/api/admin/ping` (internal auth probe — returns the resolved actor, no data) | ADMIN | app_spec · AC-22 |
| POST | `/api/admin/end-of-day` (body `{as_of}`) | ADMIN | renewal-cancellation · E7-S4 |
| GET | `/api/admin/portfolio?as_of=YYYY-MM-DD` | ADMIN | app_spec · E9-S1 |

No other paths exist (no `/approve`, `/decline`, `/api/admin/underwriting/...`, `POST /api/policies`,
`PUT` on a PUBLISHED version, or `.../refund-preview`). A new endpoint is added here first.

## Error codes

Every non-2xx response uses one envelope: `{"error": {"code": "<SCREAMING_SNAKE>", "message": "<text>", "details": …}}`.
`details` is a list `[{"field": "<name>", "code": "<DETAIL_CODE>"}]` for 422 (all failing fields at once;
`field` is the input name or a dotted path such as `kyc.pan`, `premium.base_rate`), otherwise an object
(e.g. `{"current": "CANCELLED", "target": "CANCELLED"}`) or `null`. The correlation id travels in the
`X-Correlation-ID` response header.

| Code | HTTP | Raised when |
|------|------|-------------|
| `VALIDATION_ERROR` | 422 | Body/query/rule-file validation fails (field errors in `details`) |
| `UNAUTHENTICATED` | 401 | `X-Actor-Id` or `X-Actor-Role` missing, or role not in `ActorRole` |
| `FORBIDDEN` | 403 | Role not allowed on the route |
| `NOT_FOUND` | 404 | Unknown product, version, quote, application or policy — or another customer's |
| `NO_PUBLISHED_VERSION` | 409 | Product has no PUBLISHED rule version (quote/renewal refused, no fallback) |
| `VERSION_IMMUTABLE` | 409 | Publishing or changing an already PUBLISHED version |
| `DRAFT_ALREADY_OPEN` | 409 | Creating a DRAFT while the product already has an open DRAFT |
| `INVALID_POLICY_STATE` | 409 | `InvalidPolicyStateException` — disallowed policy transition or action on a terminal policy |
| `INVALID_APPLICATION_STATE` | 409 | Application not in the status the action needs (decide ≠ MANUAL_REVIEW, override ≠ DECLINED, issue ≠ AUTO_BIND) |
| `QUOTE_STALE` | 409 | Quote's rule version is no longer the product's active version |
| `PREMIUM_ALREADY_PAID` | 409 | A payment already exists for that due date |
| `OUTSIDE_RENEWAL_WINDOW` | 409 | Renewal payment/renew requested before `expiry_date − renewal_window_days` or after grace end |
| `INTERNAL_ERROR` | 500 | Unhandled server error; the transaction rolled back and nothing was persisted (AC-06 rollback path) |

Detail codes (`details[].code`): `REQUIRED`, `OUT_OF_RANGE`, `INVALID_FORMAT`, `UNKNOWN_CODE`, `UNKNOWN_FIELD`,
`MONEY_MUST_BE_STRING`, `NOT_ALLOWED` (e.g. endorsement type not in `endorsement.allowed_types`), `UNCHANGED`,
`SHARE_EXCEEDS_100`, `AMOUNT_MISMATCH`, `OUTSIDE_TERM`, `NOT_RENEWABLE`, `RENEWAL_PREMIUM_UNPAID`,
`UNKNOWN_REASON_CODE`, `SCHEMA_VIOLATION`.

## Audit actions

`audit_records.action` values (one row per action, `actor_id`, `actor_role`, `entity_type`, `entity_id`,
`detail` JSON without PII, `correlation_id`). Written for every UNDERWRITER/ADMIN actor and the scheduler
(`system-eod`); customer actions are traced by the append-only domain rows instead.

| Action | Written by | Entity |
|--------|------------|--------|
| `RULE_VERSION_DRAFT_CREATED` | catalog create draft (ADMIN) | `RULE_SET_VERSION` |
| `RULE_VERSION_DRAFT_REPLACED` | catalog replace open DRAFT (ADMIN, DEC-009) | `RULE_SET_VERSION` |
| `RULE_VERSION_PUBLISHED` | catalog publish (ADMIN) | `RULE_SET_VERSION` |
| `UW_APPROVE` | underwriter decision `APPROVE` | `APPLICATION` |
| `UW_DECLINE` | underwriter decision `DECLINE` | `APPLICATION` |
| `UW_OVERRIDE_DECLINE` | admin override of a DECLINED application | `APPLICATION` |
| `POLICY_ISSUED` | issuance by ADMIN | `POLICY` |
| `ENDORSEMENT_CREATED` | endorsement by ADMIN | `POLICY` |
| `POLICY_CANCELLED` | cancellation by ADMIN | `POLICY` |
| `RUN_END_OF_DAY` | end-of-day run (ADMIN or `system-eod`), `detail` = `as_of` + counts | `END_OF_DAY` |

## Additional enums (`src/types/enums.py`)

- `RefundType`: `FREE_LOOK`, `PRO_RATA`.
- `EndOfDayAction`: `NONE`, `RENEW`, `IN_GRACE`, `LAPSE` (result of `renewal_rules.renewal_action`).
- `UnderwriterDecision` (request value): `APPROVE` → application `AUTO_BIND`, `DECLINE` → `DECLINED`
  (stored in `underwriting_decisions` as `Decision.AUTO_BIND` / `Decision.DECLINE`, `decided_by` = actor id;
  automatic decisions use `decided_by = "SYSTEM"`).

## Settings (`src/config/settings.py`)

| Setting | Default | Meaning |
|---------|---------|---------|
| `renewal_window_days` | `30` | Renewal opens `expiry_date − 30 days`; also the look-ahead of the dashboard renewal pipeline and lapse forecast |
| `database_url` | `sqlite:///./policyforge.db` | SQLAlchemy URL |
| `api_port` / `ui_port` | `8000` / `3000` | Ports for `npm start` |
| `business_date` | unset (= real today) | DEC-012: overrides "today" for the whole app so demos/tests can sit on a renewal or lapse date. Set via env `POLICYFORGE_BUSINESS_DATE=YYYY-MM-DD`; every layer reads the date through `src/lib/clock.py::today()` — never `date.today()` directly (architecture test) |

Pricing and lifecycle numbers (grace, free look, admin fee, term) live in rule files, never in settings.

## Rule `when` format

`underwriting.rules[].when` is `<field> <op> <value>` clauses joined by ` and ` — no `or`, parentheses or
arithmetic. Ops: `<`, `<=`, `>`, `>=`, `==`, `!=`, `in`. Values: integers, decimal strings compared as `Decimal`,
`true`/`false`, bare enum codes (`THATCH`), and for `in` a bracketed list (`construction_type in [TIMBER, THATCH]`).
Fields are quote input fields (below) plus derived fields: `age_at_term_end` (TERM_LIFE: `age + term_years`) and
`has_pre_existing_condition` (TERM_LIFE: from the application `health_declaration`).
Example: `in_flood_zone == true and sum_insured > 5000000`.

## Quote input fields (canonical, per product)

Body `{"product": "<CODE>", "inputs": {…}}`; unknown fields → 422 `UNKNOWN_FIELD`; money as strings.

| Product | Fields |
|---------|--------|
| all | `sum_insured` (money string) |
| `TERM_LIFE` | `age` (int), `term_years` (int 5–30), `smoker` (bool) |
| `MOTOR` | `owner_age` (int), `vehicle_age_years` (int ≥ 0), `engine_cc` (int > 0), `zone` (`A`\|`B`), `ncb_percent` (string key of `ncb_discounts`: `"0"`, `"20"`, `"25"`, `"35"`, `"45"`, `"50"`) |
| `HOUSEHOLD` | `proposer_age` (int), `construction_type` (`CONCRETE`\|`BRICK`\|`TIMBER`\|`THATCH`), `in_flood_zone` (bool), `has_security_system` (bool) |

Eligibility age is checked on `age` / `owner_age` / `proposer_age`. Application-only inputs: `kyc`
{`full_name`, `date_of_birth`, `aadhaar`, `pan`, `address`} and, for TERM_LIFE, `health_declaration`
{`has_pre_existing_condition` (bool), `details` (string, never logged)}. At renewal, ages and
`vehicle_age_years` advance by 1 per completed 12-month term; all other inputs are unchanged.

## Premium, delta and refund formulas

All `Decimal`, full precision, quantized to `0.01` `ROUND_HALF_UP` **once at the end**.

- Premium (E3-S1): TERM_LIFE `SI × base_rate × age_band × term_band × (1 + smoker_loading if smoker)`;
  MOTOR `SI × base_rate × vehicle_age_band × engine_cc_band × zone_rate × (1 − ncb_discount)`;
  HOUSEHOLD `SI × base_rate × construction_rate × (1 + flood_zone_loading if in_flood_zone) × (1 − security_discount if has_security_system)`;
  result `max(raw, minimum_premium)`.
- Days: `term_days = (expiry_date − effective_date).days + 1`, `days_elapsed = (d − effective_date).days`,
  `unused_days = term_days − days_elapsed`.
- Endorsement delta: `(new_premium − old_premium) × unused_days / term_days` on the policy's own rule version;
  stored on the `Endorsement` row, not collected.
- Refund: `FREE_LOOK` (new business only, `days_elapsed ≤ free_look_days`) = premium paid for the term, no fee;
  otherwise `PRO_RATA` = `max(premium_paid × unused_days / term_days − admin_fee, 0.00)`.

## Premium payments and renewal

- First-term premium is recorded as paid at issuance (one `PremiumPayment`, `due_date = effective_date`).
- Renewal premium is due on the new term's effective date (`expiry_date + 1 day`), quoted on the active
  version (`GET …/renewal`) and paid on the current policy (`POST …/payments`, recording `rule_version`).
- End-of-day for `as_of`: paid and `as_of > expiry_date` → `RENEW` (new Policy, new sequence number,
  `previous_policy_number` = old number; old → `RENEWED`); unpaid and `due ≤ as_of ≤ due + grace_period_days`
  → `IN_GRACE`; unpaid and `as_of > due + grace_period_days` → `LAPSE`; otherwise `NONE`.

## v1 rule values

The v1 base rates, factor tables, minimum premiums, eligibility, underwriting rules, reason codes and
renewal/cancellation values are defined once in `specs/stories/E2-S1.md`; every premium, delta and refund
example in `specs/` must be computable from them. Reason codes: automatic `…-UW-001…0xx`; underwriter /
override `…-UW-900` "Underwriter approved", `…-UW-901` "Admin override: risk accepted", `…-UW-902`
"Underwriter declined". Decision and override reason codes must exist in the case's rule-version `reason_codes`.

## Layer import rules

`types` → nothing · `domain` → types · `config` → types, domain · `repository` → types, config ·
`service` → types, domain, config, repository · `api` → types, config, service (not repository) ·
`lib` → **standard library only**. `config`, `repository`, `service` and `api` may import `lib`;
**`types` and `domain` may not** — they stay pure (no logging, I/O or clock), which keeps premium and
underwriting math deterministic (AC-01).

## Synthetic data (fixtures, seeds, examples)

| Field | Synthetic format | Example |
|-------|------------------|---------|
| Aadhaar | 12 digits starting `9999` | `999900000001` |
| PAN | `AAAAA` + 4 digits + `A` | `AAAAA0001A` |
| Masked Aadhaar (display/log/DB) | last 4 digits only | `XXXX-XXXX-0001` |
| Masked PAN (display/log/DB) | 4 digits only, letters masked | `XXXXX0001X` |
| Names / addresses | obviously fictional | `Test Customer 01`, `1 Sample Street, Testville` |

## Git / CI

- Diff base for "changed files" checks: `git merge-base HEAD origin/$CI_DEFAULT_BRANCH` in CI,
  `git merge-base HEAD main` locally.
- Fix-loop traces use one template — the one rendered by `scripts/fix_loop_agent.py`
  (sections: 1 Detect, 2.N Reproduce + fix, 3.N Validate, 4 Change set, 5 PR).
