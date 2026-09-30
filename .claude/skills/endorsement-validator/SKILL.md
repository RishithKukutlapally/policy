---
name: endorsement-validator
description: Validate endorsement rules (CHANGE_ADDRESS, ADD_NOMINEE, CHANGE_SUM_INSURED), premium-delta recomputation, record immutability and single-transaction atomicity, and the ENDORSED state change (AC-06, NFR-01, NFR-02).
argument-hint: "[--fix-tests]"
---

# Endorsement Validator

Audits the endorsement feature end-to-end and fills gaps with failing tests. It never edits
production code directly; defects go to the generator (or `endorsement-agent`) via `/record-fix-loop`.

## Sources of truth
- Spec: `specs/endorsement_spec.md` (AC-06) + `specs/app_spec.md`; names/paths: `docs/conventions.md`
- Domain rules: `backend/src/domain/endorsement_rules.py`
- Service: `backend/src/service/endorsement_service.py`; route `backend/src/api/routers/endorsements.py`
- Repository: `backend/src/repository/endorsement_repository.py`
- Tests: `backend/tests/unit/test_endorsement_rules.py`, `backend/tests/ac/test_ac06_*.py`, `backend/tests/integration/test_endorsement_atomicity.py`

## 1. Type rules matrix

| Type | Required payload | Validation | Premium effect | Policy attributes updated |
|------|------------------|------------|----------------|---------------------------|
| `CHANGE_ADDRESS` | `address{line1,city,pincode}` | pincode 6 digits; not identical to current | none (`delta = Decimal("0.00")`) | `address` |
| `ADD_NOMINEE` | `nominee{name,relationship,share_pct}` | shares sum ≤ 100 (Decimal); relationship in allowed list; TERM_LIFE only unless spec says otherwise | none | `nominees` (append) |
| `CHANGE_SUM_INSURED` | `new_sum_insured: Decimal` | within product min/max from active rule file; ≠ current | recompute via quote engine | `sum_insured`, `premium` |

Common rules: type ∈ the rule file's `endorsement.allowed_types`; sum-insured bounds are
`eligibility.min_sum_insured` / `eligibility.max_sum_insured`; policy status ∈ {`ACTIVE`, `ENDORSED`} else
`InvalidPolicyStateException` (`src/types/errors.py`); `effective_date` within the current term; unknown type → 422.

## 2. Premium delta recompute (CHANGE_SUM_INSURED)

```
new_annual = quote_engine.calculate(profile_with_new_SI, rules=policy.rule_version)   # same version as issued
delta      = (new_annual - old_annual) * remaining_days / term_days
delta      = delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)                    # final step only
```
Checks:
- Uses the policy's **issued** `rule_version`, not the latest published one.
- All operands `Decimal`; `remaining_days / term_days` computed as `Decimal(remaining) / Decimal(term)`.
- Negative delta allowed (SI decrease) and stored signed.
- Golden tests: increase, decrease, mid-term, last-day-of-term, `.xx5` boundary.

## 3. Immutability (NFR-02)

```bash
cd backend && grep -nE "def (update|delete|remove|save|merge)" src/repository/endorsement_repository.py
cd backend && grep -rnE "session\.(delete|merge)\(|\.update\(" src/repository/endorsement_repository.py
```
Both must return nothing. Required tests:
- `test_ac06_endorsement_record_has_no_mutators` — repository public API is exactly `{add, get, list_for_policy}`.
- `test_ac06_endorsement_row_update_rejected` — ORM `before_update`/`before_delete` listener (or DB trigger in
  migration) raises on any attempt to modify an `endorsements` row.
- Endorsement is linked by `policy_id` FK and carries `sequence_no` (monotonic per policy), `actor_id`, `created_at`.

## 4. Atomicity (single transaction)

The service must, inside **one** `with session.begin():` block:
1. load policy `FOR UPDATE` (or version check),
2. validate via domain rules,
3. `add` the `Endorsement` row (`endorsements`),
4. update policy attributes (+ premium),
5. transition status → `ENDORSED` and `add` the `PolicyStateTransition` row (`policy_state_transitions`),
6. `add` the `AuditRecord` row (`audit_records`) with `actor_id`.

Test by fault injection:
```python
@pytest.mark.ac("AC-06")
def test_ac06_endorsement_rolls_back_on_failure(session, policy, monkeypatch) -> None:
    monkeypatch.setattr(PolicyStateTransitionRepository, "add", _boom)
    with pytest.raises(RuntimeError):
        service.endorse(policy.id, change_sum_insured(Decimal("1500000")), actor_id="u-1")
    refreshed = repo.get(policy.id)
    assert refreshed.sum_insured == policy.sum_insured and refreshed.status is PolicyStatus.ACTIVE
    assert endorsement_repo.list_for_policy(policy.id) == []
```
Also check no `session.commit()` calls appear inside helpers called from `endorse` (`grep -n "commit()" src/service/endorsement_service.py` → only at the unit-of-work boundary).

## 5. State
- After success: `policy.status is PolicyStatus.ENDORSED`; second endorsement keeps `ENDORSED` (allowed self-transition).
- Endorsing a `LAPSED`/`CANCELLED`/`RENEWED` policy → 409 `INVALID_POLICY_STATE` (cross-check with `policy-state-machine-generator`).

## 6. PII
`ADD_NOMINEE` payload may include PAN/Aadhaar stubs (synthetic formats in `docs/conventions.md`: PAN `AAAAA0001A`,
Aadhaar `999900000001`; only the masked form `XXXX-XXXX-0001` may be logged): assert log output contains neither
(`caplog` + regex `\b[A-Z]{5}[0-9]{4}[A-Z]\b` and `\b\d{4}\s?\d{4}\s?\d{4}\b`).

## Run
```bash
cd backend && uv run pytest -m ac -k ac06 -q
cd backend && uv run pytest tests/unit/test_endorsement_rules.py tests/integration/test_endorsement_atomicity.py -q
```

## Output
Write `specs/reviews/endorsement-validation.md` with a table `check → status → evidence (test id / file:line)` and a final `VERDICT: PASS|FAIL`.

## Checklist
- [ ] 3 types each have happy-path + ≥1 rejection test tagged AC-06
- [ ] Delta uses issued rule version, Decimal-only, single final quantize
- [ ] Repository has no mutators; DB/ORM blocks updates
- [ ] Fault-injection rollback test passes
- [ ] Status ENDORSED + transition + audit rows written in the same transaction
- [ ] No PII in logs
