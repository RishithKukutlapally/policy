# Quote Engine — Feature Specification

| | |
|---|---|
| **Root** | [app_spec.md](app_spec.md) |
| **Owns** | AC-01, AC-12, AC-13 |
| **Epic** | E3 — Quote engine (Sprint 2) |
| **Depends on** | [product-catalog_spec.md](product-catalog_spec.md) (active version, `RuleSet`) |
| **Canonical names** | `docs/conventions.md` |

## Purpose

Turn a product code and an insured-profile / risk input into a **deterministic premium** computed only from the
product's **active PUBLISHED rule set**, and record the quote with the exact rule version used so the premium
can be reproduced later. The same calculator is reused by underwriting/issuance, endorsements
(sum-insured change) and renewal (refreshed premium).

## Scope

**In scope**
- Pure premium calculator `src/domain/premium_calculator.py` for `TERM_LIFE`, `MOTOR`, `HOUSEHOLD` (Decimal only).
- Quote input validation against `eligibility.*` and the factor tables of the active rule set.
- Quote service `src/service/quote_service.py`: resolve active version, validate, price, persist `Quote`.
- Reproduction: recompute a stored quote against its recorded rule version.
- Quote API and the customer **Get a Quote** UI.

**Out of scope**
- Taxes (GST), discounts not in the rule file, multi-currency, quote expiry, instalment plans.
- KYC and underwriting decisions ([underwriting_spec.md](underwriting_spec.md)).
- Quotes carry **no PII** — no Aadhaar, PAN or health declaration fields are accepted.

## Business rules

### BR-1 Version resolution
The quote is priced with the product's **active version** (highest PUBLISHED version, see product-catalog BR-4).
If the product has no PUBLISHED version the quote is **refused** with 409 `NO_PUBLISHED_VERSION`; there is no
fallback to a DRAFT, a superseded version, a hard-coded rate or another product. Nothing is persisted.

### BR-2 Inputs per product

Request body `{"product": "<CODE>", "inputs": {…}}`; field names are the canonical list in `docs/conventions.md`.

| Product | Field | Type | Validated against |
|---------|-------|------|-------------------|
| all | `product` | `ProductCode` | must be a known product (else 404 `NOT_FOUND`) |
| all | `sum_insured` | money string | `eligibility.min_sum_insured` ≤ x ≤ `eligibility.max_sum_insured` |
| `TERM_LIFE` | `age` | int | `eligibility.min_age` ≤ x ≤ `eligibility.max_age`; must fall in a `premium.factors.age_bands` band |
| `TERM_LIFE` | `smoker` | bool | — |
| `TERM_LIFE` | `term_years` | int 5–30 | must fall in a `premium.factors.term_years_bands` band |
| `MOTOR` | `owner_age` | int | `eligibility.min_age` ≤ x ≤ `eligibility.max_age` |
| `MOTOR` | `vehicle_age_years` | int ≥ 0 | must fall in a `premium.factors.vehicle_age_bands` band |
| `MOTOR` | `engine_cc` | int > 0 | must fall in a `premium.factors.engine_cc_bands` band |
| `MOTOR` | `zone` | string | key of `premium.factors.zone_rates` (`A`, `B`) |
| `MOTOR` | `ncb_percent` | string | key of `premium.factors.ncb_discounts` (`"0"`, `"20"`, `"25"`, `"35"`, `"45"`, `"50"`) |
| `HOUSEHOLD` | `proposer_age` | int | `eligibility.min_age` ≤ x ≤ `eligibility.max_age` |
| `HOUSEHOLD` | `construction_type` | string | key of `premium.factors.construction_type_rates` (`CONCRETE`, `BRICK`, `TIMBER`, `THATCH`) |
| `HOUSEHOLD` | `in_flood_zone` | bool | — |
| `HOUSEHOLD` | `has_security_system` | bool | — |

Any violation → 422 `VALIDATION_ERROR` with one `details` entry `{field, code}` per failing field (all failures
reported together, not just the first); detail codes `REQUIRED`, `OUT_OF_RANGE`, `UNKNOWN_CODE`, `UNKNOWN_FIELD`,
`MONEY_MUST_BE_STRING`. Unknown extra fields are rejected. A money value sent as a JSON number is rejected
(`sum_insured` must be a string such as `"500000.00"`). Nothing is persisted on 422.

### BR-3 Premium formulae (all `Decimal`, no intermediate rounding)

`raw` is computed at full `Decimal` precision; then `premium = max(raw, premium.minimum_premium)` quantized to
`0.01` with `ROUND_HALF_UP`. A band multiplier is the `multiplier` of the band whose `min` ≤ value ≤ `max`.

| Product | `raw` |
|---------|-------|
| `TERM_LIFE` | `sum_insured × premium.base_rate × age_bands[age] × term_years_bands[term_years] × (1 + smoker_loading if smoker else 1)` — annual premium |
| `MOTOR` | `sum_insured × premium.base_rate × vehicle_age_bands[vehicle_age_years] × engine_cc_bands[engine_cc] × zone_rates[zone] × (1 − ncb_discounts[ncb_percent])` |
| `HOUSEHOLD` | `sum_insured × premium.base_rate × construction_type_rates[construction_type] × (1 + flood_zone_loading if in_flood_zone else 1) × (1 − security_discount if has_security_system else 1)` |

`smoker_loading` (`"0.50"`) and `flood_zone_loading` (`"0.25"`) are loadings added to 1; `ncb_discounts` values
and `security_discount` (`"0.10"`) are fractions subtracted from 1 — see E2-S1 and `docs/conventions.md`.

### BR-4 Determinism
The calculator is a pure function `(RuleSet, QuoteInput) → Decimal`: no clock, randomness, I/O, logging, global
state or `float`. The same input and rule version always yield the same premium, byte-for-byte as a string.

### BR-5 Quote record and reproduction
Every successful quote persists `product`, `rule_version`, the validated inputs, `sum_insured`, `premium`,
`currency`, `actor_id` and `created_at`. Re-pricing the stored inputs against the **recorded** version (not the
current active version) must return the identical premium, even after a newer version is published.
Reproduction is exposed as `GET /api/quotes/{quote_id}/reprice`, which returns the recomputed premium and
`"matches": true|false`; it never mutates the quote.

## API endpoints

| Method | Path | Roles | Success | Errors |
|--------|------|-------|---------|--------|
| POST | `/api/quotes` | CUSTOMER | 201 `{quote_id, product, rule_version, sum_insured, premium, currency, created_at}` | 401 `UNAUTHENTICATED`, 403 `FORBIDDEN`, 404 `NOT_FOUND` (unknown product), 409 `NO_PUBLISHED_VERSION`, 422 `VALIDATION_ERROR` |
| GET | `/api/quotes/{quote_id}` | owner CUSTOMER, UNDERWRITER, ADMIN | 200 stored quote incl. inputs | 401, 404 `NOT_FOUND` (unknown or another customer's quote) |
| GET | `/api/quotes/{quote_id}/reprice` | owner CUSTOMER, UNDERWRITER, ADMIN | 200 `{quote_id, rule_version, stored_premium, recomputed_premium, matches}` | 401, 404 |

`quote_id` is a UUID4 string. Money is returned as strings (`"14322.00"`). Errors use the envelope in
`docs/conventions.md`. Performance target: `POST /api/quotes` < 2 s p95 (BRD M1).

## Data

| Model | Table | Append-only | Key columns |
|-------|-------|-------------|-------------|
| `Quote` | `quotes` | — (insert only in practice) | `id` (UUID4 = `quote_id`), `product`, `rule_version`, `inputs` (JSON), `sum_insured` `Numeric(12, 2)`, `premium` `Numeric(12, 2)`, `currency`, `actor_id`, `created_at` |
| `RuleSetVersion` | `rule_set_versions` | ✅ (read only here) | see [product-catalog_spec.md](product-catalog_spec.md) |

## NFRs that apply

- **NFR-01** — calculator and service use `Decimal` only; `ROUND_HALF_UP` to 0.01 once at the end; hook
  `premium-precision-check`; architecture test forbids `float` in `src/domain/premium_calculator.py`.
- **NFR-03** — quote inputs contain no PII; logs record `quote_id`, product, version and premium only.
- **NFR-04** — role check at the router; customers can read only their own quotes.
- **NFR-06** — quote requests logged as JSON lines with `correlation_id`.
- **NFR-08** — domain purity (no `lib`, I/O, clock) enforced by import-linter.

## Implementing stories

| Story | Title | Layer |
|-------|-------|-------|
| E3-S1 | Premium calculator (three products, Decimal) | Domain |
| E3-S2 | Quote service + `Quote` persistence | Service |
| E3-S3 | Quote API + Get-a-Quote UI | UI |


Golden cases for `/quote-check` live with the calculator tests. Every figure below is computed from the **v1
rule values in `specs/stories/E2-S1.md`** (the actual v1 files are authoritative; golden tests are computed from
them). The hypothetical MOTOR v2 used in versioning scenarios is identical to v1 except `premium.base_rate`
`"0.0320"`.

| Product | v1 values used below |
|---------|----------------------|
| `TERM_LIFE` | `base_rate` `"0.0015"`, `minimum_premium` `"3000.00"`, age 31–40 → `"1.20"`, term 16–25 → `"1.10"`, `smoker_loading` `"0.50"`, eligibility age 18–60 |
| `MOTOR` | `base_rate` `"0.0310"`, `minimum_premium` `"2500.00"`, vehicle age 0–5 → `"1.00"`, engine 0–1000 cc → `"1.00"`, 1001–1500 cc → `"1.10"`, `zone_rates` `A` → `"1.05"`, `B` → `"1.00"`, `ncb_discounts` `"20"` → `"0.20"`, `"50"` → `"0.50"`, eligibility owner_age 18–75 |
| `HOUSEHOLD` | `base_rate` `"0.0008"`, `minimum_premium` `"1500.00"`, `BRICK` → `"1.00"`, `flood_zone_loading` `"0.25"`, `security_discount` `"0.10"`, max sum insured `"20000000.00"` |

## Acceptance Criteria

### AC-01 — The quote engine returns a deterministic premium for a product and insured profile, sourced from the active versioned rule file

```gherkin
Scenario: MOTOR premium from the active v1 rule file
  Given MOTOR version 1 is the active PUBLISHED version
  When customer "cust-001" sends POST /api/quotes with product "MOTOR" and inputs:
    | sum_insured | owner_age | vehicle_age_years | engine_cc | zone | ncb_percent |
    | 500000.00   | 30        | 3                 | 1200      | A    | 20          |
  Then the response status is 201
  And "premium" is "14322.00"
  And "rule_version" is 1
  # 500000.00 × 0.0310 × 1.00 (vehicle 0–5) × 1.10 (1001–1500 cc) × 1.05 (zone A) × (1 − 0.20) = 14322.00

Scenario: TERM_LIFE premium, non-smoker and smoker
  Given TERM_LIFE version 1 is the active PUBLISHED version
  When the premium is calculated for age 35, term_years 20, sum_insured "5000000.00" and smoker false
  Then the premium is "9900.00"
  # 5000000.00 × 0.0015 × 1.20 × 1.10 = 9900.00
  When the same profile is calculated with smoker true
  Then the premium is "14850.00"
  # 5000000.00 × 0.0015 × 1.20 × 1.10 × (1 + 0.50) = 14850.00

Scenario: HOUSEHOLD premium rounds half up to 0.01
  Given HOUSEHOLD version 1 is the active PUBLISHED version
  When the premium is calculated for sum_insured "3000625.00", construction_type "BRICK", in_flood_zone true, has_security_system false, proposer_age 42
  Then the raw amount is exactly Decimal("3000.625")
  And the premium is "3000.63" (ROUND_HALF_UP, not banker's "3000.62")
  # 3000625.00 × 0.0008 × 1.00 × (1 + 0.25) = 3000.625

Scenario: Minimum premium applies
  Given MOTOR version 1 is the active PUBLISHED version
  When the premium is calculated for sum_insured "100000.00", vehicle_age_years 2, engine_cc 900, zone "B", ncb_percent "50", owner_age 40
  Then the raw amount is Decimal("1550.00")
  And the premium is "2500.00" from "premium.minimum_premium"
  # 100000.00 × 0.0310 × 1.00 × 1.00 × 1.00 × (1 − 0.50) = 1550.00 < 2500.00

Scenario: Identical input gives identical premium every time
  Given MOTOR version 1 is the active PUBLISHED version
  When the golden MOTOR profile above is priced 100 times
  Then all 100 premiums equal "14322.00"
  And every returned premium is a Decimal with exponent -2

Scenario: Rates come from the rule file, not code
  Given MOTOR version 2 is published with "premium.base_rate" "0.0320" and otherwise identical to version 1
  When customer "cust-001" quotes the golden MOTOR profile (sum_insured "500000.00", owner_age 30, vehicle_age_years 3, engine_cc 1200, zone "A", ncb_percent "20")
  Then "rule_version" is 2
  And "premium" is "14784.00"
  # 500000.00 × 0.0320 × 1.00 × 1.10 × 1.05 × (1 − 0.20) = 14784.00
```

### AC-12 — Invalid quote input returns 422 with field errors; a product with no PUBLISHED version is refused with no fallback

```gherkin
Scenario: Input outside eligibility returns 422 with every failing field
  Given TERM_LIFE version 1 is active with "eligibility.min_age" 18 and "eligibility.max_age" 60
  When customer "cust-001" sends POST /api/quotes with product "TERM_LIFE", age 17, term_years 40, smoker false, sum_insured "5000000.00"
  Then the response status is 422
  And the error code is "VALIDATION_ERROR"
  And "error.details" contains {"field": "age", "code": "OUT_OF_RANGE"}
  And "error.details" contains {"field": "term_years", "code": "OUT_OF_RANGE"}
  And no row is added to "quotes"

Scenario: Unknown factor code and missing field
  Given MOTOR version 1 is active with "premium.factors.zone_rates" keys "A" and "B"
  When customer "cust-001" sends POST /api/quotes with product "MOTOR", zone "Z", no "engine_cc", sum_insured "500000.00", owner_age 30, vehicle_age_years 1, ncb_percent "0"
  Then the response status is 422
  And "error.details" contains {"field": "zone", "code": "UNKNOWN_CODE"}
  And "error.details" contains {"field": "engine_cc", "code": "REQUIRED"}

Scenario: Sum insured outside the product limits
  Given HOUSEHOLD version 1 is active with "eligibility.max_sum_insured" "20000000.00"
  When customer "cust-001" quotes HOUSEHOLD with sum_insured "25000000.00"
  Then the response status is 422
  And "error.details" contains {"field": "sum_insured", "code": "OUT_OF_RANGE"}

Scenario: Money sent as a float is rejected
  When customer "cust-001" sends POST /api/quotes for MOTOR with "sum_insured": 500000.5 as a JSON number
  Then the response status is 422
  And "error.details" contains {"field": "sum_insured", "code": "MONEY_MUST_BE_STRING"}

Scenario: No PUBLISHED version means the quote is refused
  Given HOUSEHOLD has only version 1 with status DRAFT and no PUBLISHED version
  When customer "cust-001" sends a schema-valid HOUSEHOLD quote request
  Then the response status is 409
  And the error code is "NO_PUBLISHED_VERSION"
  And no premium is returned
  And no row is added to "quotes"

Scenario: No fallback to a draft even when one exists alongside nothing published
  Given TERM_LIFE has a DRAFT version 1 with "premium.base_rate" "0.0015" and no PUBLISHED version
  When the quote service is asked to price any TERM_LIFE profile
  Then it raises the typed "NoPublishedVersionError"
  And the premium calculator is never invoked
```

### AC-13 — Every quote records its product and rule version; re-quoting the same input on that version reproduces the premium

```gherkin
Scenario: Quote stores product and rule version
  Given MOTOR version 1 is active
  When customer "cust-001" quotes MOTOR with sum_insured "500000.00", owner_age 30, vehicle_age_years 3, engine_cc 1200, zone "A", ncb_percent "20"
  Then the response has a UUID4 "quote_id" (alias Q1)
  And the "quotes" row for Q1 has product "MOTOR", rule_version 1, premium "14322.00" and the validated inputs

Scenario: Reprice after a newer version is published reproduces the original premium
  Given quote Q1 was priced on MOTOR version 1 at "14322.00"
  And MOTOR version 2 with "premium.base_rate" "0.0320" has since been published and is active
  When customer "cust-001" sends GET /api/quotes/{Q1}/reprice
  Then the response status is 200
  And "rule_version" is 1
  And "recomputed_premium" is "14322.00"
  And "matches" is true
  And the "quotes" row for Q1 is unchanged

Scenario: A fresh quote with the same input uses the new active version
  Given MOTOR version 2 is active
  When customer "cust-001" quotes the same MOTOR input again
  Then a new quote Q2 is returned with rule_version 2 and premium "14784.00"
  And quote Q1 still shows rule_version 1 and premium "14322.00"

Scenario: Customer cannot read another customer's quote
  Given quote Q1 belongs to "cust-001"
  When customer "cust-002" sends GET /api/quotes/{Q1}
  Then the response status is 404 with error code "NOT_FOUND"
```
