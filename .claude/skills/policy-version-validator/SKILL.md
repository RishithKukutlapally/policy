---
name: policy-version-validator
description: Validate versioned policy rule files (backend/policy_rules/<product>/v<N>.json) — JSON schema, required fields per product, version monotonicity, PUBLISHED immutability vs git HEAD, and reason-code integrity for underwriting (AC-02, AC-04, NFR-02, NFR-05).
argument-hint: "[<TERM_LIFE|MOTOR|HOUSEHOLD> | all]"
context: fork
agent: policy-version-validator-agent
---

# Policy Version Validator

Gatekeeper for rule-set files. Used by `/publish-policy-version`, by CI, and before any sprint touching
quote or underwriting. Read-only: it reports, it does not rewrite rule files.

## Layout it expects
```
backend/policy_rules/
  schema/rule-file.schema.json         # JSON Schema (draft 2020-12)
  PUBLISHED.lock                       # "<sha256>  <relative path>" per published file, append-only
  term_life/v1.json v2.json ...        # folders lower snake_case; `product` field is the code (TERM_LIFE)
  motor/v1.json ...
  household/v1.json ...
```
Names, folder ↔ code mapping and the rule-file shape come from `docs/conventions.md`; this table must match it.

## 1. Schema (all products)

Required fields (money/rates are JSON **strings** → `Decimal`):

| Field | Type | Rule |
|-------|------|------|
| `product` | enum | `TERM_LIFE|MOTOR|HOUSEHOLD`; must equal the folder's code (`term_life` → `TERM_LIFE`) |
| `version` | int ≥ 1 | must equal `N` in `v<N>.json` |
| `status` | enum | `DRAFT|PUBLISHED` |
| `effective_from` | ISO date | ≥ previous version's `effective_from` |
| `currency` | string | `INR` |
| `premium.base_rate`, `premium.minimum_premium` | decimal string | e.g. `"0.0310"`, `"2500.00"` |
| `premium.factors` | object | product-specific factor tables (below); every numeric leaf a decimal string |
| `eligibility` | object | `min_age < max_age` (int); `min_sum_insured < max_sum_insured` (decimal strings) |
| `underwriting.rules` | array | each `{when, decision: AUTO_BIND|MANUAL_REVIEW|DECLINE, reason_code}` |
| `underwriting.reason_codes` | object | `code → description`; codes match `^(TL|MO|HH)-UW-\d{3}$` with product prefix |
| `endorsement.allowed_types` | array | subset of `CHANGE_ADDRESS|ADD_NOMINEE|CHANGE_SUM_INSURED` (AC-06) |
| `renewal.term_months`, `renewal.grace_period_days` | int | AC-07 |
| `cancellation.method` | enum | e.g. `PRO_RATA` (AC-08); `cancellation.free_look_days` int, `cancellation.admin_fee` decimal string |

Product-specific `premium.factors` keys:
- **TERM_LIFE**: `age_bands`, `smoker_loading`
- **MOTOR**: `vehicle_age_bands`, `engine_cc_bands`, `ncb_discounts`, `zone_rates`
- **HOUSEHOLD**: `construction_type_rates`, `flood_zone_loading`

Validate:
```bash
cd backend && uv run python -m src.config.rule_loader policy_rules/<product_lower>/v<N>.json
# fallback if the CLI does not exist yet:
cd backend && uv run python -c "import json,jsonschema,sys;jsonschema.validate(json.load(open(sys.argv[1])),json.load(open('policy_rules/schema/rule-file.schema.json')))" policy_rules/<product_lower>/v<N>.json
```
Reject any JSON number (float literal) in money/rate fields: `grep -nE '": [0-9]+\.[0-9]+' policy_rules/<product_lower>/v<N>.json` must be empty.

## 2. Version monotonicity
- Files per product are `v1..vN` with **no gaps** and no duplicates.
- At most one `DRAFT`, and it must be the highest `N`.
- `effective_from` is non-decreasing across versions.
```bash
ls backend/policy_rules/<product_lower>/ | sed -E 's/v([0-9]+)\.json/\1/' | sort -n
```

## 3. PUBLISHED immutability vs git (NFR-02/05)
Diff base: `BASE=$(git merge-base HEAD origin/$CI_DEFAULT_BRANCH)` in CI, `BASE=$(git merge-base HEAD main)` locally.
For every file that is `PUBLISHED` at `BASE` or HEAD:
```bash
git diff --name-status HEAD -- backend/policy_rules/ | grep -E '^(M|D|R)'    # working tree; hit on a PUBLISHED file = FAIL
git diff --name-status $BASE -- backend/policy_rules/ | grep -E '^(M|D|R)'   # branch vs base
git show HEAD:backend/policy_rules/<product_lower>/v<N>.json | python -c "import json,sys;print(json.load(sys.stdin)['status'])"
(cd backend/policy_rules && sha256sum -c PUBLISHED.lock)                    # every lock line "<sha256>  <relative path>" verifies
L=backend/policy_rules/PUBLISHED.lock; diff <(git show $BASE:$L) <(head -n "$(git show $BASE:$L | wc -l)" $L)   # append-only: base lines are an unchanged prefix
```
Allowed changes: `A` (new file), or `M` on a file whose HEAD status is `DRAFT`. A `DRAFT→PUBLISHED`
flip is allowed only if the only changed key is `status`, and it must add exactly one new lock line.
The `policy-immutability-check.js` hook enforces the same rule at edit time; this is the batch check.

## 4. Reason-code integrity (AC-04)
- Every `underwriting.rules[*].reason_code` exists in `underwriting.reason_codes` of the **same file**.
- Every reason code referenced in code/tests exists in at least one PUBLISHED version:
```bash
comm -23 \
  <(grep -rhoE '\b(TL|MO|HH)-UW-[0-9]{3}\b' backend/src backend/tests frontend/src | sort -u) \
  <(cat backend/policy_rules/*/v*.json | grep -oE '\b(TL|MO|HH)-UW-[0-9]{3}\b' | sort -u)   # must be empty
```
- Reason codes are never removed in a newer version (retired codes stay with a `"retired": true` marker)
  so historical decisions remain explainable.
- Each product has ≥1 rule per decision outcome (AUTO_BIND, MANUAL_REVIEW, DECLINE).

## 5. Distinct rule sets (AC-02)
Three product folders exist, each with ≥1 PUBLISHED version, and `premium.base_rate` differs between products.

## Tests this skill expects (create failing ones if missing)
- `backend/tests/unit/test_rule_files_schema.py` — parametrized over every `v*.json`, `@pytest.mark.ac("AC-02")`.
- `backend/tests/unit/test_reason_codes.py` — `test_ac04_reason_codes_resolve`, `@pytest.mark.ac("AC-04")`.
- `backend/tests/architecture/test_rule_versions_immutable.py` — see `archtest-author`.

```bash
cd backend && uv run pytest tests/unit/test_rule_files_schema.py tests/unit/test_reason_codes.py tests/architecture -q
```

## Output
```
| product   | version | status    | schema | monotonic | immutable | reason codes |
|-----------|---------|-----------|--------|-----------|-----------|--------------|
| MOTOR     | v2      | PUBLISHED | PASS   | PASS      | PASS      | PASS (7)     |
VERDICT: PASS|FAIL
```
Append the table to `specs/reviews/policy-version-validation.md`. Exit with FAIL on any single violation.
