# backend/src/domain/ — business rules (pure)

The rubric's "rule / policy / validator files under src/domain/" live here (≥4 required).

## Planned modules

| File | Owns | AC / NFR |
|------|------|----------|
| `premium_calculator.py` | Deterministic premium from a rule set + insured profile | AC-01, AC-02, NFR-01 |
| `application_validator.py` | KYC stub + risk-input validation against product rules | AC-03 |
| `underwriting_rules.py` | AUTO_BIND / MANUAL_REVIEW / DECLINE + reason codes | AC-04 |
| `policy_state_machine.py` | Allowed lifecycle transitions, raises `InvalidPolicyStateException` | AC-10 |
| `endorsement_rules.py` | Endorsement types, eligibility, premium delta | AC-06 |
| `renewal_rules.py` | Renewal term, refreshed premium, grace-period lapse | AC-07 |
| `refund_rules.py` | Pro-rated cancellation refund per product | AC-08 |

## Rules

- **Pure functions / frozen dataclasses only.** No FastAPI, SQLAlchemy, HTTP, file or clock access —
  inject `today: date` and the parsed rule set as arguments. (Enforced by import-linter + arch tests.)
- Imports allowed: `src.types` and the standard library only.
- Money: `Decimal` from strings, one `quantize(Decimal("0.01"), ROUND_HALF_UP)` at the end of a computation.
- Reason codes are read from the rule set (`underwriting.reason_codes`), never hard-coded.
- Every public function has a unit test in `backend/tests/unit/` and its AC-tagged test in `backend/tests/ac/`.
- Skills: `premium-calc-evaluator`, `policy-state-machine-generator`, `endorsement-validator`.
