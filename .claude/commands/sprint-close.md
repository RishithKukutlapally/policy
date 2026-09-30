---
name: sprint-close
description: Close a sprint group — full tests, coverage, lint-imports, /review (evaluator + security-reviewer) plus clean-code-reviewer spawned in parallel, require passing verdicts on the last line of all three reports, update progress state, then git merge --no-ff into main with an intent-block message.
argument-hint: "<group-id>"
---

# /sprint-close — Gate, Review, Merge

Argument: `$ARGUMENTS` = group id (e.g. `group-02`). Contract: `sprint-contracts/$ARGUMENTS.json`.
Stop at the first failing step and report it; never skip a gate.

## Step 1: Preconditions
```bash
test -f sprint-contracts/<group-id>.json
git rev-parse --abbrev-ref HEAD      # must be <type>/<desc>, not main
git status --porcelain               # must be empty
git fetch --all 2>/dev/null; git merge-base --is-ancestor main HEAD || echo "merge main first"
```
Contract must have `"approved": true`.

## Step 2: Full verification
```bash
cd backend && uv run ruff check . && uv run mypy src/
cd backend && uv run lint-imports
cd backend && uv run pytest -q --cov=src --cov-report=xml:coverage.xml --cov-report=term --cov-fail-under=80
cd backend && uv run pytest -m ac -q
cd frontend && npm run lint && npm run typecheck && npm test -- --run
cd e2e && npx playwright test
```
Then run `/ac-coverage` — every AC in this group's contract must be COVERED.

## Step 3: Review (three reviewers, in parallel)
The harness `/review` skill spawns only **evaluator** + **security-reviewer**, so this command spawns the third
reviewer itself. In **one** message, issue both:
1. `/review <group-id>` — evaluator → `specs/reviews/evaluator-report.md`; security-reviewer, told to write
   `specs/reviews/security-review-<group-id>.md`.
2. `Agent(subagent_type="clean-code-reviewer")` with scope `<group-id>` and the diff base
   `$(git merge-base HEAD main)` → `specs/reviews/clean-code-review-<group-id>.md`.
Wait for all three before Step 4.

## Step 4: Verdict gate (last line of each report)
Every verdict is the report's **last line** (`docs/conventions.md` → Reports).
```bash
tail -n 1 specs/reviews/evaluator-report.md                    | grep -qx 'VERDICT: PASS'
tail -n 1 specs/reviews/security-review-<group-id>.md          | grep -qE '^VERDICT: (CLEAR|WARN)$'
tail -n 1 specs/reviews/clean-code-review-<group-id>.md        | grep -qE '^VERDICT: (APPROVE|APPROVE_WITH_NITS)$'
```
Any missing report, a verdict that is not on the last line, `VERDICT: FAIL`, `BLOCK` or `CHANGES_REQUIRED`
stops the close: list the failed criteria / high findings, return to the generator loop, and stop.
Security findings rated HIGH/CRITICAL block the merge even under `WARN`.

## Step 5: Update state
- `features.json`: set every feature in this group to `"passes": true` (only those verified).
- `claude-progress.txt`: append a session block — date, `groups_completed`, `current_group: none`,
  coverage %, test counts, `next_action`.
- Commit on the branch: `chore(sprint): close <group-id>` including `coverage.xml`, reports, contract.

## Step 6: Merge (no fast-forward)
```bash
git checkout main
git merge --no-ff <branch> -m "<type>(<scope>): <group-id> <group name>" -m "Intent: <one line from contract>
Why: <business reason / AC ids>
Acceptance: <AC-NN list> verified; evaluator PASS, security <CLEAR|WARN>, clean-code <APPROVE*>; coverage <x>%
Out of scope: <deferred items>"
```
If the repo uses a remote PR flow, push the branch and open the MR instead, pasting the same intent block.

## Step 7: Post-merge
```bash
cd backend && uv run pytest -q          # main is green
git log --oneline --merges -3
```
Print: group, merge SHA, VERDICT, coverage, ACs closed, next group.
