# Product Catalog — Feature Specification

| | |
|---|---|
| **Root** | [app_spec.md](app_spec.md) |
| **Owns** | AC-02, AC-11 |
| **Epic** | E2 — Product catalog & rule versions (Sprint 1) |
| **Canonical names** | `docs/conventions.md` |

## Purpose

Hold the three insurance products and their **versioned, immutable rule sets** — the single source of every
rate, eligibility limit, underwriting rule, endorsement type, renewal term and cancellation rule used downstream.
Admins create a new version as a DRAFT and publish it without any code change (BRD M4); once PUBLISHED a
version never changes, so past quotes and policies stay reproducible.

## Scope

**In scope**
- Three products `TERM_LIFE`, `MOTOR`, `HOUSEHOLD`, each with its own rule-file folder and v1 file.
- Rule-file JSON schema `backend/policy_rules/schema/rule-file.schema.json` with product-specific factor keys.
- Rule loader `src/config/rule_loader.py` (file → `RuleSet`, schema validation) and seed import into `rule_set_versions`.
- `PUBLISHED.lock` ledger for published files.
- Catalog service: list products, list versions (incl. active flag and rule body), create draft, publish.
- Catalog API and the Admin **Product Catalog Manager** UI (versions list, draft editor, publish).

**Out of scope**
- Adding a fourth product code at runtime (a new product requires a `docs/conventions.md` change first).
- Deleting or unpublishing versions; scheduled/future-dated activation; rule DSLs (BRD §7 option C rejected).
- Premium calculation itself ([quote-engine_spec.md](quote-engine_spec.md)).

## Business rules

### BR-1 Products and rule files

| Product | Folder | Reason-code prefix | Required `premium.factors` keys |
|---------|--------|--------------------|---------------------------------|
| `TERM_LIFE` | `backend/policy_rules/term_life/` | `TL-UW-###` | `age_bands`, `smoker_loading`, `term_years_bands` |
| `MOTOR` | `backend/policy_rules/motor/` | `MO-UW-###` | `vehicle_age_bands`, `engine_cc_bands`, `ncb_discounts`, `zone_rates` |
| `HOUSEHOLD` | `backend/policy_rules/household/` | `HH-UW-###` | `construction_type_rates`, `flood_zone_loading`, `security_discount` |

Files are named `v<N>.json` (`v1.json`, `v2.json`, …).

### BR-2 Rule-file shape (schema-validated)

Top-level fields: `product`, `version` (int ≥ 1), `status` (`DRAFT` | `PUBLISHED`), `effective_from` (ISO date),
`currency` (`"INR"`), and:

- `premium.base_rate`, `premium.minimum_premium`, `premium.factors.*` (keys per BR-1).
- `eligibility.min_age`, `eligibility.max_age` (int), `eligibility.min_sum_insured`, `eligibility.max_sum_insured`.
- `underwriting.rules[]` (`when`, `decision` ∈ `AUTO_BIND`|`MANUAL_REVIEW`|`DECLINE`, `reason_code`) and
  `underwriting.reason_codes` (map code → description). Every `reason_code` used in `underwriting.rules` must
  exist in `underwriting.reason_codes` and match the product prefix.
- `endorsement.allowed_types` ⊆ {`CHANGE_ADDRESS`, `ADD_NOMINEE`, `CHANGE_SUM_INSURED`}.
- `renewal.term_months`, `renewal.grace_period_days`.
- `cancellation.method` (`PRO_RATA` only in v1), `cancellation.free_look_days`, `cancellation.admin_fee`.

All money and rates are **JSON strings** parsed to `Decimal` (NFR-01); a JSON number in a money/rate field fails
validation. Bands are arrays of `{ "min": int, "max": int, "multiplier": "<decimal string>" }` with no gaps or
overlaps; maps are `{ "<code>": "<decimal string>" }`. `eligibility.min_sum_insured` ≤ `max_sum_insured` and
`min_age` ≤ `max_age`. The body's `product` must equal the path product.

### BR-3 Distinct rule sets
Each product's rule set is distinct: its own factor keys (BR-1), reason-code prefix, and values. A rule file for
one product is rejected if it carries another product's factor keys or reason-code prefix.

### BR-4 Versions and status
- A version is identified by (`product`, `version`). Status is `DRAFT` or `PUBLISHED`.
- `rule_set_versions` is **append-only**: creating a draft, replacing a draft and publishing each **insert a new
  row**; the current state of (`product`, `version`) is its latest row. No `UPDATE`/`DELETE` ever.
- **Create draft**: version number = highest existing version for the product + 1. At most **one open DRAFT per
  product**; a second create returns 409 `DRAFT_ALREADY_OPEN`.
- **Publish**: DRAFT → PUBLISHED; the body is re-validated; only `status` changes (no publish timestamp inside
  the rule body — publish time is the new row's `created_at`). Publishing a PUBLISHED version or modifying a
  PUBLISHED version returns 409 `VERSION_IMMUTABLE`. There is no endpoint that edits a stored version.
- **Active version** of a product = its PUBLISHED version with the highest version number. Exactly one active
  version per product at any time; older PUBLISHED versions are **superseded** but remain readable and are still
  used to reproduce quotes/policies that recorded them (AC-13).
- File-based versions (seed) are imported by `python -m src.seed`; a file with `status` `PUBLISHED` must have a
  matching line `<sha256>  <product_folder>/v<N>.json` in `backend/policy_rules/PUBLISHED.lock` (append-only,
  verified by the architecture test and hooks `policy-immutability-check`, `shell-immutability-check`).
- Create and publish write an `audit_records` row (`RULE_VERSION_DRAFT_CREATED`, `RULE_VERSION_PUBLISHED`) with
  the admin's actor id (NFR-04).
- `underwriting.rules[].when` follows the `docs/conventions.md` format (`<field> <op> <value>` joined by ` and `;
  ops `<`, `<=`, `>`, `>=`, `==`, `!=`, `in`); `underwriting.reason_codes` holds the automatic codes
  (`…-UW-001…0xx`) and the manual codes `…-UW-900`/`901`/`902` (see E2-S1).

## API endpoints

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| GET | `/api/products` | CUSTOMER, UNDERWRITER, ADMIN | 200 list of `{product, name, active_version, currency}` | 401 |
| GET | `/api/products/{product}/versions` | CUSTOMER, UNDERWRITER, ADMIN | 200 list of `{version, status, effective_from, is_active, created_at, rules}` (`rules` = full rule body) | 401, 404 `NOT_FOUND` |
| POST | `/api/products/{product}/versions` | ADMIN | 201 `{product, version, status: "DRAFT"}` | 401, 403 `FORBIDDEN`, 404, 409 `DRAFT_ALREADY_OPEN`, 422 `VALIDATION_ERROR` |
| PUT | `/api/products/{product}/versions/{version}` | ADMIN | 200 `{product, version, status: "DRAFT"}` — replaces an open DRAFT (DEC-009) by appending a new row; audited `RULE_VERSION_DRAFT_REPLACED` | 401, 403, 404, 409 `VERSION_IMMUTABLE`, 422 `VALIDATION_ERROR` |
| POST | `/api/products/{product}/versions/{version}/publish` | ADMIN | 200 `{product, version, status: "PUBLISHED", is_active: true}` | 401, 403, 404, 409 `VERSION_IMMUTABLE`, 422 `VALIDATION_ERROR` |

`{product}` is the product code (`TERM_LIFE`, `MOTOR`, `HOUSEHOLD`). 422 responses list schema violations in
`error.details` as `{field, code}` with a dotted `field` path (e.g. `premium.factors.zone_rates`, code
`SCHEMA_VIOLATION`). Endpoint list: `docs/conventions.md`.

## Data

| Model | Table | Append-only | Key columns |
|-------|-------|-------------|-------------|
| `RuleSetVersion` | `rule_set_versions` | ✅ | `id`, `product`, `version`, `status`, `effective_from`, `content` (JSON), `content_sha256`, `actor_id`, `created_at`; unique (`product`, `version`, `status`) |
| `AuditRecord` | `audit_records` | ✅ | `id`, `actor_id`, `actor_role`, `action`, `entity_type`, `entity_id`, `detail` (JSON), `created_at` |

Rule files: `backend/policy_rules/<product_folder>/v<N>.json`, schema `backend/policy_rules/schema/rule-file.schema.json`,
ledger `backend/policy_rules/PUBLISHED.lock`. Value objects in `src/types/rules.py` (`RuleSet`, …); enums in
`src/types/enums.py` (`ProductCode`).

## NFRs that apply

- **NFR-01** — money/rates as JSON strings → `Decimal`; rates stored `Numeric(9, 6)`, money `Numeric(12, 2)`.
- **NFR-02** — `rule_set_versions` append-only; PUBLISHED versions immutable (DB and files).
- **NFR-04** — write endpoints ADMIN-only, enforced in `src/api/deps.py`; every write audited with actor id.
- **NFR-05** — policy migrations are new `v<N>.json` files + appended `PUBLISHED.lock` lines; never edits.
- **NFR-08** — architecture test recomputes `PUBLISHED.lock` hashes and fails if a PUBLISHED file changed.

## Implementing stories

| Story | Title | Layer |
|-------|-------|-------|
| E2-S1 | Rule-set types, JSON schema and three v1 rule files + `PUBLISHED.lock` | Types |
| E2-S2 | Rule loader, `RuleSetVersion` model/repository, seed import | Repository |
| E2-S3 | Catalog service: list, active version, create draft, publish | Service |
| E2-S4 | Catalog API + Product Catalog Manager UI | UI |

## Acceptance Criteria

### AC-02 — The catalog supports at least 3 products (TERM_LIFE, MOTOR, HOUSEHOLD) with distinct rule sets

```gherkin
Scenario: Seeded catalog lists three products each with an active v1
  Given the database was seeded with "python -m src.seed"
  When customer "cust-001" sends GET /api/products with X-Actor-Role "CUSTOMER"
  Then the response status is 200
  And the response lists exactly these products:
    | product   | active_version | currency |
    | TERM_LIFE | 1              | INR      |
    | MOTOR     | 1              | INR      |
    | HOUSEHOLD | 1              | INR      |

Scenario: Each product's active rule set is distinct
  When the active rule sets of TERM_LIFE, MOTOR and HOUSEHOLD are loaded
  Then TERM_LIFE "premium.factors" has keys "age_bands", "smoker_loading", "term_years_bands"
  And MOTOR "premium.factors" has keys "vehicle_age_bands", "engine_cc_bands", "ncb_discounts", "zone_rates"
  And HOUSEHOLD "premium.factors" has keys "construction_type_rates", "flood_zone_loading", "security_discount"
  And every "underwriting.reason_codes" key of TERM_LIFE starts with "TL-UW-", MOTOR with "MO-UW-", HOUSEHOLD with "HH-UW-"
  And the three "premium.base_rate" values are not all equal

Scenario: Every v1 file validates against the schema and matches the ledger
  Given the files "term_life/v1.json", "motor/v1.json" and "household/v1.json" with status "PUBLISHED"
  When each is validated against "backend/policy_rules/schema/rule-file.schema.json"
  Then all three are valid
  And "backend/policy_rules/PUBLISHED.lock" contains a line "<sha256>  motor/v1.json" whose hash equals the file's sha256

Scenario: A rule file with another product's factors is rejected
  Given a MOTOR rule body whose "premium.factors" contains "age_bands" and lacks "zone_rates"
  When the rule loader validates it
  Then validation fails with field errors "premium.factors.zone_rates" and "premium.factors.age_bands"

Scenario: Money written as a JSON number is rejected
  Given a HOUSEHOLD rule body with "premium.minimum_premium": 1500.00 as a JSON number
  When the rule loader validates it
  Then validation fails with field error "premium.minimum_premium"
```

### AC-11 — Admin creates a DRAFT version and publishes it; PUBLISHED versions are immutable; only one active version per product

```gherkin
Scenario: Admin creates a draft version
  Given MOTOR has only version 1 with status PUBLISHED
  When admin "admin-001" sends POST /api/products/MOTOR/versions with a schema-valid MOTOR body whose "premium.base_rate" is "0.0320"
  Then the response status is 201
  And the body is {"product": "MOTOR", "version": 2, "status": "DRAFT"}
  And the active MOTOR version is still 1
  And an "audit_records" row exists with actor_id "admin-001" and action "RULE_VERSION_DRAFT_CREATED"

Scenario: Admin publishes the draft and it becomes the single active version
  Given MOTOR version 2 is DRAFT and version 1 is PUBLISHED
  When admin "admin-001" sends POST /api/products/MOTOR/versions/2/publish
  Then the response status is 200
  And GET /api/products/MOTOR/versions shows exactly one entry with "is_active" true: version 2 with "rules.premium.base_rate" "0.0320"
  And version 1 is still PUBLISHED and listed with "rules.premium.base_rate" "0.0310"
  And "rule_set_versions" gained one new row and no existing row was updated or deleted
  And an "audit_records" row exists with actor_id "admin-001" and action "RULE_VERSION_PUBLISHED"

Scenario: Admin replaces an open draft (DEC-009)
  Given MOTOR version 2 is DRAFT with "premium.base_rate" "0.0320"
  When admin "admin-001" sends PUT /api/products/MOTOR/versions/2 with a schema-valid MOTOR body whose "premium.base_rate" is "0.0330"
  Then the response status is 200
  And the body is {"product": "MOTOR", "version": 2, "status": "DRAFT"}
  And "rule_set_versions" gained one new row and no existing row was updated or deleted
  And GET /api/products/MOTOR/versions shows version 2 as DRAFT with "rules.premium.base_rate" "0.0330"
  And an "audit_records" row exists with actor_id "admin-001" and action "RULE_VERSION_DRAFT_REPLACED"

Scenario: A published version cannot be replaced
  Given MOTOR version 1 is PUBLISHED
  When admin "admin-001" sends PUT /api/products/MOTOR/versions/1 with a schema-valid MOTOR body
  Then the response status is 409 with error code "VERSION_IMMUTABLE"
  And GET /api/products/MOTOR/versions still lists version 1 with "rules.premium.base_rate" "0.0310"

Scenario: A published version cannot be modified
  Given MOTOR version 1 is PUBLISHED
  When the catalog service is asked to store a changed body for MOTOR version 1 with "premium.base_rate" "0.0299"
  Then it raises the typed error mapped to 409 "VERSION_IMMUTABLE"
  And the API exposes no route that edits a stored version
  And GET /api/products/MOTOR/versions still lists version 1 with "rules.premium.base_rate" "0.0310"

Scenario: A published version cannot be published again
  Given MOTOR version 1 is PUBLISHED
  When admin "admin-001" sends POST /api/products/MOTOR/versions/1/publish
  Then the response status is 409 with error code "VERSION_IMMUTABLE"

Scenario: Only one open draft per product
  Given HOUSEHOLD version 2 is DRAFT
  When admin "admin-001" sends POST /api/products/HOUSEHOLD/versions with a schema-valid HOUSEHOLD body
  Then the response status is 409 with error code "DRAFT_ALREADY_OPEN"

Scenario: Malformed draft is rejected on create
  When admin "admin-001" sends POST /api/products/TERM_LIFE/versions with "eligibility.min_age" 60 and "eligibility.max_age" 18
  Then the response status is 422 with error code "VALIDATION_ERROR"
  And "error.details" contains field "eligibility.min_age"
  And no row is added to "rule_set_versions"

Scenario: Editing a published rule file on disk is caught
  Given "backend/policy_rules/motor/v1.json" is PUBLISHED and listed in "PUBLISHED.lock"
  When its "premium.base_rate" is changed from "0.0310" to "0.0300" in the working tree
  Then the architecture test recomputing "PUBLISHED.lock" hashes fails for "motor/v1.json"

Scenario: Non-admin cannot draft or publish
  When underwriter "uw-001" sends POST /api/products/MOTOR/versions/2/publish with X-Actor-Role "UNDERWRITER"
  Then the response status is 403 with error code "FORBIDDEN"
  And MOTOR version 2 remains DRAFT
```
