---
name: ac-coverage
description: Build the AC-NN → test traceability matrix from specs and tagged tests; fail if any acceptance criterion has zero tests; writes specs/reviews/ac-coverage.md.
argument-hint: "[--strict]"
---

# /ac-coverage — Acceptance Criteria Traceability

`--strict` also fails when an AC has backend tests but no Playwright test for a UI-facing AC
(AC-01, AC-03, AC-05, AC-06, AC-09).

## Step 1: Collect ACs from specs
```bash
grep -noE '\bAC-[0-9]{2}\b' specs/*_spec.md | sort -u      # the glob already includes app_spec.md
```
Only count ids that appear inside a `## Acceptance Criteria` section (scan from that heading to the next
`## `). Build `AC → [spec_file:line]`. The expected set is at least AC-01..AC-10.

## Step 2: Collect tagged tests
Backend — the `@pytest.mark.ac("AC-NN")` marker is what counts (the `test_acNN_*` name is required but
secondary; see `docs/conventions.md` → Tests and traceability):
```bash
cd backend && uv run pytest --collect-only -q -m ac 2>/dev/null | grep '::'
grep -rnE '@pytest\.mark\.ac\("AC-[0-9]{2}"\)' backend/tests
grep -rnE 'def test_ac[0-9]{2}_' backend/tests
```
Playwright:
```bash
grep -rnE "test(\.only|\.skip)?\(\s*['\"\`]AC-[0-9]{2}" e2e/tests
```
Flag inconsistencies: `test_ac04_*` marked `AC-05`, marker without `test_acNN_` name, or `.skip` / `xfail`
(skipped tests do **not** count as coverage).

## Step 3: Optional pass/fail status
If `backend/coverage.xml` or a recent junit file exists, run:
```bash
cd backend && uv run pytest -m ac -q --junitxml=.ac.xml ; cd ../e2e && npx playwright test --reporter=json > .ac-e2e.json
```
and attach PASS/FAIL per test. Delete the temp files afterwards.

## Step 4: Print the matrix
```
| AC    | Spec                              | Unit | AC/API | E2E | Status  |
|-------|-----------------------------------|------|--------|-----|---------|
| AC-01 | quote-engine_spec.md:31           | 6    | 2      | 1   | COVERED |
| AC-09 | underwriting_spec.md:88           | 0    | 0      | 0   | MISSING |
Totals: 9/10 covered · 57 tagged tests · 1 inconsistency
```

## Step 5: Write the report
Write `specs/reviews/ac-coverage.md` — the single deterministic traceability report (the agent quality review
`specs/reviews/ac-audit.md` from `scripts/ac_audit_agent.py` is separate; there is no third report) — with: timestamp, git short SHA (`git rev-parse --short HEAD`),
the matrix, a per-AC list of test node ids, the inconsistency list, and a last line
`AC-COVERAGE: PASS` or `AC-COVERAGE: FAIL (<ids>)`.

## Step 6: Fail loudly
If any AC has zero counted tests (or `--strict` gaps), print
`FAIL: ACs with no tests: AC-09, ...` and recommend running the `spec-to-test-generator` skill for those ids.
Do not generate tests from this command.
