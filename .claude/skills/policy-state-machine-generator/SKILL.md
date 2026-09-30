---
name: policy-state-machine-generator
description: Generate the policy lifecycle transition table in backend/src/domain/policy_state_machine.py plus exhaustive parametrized tests for every valid and invalid state pair (AC-10, NFR-02 append-only transition log).
argument-hint: "[--tests-only]"
---

# Policy State Machine Generator

Produces a single, data-driven source of truth for policy status transitions and proves it with an
exhaustive N×N test matrix. Follow TDD: generate the tests (red), then the table (green).

## Spec source

Read `specs/policy-issuance_spec.md`, `specs/endorsement_spec.md`, `specs/renewal-cancellation_spec.md`
(AC-05, AC-06, AC-07, AC-08, AC-10). If the spec and this skill disagree, **the spec wins** — update the
table below in the spec first, then regenerate.

## Canonical states and transitions

States (`PolicyStatus` in `backend/src/types/enums.py`, `StrEnum`): `ACTIVE, ENDORSED, LAPSED, CANCELLED, RENEWED`
(canonical lifecycle in `docs/conventions.md`).

| From \ To  | ACTIVE | ENDORSED | LAPSED | CANCELLED | RENEWED |
|------------|--------|----------|--------|-----------|---------|
| ACTIVE     | –      | ✔        | ✔      | ✔         | ✔       |
| ENDORSED   | –      | ✔ (further endorsement) | ✔ | ✔     | ✔       |
| LAPSED     | –      | –        | –      | –         | –       |
| CANCELLED  | –      | –        | –      | –         | –       |
| RENEWED    | –      | –        | –      | –         | –       |

`LAPSED`, `CANCELLED`, `RENEWED` are terminal for that policy term (renewal creates a **new** term record
that starts `ACTIVE`). Adjust only if the spec says otherwise (e.g. reinstatement).

## Step 1 — Tests first (`backend/tests/unit/test_policy_state_machine.py`)

```python
ALL = list(PolicyStatus)
VALID = {(PolicyStatus.ACTIVE, PolicyStatus.ENDORSED), ...}  # copied from the spec table, NOT imported
INVALID = [(a, b) for a in ALL for b in ALL if (a, b) not in VALID]

@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(("src", "dst"), sorted(VALID), ids=lambda s: s.value)
def test_ac10_valid_transition_allowed(src: PolicyStatus, dst: PolicyStatus) -> None:
    assert transition(src, dst) is dst

@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(("src", "dst"), INVALID, ids=lambda s: s.value)
def test_ac10_invalid_transition_raises(src: PolicyStatus, dst: PolicyStatus) -> None:
    with pytest.raises(InvalidPolicyStateException) as exc:
        transition(src, dst)
    assert src.value in str(exc.value) and dst.value in str(exc.value)

@pytest.mark.ac("AC-10")
def test_ac10_matrix_is_exhaustive() -> None:
    assert len(VALID) + len(INVALID) == len(ALL) ** 2
```

The expected `VALID` set is written out literally in the test — importing it from production code makes
the test tautological. Also add:
- `test_ac10_terminal_states_have_no_exits` — for each terminal state, `allowed_targets(s) == frozenset()`.
- `test_ac10_transition_table_is_immutable` — `TRANSITIONS` is a `Mapping[PolicyStatus, frozenset[...]]`
  wrapped in `MappingProxyType`; item assignment raises `TypeError`.

Run and confirm **red**: `cd backend && uv run pytest tests/unit/test_policy_state_machine.py -q`

## Step 2 — Domain module (`backend/src/domain/policy_state_machine.py`)

Rules: pure domain, imports only `src.types`; no I/O, no logging, no DB; < 80 lines.

```python
TRANSITIONS: Final[Mapping[PolicyStatus, frozenset[PolicyStatus]]] = MappingProxyType({
    PolicyStatus.ACTIVE: frozenset({ENDORSED, LAPSED, CANCELLED, RENEWED}),
    PolicyStatus.ENDORSED: frozenset({ENDORSED, LAPSED, CANCELLED, RENEWED}),
    PolicyStatus.LAPSED: frozenset(), PolicyStatus.CANCELLED: frozenset(), PolicyStatus.RENEWED: frozenset(),
})

def allowed_targets(src: PolicyStatus) -> frozenset[PolicyStatus]: ...
def transition(src: PolicyStatus, dst: PolicyStatus) -> PolicyStatus:
    if dst not in TRANSITIONS[src]:
        raise InvalidPolicyStateException(src, dst)
    return dst
```
`InvalidPolicyStateException` lives in `backend/src/types/errors.py` (`src.types.errors`), carries `from_status`,
`to_status`, and maps to HTTP 409 in `backend/src/api/` error handlers.

## Step 3 — Append-only transition log (NFR-02)

- Model `PolicyStateTransition` → table `policy_state_transitions` (`id, policy_id, from_status, to_status, reason,
  actor_id, occurred_at`) in `backend/src/repository/models.py`.
- `PolicyStateTransitionRepository` exposes **only** `add(...)` and `list_for_policy(...)` — no `update`, `delete`, `merge`.
- Service writes the new policy status and the transition row in **one** transaction.
- Tests:
  - `test_ac10_transition_is_logged` (integration) — after `cancel`, one row ACTIVE→CANCELLED exists.
  - `test_ac10_rejected_transition_not_logged` — invalid attempt leaves the log unchanged.
  - Architecture: repository class has no method named `update*|delete*|remove*` (see `archtest-author`).

## Step 4 — API/E2E coverage

- `backend/tests/ac/test_ac10_api.py`: `POST /api/policies/{policy_number}/cancel` on a CANCELLED policy → `409` with
  `{"error": "INVALID_POLICY_STATE", "from": "CANCELLED", "to": "CANCELLED"}`.
- Playwright (`e2e/tests/policy-lifecycle.spec.ts`): title contains `AC-10`, asserts the cancel button is
  disabled / error toast shown for a lapsed policy.

## Step 5 — Verify
```bash
cd backend && uv run pytest tests/unit/test_policy_state_machine.py -q     # 25 parametrized + extras
cd backend && uv run pytest -m ac -k ac10 -q
cd backend && uv run mypy src/domain/policy_state_machine.py && uv run lint-imports
```

## Checklist
- [ ] 5×5 = 25 pairs covered (valid + invalid) and exhaustiveness test present
- [ ] Expected table hard-coded in tests, not imported
- [ ] Table immutable (`MappingProxyType` + `frozenset`)
- [ ] Exception message names both states; API maps to 409
- [ ] Transition log append-only, written atomically with status change
- [ ] All tests tagged `@pytest.mark.ac("AC-10")`, names start `test_ac10_`
