---
name: publish-policy-version
description: Create the next rule-set version for a product as DRAFT (copy of the latest), validate it with policy-version-validator, and flip it to PUBLISHED only after explicit approval. Never edits a PUBLISHED file.
argument-hint: "<TERM_LIFE|MOTOR|HOUSEHOLD>"
---

# /publish-policy-version — New Rule-Set Version

Argument: `$ARGUMENTS` = product code. Reject anything other than `TERM_LIFE`, `MOTOR`, `HOUSEHOLD`.
The rule folder is the lowercase code: `backend/policy_rules/<product_lower>/` (`term_life`, `motor`, `household`);
file shape and lock format per `docs/conventions.md`.

## Hard rule
A file whose status at `git HEAD` is `PUBLISHED` is **never** opened for writing. Changes always go into a
new `v<N+1>.json`. The `policy-immutability-check` hook will block violations; do not try to bypass it.

## Step 1: Preconditions
```bash
git status --porcelain backend/policy_rules/      # must be empty
git rev-parse --abbrev-ref HEAD                    # must not be main
```
If on `main`, create a branch: `git checkout -b feat/policy-<product_lower>-v<N+1>`.

## Step 2: Find the latest version
List `backend/policy_rules/<product_lower>/v*.json`, sort numerically, take `N` = highest.
- If `vN` is already `DRAFT`, do not create another — continue editing `vN` (go to Step 4).
- Otherwise `vN` must be `PUBLISHED`; continue.

## Step 3: Create the DRAFT
Copy `vN.json` → `v<N+1>.json` and set only:
`"version": N+1`, `"status": "DRAFT"`, `"effective_from": "<proposed date>"`
(ask the user for the date; must be ≥ vN's `effective_from`).

## Step 4: Apply the requested rule changes
Ask the user what changes (`premium.*` rates/factors, `eligibility`, `underwriting.rules` /
`underwriting.reason_codes`, `endorsement.allowed_types`, `renewal.*`, `cancellation.*`).
Apply them to `v<N+1>.json` only. Rules:
- Money/rate values stay **decimal strings** (`"0.0135"`), never JSON floats.
- Reason codes may be added or marked `"retired": true`; never deleted or renumbered.
- Show a semantic diff: `git diff --no-index backend/policy_rules/<product_lower>/vN.json backend/policy_rules/<product_lower>/v<N+1>.json`.

## Step 5: Validate
Invoke the `policy-version-validator` skill for `<PRODUCT>`, then:
```bash
cd backend && uv run pytest tests/unit/test_rule_files_schema.py tests/unit/test_reason_codes.py tests/architecture -q
cd backend && uv run pytest tests/unit/test_premium_golden_<product_lower>.py -q
```
Golden tests for the new version (names embed `_v<N+1>_`) must exist; if absent, ask `quote-engine-agent` to add
golden cases (red) and stop here — the draft is committed as DRAFT.

## Step 6: Approval gate
Print the validator table and the diff summary, then ask: **"Publish <PRODUCT> v<N+1>? (yes/no)"**.
Anything but an explicit `yes` → commit as DRAFT (`feat(rules): draft <PRODUCT> v<N+1>`) and stop.

## Step 7: Publish
Change only `"status": "PUBLISHED"` in `v<N+1>.json`. Append one ledger line `<sha256>  <relative path>`
(two spaces; path relative to `backend/policy_rules/`) to `PUBLISHED.lock`:
`(cd backend/policy_rules && sha256sum <product_lower>/v<N+1>.json >> PUBLISHED.lock)`.
The lock is append-only — never edit, reorder or remove existing lines (hook `policy-immutability-check`). Re-run Step 5, then commit:
```
feat(rules): publish <PRODUCT> v<N+1>

Intent: publish <PRODUCT> rule set v<N+1>
Why: <user-supplied reason>
Acceptance: policy-version-validator PASS; golden tests PASS (AC-01, AC-02, AC-04)
Out of scope: changes to v1..vN (immutable)
```
Merge via PR / `/sprint-close` — never directly to `main`.
