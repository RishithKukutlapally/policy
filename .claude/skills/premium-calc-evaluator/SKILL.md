---
name: premium-calc-evaluator
description: Verify premium math against golden cases per product and rule-file version — Decimal-only arithmetic, ROUND_HALF_UP boundaries (x.xx5), and determinism (AC-01, AC-02, NFR-01).
argument-hint: "<TERM_LIFE|MOTOR|HOUSEHOLD|all> [version]"
context: fork
agent: quote-engine-agent
---

# Premium Calc Evaluator

Proves that the quote engine returns the **same, correctly rounded, Decimal-typed** premium for a
given product + insured profile, sourced from `backend/policy_rules/<product_lower>/v<N>.json` (folders
`term_life/`, `motor/`, `household/`; shape and names in `docs/conventions.md`).
Read-only on production code: if a check fails, report it and hand off to the generator / `/record-fix-loop`.

## Inputs

- `$ARGUMENTS` → `<PRODUCT> [version]` (product code `TERM_LIFE|MOTOR|HOUSEHOLD`; folder = lowercase code).
  `all` = every product. No version = latest `PUBLISHED` file.
- Golden tests: `backend/tests/unit/test_premium_golden_<product_lower>.py` (e.g. `test_premium_golden_term_life.py`).
- Golden data (if split out): `backend/tests/unit/golden/<product_lower>_v<N>.json`.

## Procedure

### 1. Resolve the rule file
```bash
ls backend/policy_rules/<product_lower>/       # pick highest v<N> with "status": "PUBLISHED"
python -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['product'],d['version'],d['status'])" backend/policy_rules/<product_lower>/v<N>.json
```
A golden case must pin `product` **and** `version`. Cases without a version are a defect.

### 2. Run the golden suite
```bash
cd backend && uv run pytest tests/unit -k "premium_golden and <product_lower>" -q -rA
cd backend && uv run pytest -m ac -k "ac01 or ac02" -q
```
Collect for every case: `case_id → expected → actual → PASS/FAIL`.

### 3. Decimal-only static checks (NFR-01)
```bash
cd backend && grep -rnE "float\(|: float|-> float|\b[0-9]+\.[0-9]+\b\s*[*/+-]" src/domain src/service | grep -iE "premium|rate|loading|sum_insured|refund"
cd backend && grep -rn "Decimal(" src/domain | grep -vE "Decimal\(\"|Decimal\('|Decimal\(str\("
```
- Every literal must be `Decimal("0.05")` — never `Decimal(0.05)` (float constructor leaks binary error).
- Rule-file numbers are JSON strings (`premium.base_rate`, `premium.minimum_premium`, `premium.factors`) and are
  loaded only by `src/config/rule_loader.py` (strings → `Decimal`, `parse_float=Decimal` as a backstop).
- Quantize exactly once, at the final step: `amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
  Intermediate quantization (e.g. rounding the base rate before loadings) is a FAIL.

### 4. Rounding boundary cases (x.xx5)
Each product's golden file must include at least these cases; add missing ones as **failing tests first**:

| Case | Raw (unrounded) | Expected | Why |
|------|-----------------|----------|-----|
| half-up-boundary | `1234.565` | `1234.57` | banker's rounding would give `1234.56` |
| below-boundary | `1234.5649999` | `1234.56` | no double rounding |
| exact | `1000.000` | `1000.00` | scale is always 2 |
| tiny | `0.005` | `0.01` | min premium path |
| large SI | `50000000 × 0.00123` | `61500.00` | no overflow / precision loss |

Construct inputs whose un-rounded premium lands on `.xx5` by back-solving from the rule rates.

### 5. Determinism
```bash
cd backend && for i in 1 2 3; do uv run pytest tests/unit -k premium_golden -q -p no:cacheprovider || exit 1; done
```
Plus an in-test assertion: calling `calculate_premium(profile, rules)` 100× yields one distinct value,
and the result does not depend on dict ordering, wall-clock time, or env vars.

### 6. Type assertions every golden test must contain
```python
@pytest.mark.ac("AC-01")
def test_ac01_term_life_v1_half_up_boundary() -> None:
    result = calculate_premium(profile, load_rule_set(ProductCode.TERM_LIFE, 1))  # src.config.rule_loader
    assert isinstance(result.premium, Decimal)
    assert result.premium == Decimal("1234.57")
    assert result.premium.as_tuple().exponent == -2
    assert result.rule_version == 1
```

### 7. Distinct rule sets (AC-02)
For the same canonical profile, the three products must produce three different premiums and cite
three different `rule_version` / `product` values. One parametrized test covers this.

## Output

Print, and append to `specs/reviews/premium-calc-report.md`:

```
Product: MOTOR  Version: v2 (PUBLISHED)
| case_id              | expected  | actual    | type    | result |
|----------------------|-----------|-----------|---------|--------|
| mo-v2-basic          | 8420.00   | 8420.00   | Decimal | PASS   |
| mo-v2-half-up        | 1234.57   | 1234.56   | Decimal | FAIL   |
Static: float usages 0 | Decimal(float) 0 | intermediate quantize 0
Determinism: 3/3 identical
VERDICT: PASS|FAIL
```

## Checklist
- [ ] Every golden case pins product + version and is tagged `@pytest.mark.ac("AC-01")`
- [ ] ≥1 `.xx5` half-up boundary case per product
- [ ] No `float` in premium path; no `Decimal(<float>)`
- [ ] Single final quantize with `ROUND_HALF_UP`
- [ ] 3 products → 3 distinct premiums (AC-02)
- [ ] Repeated runs identical

## Gotchas
- `round()` on a Decimal uses ROUND_HALF_EVEN — banned for money.
- `json.load` without `parse_float=Decimal` turns `0.0125` into a float silently.
- Pydantic `float` fields in request schemas re-introduce floats at the API boundary; use `condecimal`/`Decimal`.
