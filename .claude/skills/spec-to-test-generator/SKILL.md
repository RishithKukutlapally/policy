---
name: spec-to-test-generator
description: Parse AC-NN ids and Given-When-Then scenarios from specs/*_spec.md into failing, AC-tagged pytest and Playwright tests (red first), then hand traceability to /ac-coverage (specs/reviews/ac-coverage.md).
argument-hint: "[spec-file | AC-NN ...]"
context: fork
agent: test-engineer
---

# Spec-to-Test Generator

Turns acceptance criteria into executable, **initially failing** tests. Spec is truth: tests encode the
spec's wording, never the current implementation's behaviour.

## Inputs
- `$ARGUMENTS`: a spec path (`specs/underwriting_spec.md`), one or more `AC-NN` ids, or empty = all specs.
- Specs: `specs/app_spec.md`, `specs/{product-catalog,quote-engine,underwriting,policy-issuance,endorsement,renewal-cancellation}_spec.md`.

## Step 1 — Parse

Only read content under the `## Acceptance Criteria` heading of each spec (stop at the next `## `).
Expected shape:
```markdown
### AC-04 — Underwriting decision with reason codes
**Scenario: smoker over 55 is referred**
- **Given** a TERM_LIFE application with age 58 and smoker = true under rule version v1
- **When** underwriting runs
- **Then** the decision is MANUAL_REVIEW
- **And** reason code TL-UW-002 is returned
```
Extraction rules:
- AC id regex `\bAC-(\d{2})\b`; a scenario belongs to the nearest preceding AC heading.
- One scenario → one test. `And` lines attach to the previous Given/When/Then.
- Record `spec_file:line` for every scenario (cited in the test docstring).
- If an AC has no Given-When-Then, stop and report it — ask for the spec to be fixed; do not invent behaviour.

Quick inventory:
```bash
grep -nE '^#{2,4} .*AC-[0-9]{2}|\*\*(Given|When|Then|And)\*\*' specs/*_spec.md
```

## Step 2 — Choose the test layer

| Signal in the scenario | Layer | Location |
|------------------------|-------|----------|
| Pure calculation / rule / state (premium, reason code, transition) | unit | `backend/tests/unit/test_<feature>_*.py` |
| Endpoint, persistence, transaction, audit row | AC/API | `backend/tests/ac/test_acNN_<behaviour>.py` (FastAPI `TestClient`) |
| User sees / clicks / navigates | E2E | `e2e/tests/<feature>.spec.ts` |

Every AC gets ≥1 backend test; ACs with a user journey (AC-01, AC-03, AC-05, AC-06, AC-09) also get a Playwright test.

## Step 3 — Generate pytest (red)

```python
import pytest

@pytest.mark.ac("AC-04")
def test_ac04_smoker_over_55_is_referred(client, seed_term_life_v1) -> None:
    """AC-04: Underwriting decision with reason codes.

    specs/underwriting_spec.md:42 — Scenario: smoker over 55 is referred.
    """
    # Given
    app_id = submit_application(client, product="TERM_LIFE", age=58, smoker=True)
    # When
    resp = client.post(f"/api/underwriting/{app_id}/decide")
    # Then
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "MANUAL_REVIEW"
    assert "TL-UW-002" in body["reason_codes"]
```
Conventions:
- Name `test_acNN_<snake_case_behaviour>` **and** marker `@pytest.mark.ac("AC-NN")` — the marker is what `/ac-coverage`
  counts (registered in `backend/pyproject.toml` `[tool.pytest.ini_options] markers`).
- Docstring: first line `AC-NN: <criterion>` (per `backend/tests/CLAUDE.md`), then `spec_file:line` and scenario title.
- Given/When/Then comments mirror the spec.
- Money assertions compare `Decimal("…")`; never `pytest.approx` on money.
- Synthetic data only, in the formats of `docs/conventions.md` (PAN `AAAAA0001A`, Aadhaar `999900000001`,
  masked `XXXX-XXXX-0001`, names like `Test Customer 01`).
- Do **not** write production code, stubs that make the test pass, or `xfail`/`skip`.

## Step 4 — Generate Playwright (red)

```ts
test('AC-04 underwriting status shows MANUAL_REVIEW with TL-UW-002 @ac', async ({ page }) => {
  // Given
  await page.goto('/apply/term-life');
  await page.getByLabel('Age').fill('58');
  await page.getByLabel('Smoker').check();
  // When
  await page.getByRole('button', { name: 'Submit application' }).click();
  // Then
  await expect(page.getByText('MANUAL_REVIEW')).toBeVisible();
  await expect(page.getByText('TL-UW-002')).toBeVisible();
});
```
`AC-NN` must be the first token of the test title; use `getByRole/getByLabel/getByText` only; no `waitForTimeout`.

## Step 5 — Prove red
```bash
cd backend && uv run pytest -m ac -k "ac04" -q          # expect failures (not collection errors)
cd e2e && npx playwright test -g "AC-04" --reporter=line  # expect failures
```
A test that errors on import/collection is not "red" — fix fixtures/imports until it fails on an assertion.
A test that passes immediately means the behaviour already exists or the assertion is weak — tighten it.
Commit red tests alone: `test: add failing AC-04 tests from underwriting spec`.

## Step 6 — Hand off to /ac-coverage

Do **not** write a separate traceability file. Run `/ac-coverage` — the single deterministic report
(`specs/reviews/ac-coverage.md`, counted by `@pytest.mark.ac` marker and Playwright `AC-NN` titles). Every
generated test must appear there against its AC; if one is missing, its tag or title is wrong — fix the test.
In the hand-off message list `AC → spec_file:line → test node id → layer → RED` for the new tests only.

## Checklist
- [ ] Every scenario under `## Acceptance Criteria` has exactly one generated test per chosen layer
- [ ] All pytest tests named `test_acNN_*` and marked `@pytest.mark.ac("AC-NN")`
- [ ] All Playwright titles start with `AC-NN`
- [ ] Tests fail on assertions, not on imports
- [ ] `/ac-coverage` run; every new test counted against its AC; docstrings cite spec lines
