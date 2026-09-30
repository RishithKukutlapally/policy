---
name: quote-check
description: Run premium golden cases for a product (and optional rule version) and verify Decimal math with the premium-calc-evaluator skill; prints case → expected → actual.
argument-hint: "<TERM_LIFE|MOTOR|HOUSEHOLD|all> [version]"
---

# /quote-check — Premium Golden-Case Check

Arguments: `$ARGUMENTS` → `<PRODUCT> [version]`. Product codes are uppercase; rule folders are the lowercase
code (`TERM_LIFE` → `backend/policy_rules/term_life/`), per `docs/conventions.md`.

## Step 1: Parse and resolve
1. Split `$ARGUMENTS`. `product` is required and must be `TERM_LIFE`, `MOTOR`, `HOUSEHOLD` or `all`;
   otherwise stop and print the usage line.
2. If `version` is omitted, pick the highest `v<N>.json` in `backend/policy_rules/<product_lower>/` whose
   `"status"` is `PUBLISHED`. Print `Checking <product> v<N> (<status>)`.
3. Map product → test file: `TERM_LIFE → test_premium_golden_term_life.py`,
   `MOTOR → test_premium_golden_motor.py`, `HOUSEHOLD → test_premium_golden_household.py`.
   If the file is missing, stop: "No golden tests for <product> — ask `quote-engine-agent` to add golden cases
   (red first, per the `premium-calc-evaluator` skill)."

## Step 2: Run the golden tests
```bash
cd backend && uv run pytest tests/unit/test_premium_golden_<product_lower>.py -q -rA -k "_v<N>_" --junitxml=.quote-check.xml
```
(`-k "_v<N>_"` only when a version was given; the delimiters stop `_v1_` matching v10–v19, so golden test
names embed the version as `_v<N>_`, e.g. `test_ac01_term_life_v1_half_up_boundary`.) Parse `.quote-check.xml` for per-case pass/fail and failure
messages (`expected Decimal('…') got Decimal('…')`), then delete it.

## Step 3: Run the evaluator skill
Invoke the `premium-calc-evaluator` skill with `<product> [version]`. It adds:
- Decimal-only static scan (NFR-01), `.xx5` half-up boundary coverage, determinism (3 runs),
- AC-01 / AC-02 tag check.

## Step 4: Print the result table
```
/quote-check MOTOR v2
| case_id          | expected | actual   | type    | result |
|------------------|----------|----------|---------|--------|
| mo-v2-basic      | 8420.00  | 8420.00  | Decimal | PASS   |
| mo-v2-half-up    | 1234.57  | 1234.56  | Decimal | FAIL   |
Boundary cases: 2/2 present | Float usages: 0 | Determinism: 3/3
VERDICT: FAIL (1 case)
```
For `all`, print one table per product then a one-line summary per product.

## Step 5: On failure
- Do **not** edit production code or golden values from this command.
- Show the failing case's rule-file inputs and the evaluator's diagnosis (e.g. intermediate rounding,
  `ROUND_HALF_EVEN`, float parse).
- Suggest: `/record-fix-loop premium-rounding-<product_lower>` to drive the fix through a branch + PR.

Exit status: PASS only if every case passes and the evaluator verdict is PASS.
