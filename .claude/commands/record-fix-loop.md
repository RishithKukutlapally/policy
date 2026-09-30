---
name: record-fix-loop
description: Capture an autonomous fix loop (detect → reproduce → fix → validate → PR) as docs/fix-loops/<date>-<slug>.md with commands, failing output, diff summary, passing output and branch/merge ref; feed failures.md / learned-rules.md.
argument-hint: "<short-slug>"
---

# /record-fix-loop — Fix Loop Evidence

Argument: `$ARGUMENTS` = kebab-case slug (e.g. `premium-rounding-motor`). Date = today (`YYYY-MM-DD`).
Output: `docs/fix-loops/<date>-<slug>.md`, in the single trace template rendered by `scripts/fix_loop_agent.py`
(`docs/conventions.md` → Git / CI). If that script ran the loop, the trace already exists — only verify and
complete it. Capture **real** command output — never paraphrase or invent it.

## Step 1: Detect
Identify the failure source (CI job, `/quote-check`, `/ac-coverage`, hook block, evaluator report).
Record: trigger, first failing command, timestamp, affected AC/NFR ids.

## Step 2: Reproduce (environment first)
```bash
git switch fix/<slug> 2>/dev/null || git switch -c fix/<slug>   # reuse the branch if the fix-loop script created it
uv --version && python --version && node --version        # rule out env drift first
cd backend && uv sync --frozen
cd backend && uv run pytest <failing node id> -q 2>&1 | tail -40
```
If it does not reproduce, record that and investigate env (lockfile, DB file, cached coverage) before code.
Add or confirm a **failing test** that pins the bug (tagged with its AC). Commit: `test: reproduce <slug>`.

## Step 3: Fix
Delegate the code change to the generator / owning domain agent. Production code is never hand-edited.
Commit: `fix(<scope>): <summary>`.

## Step 4: Validate
```bash
cd backend && uv run pytest <failing node id> -q
cd backend && uv run pytest -q --cov=src --cov-report=xml:coverage.xml
cd backend && uv run lint-imports
```
Capture `git diff --stat $(git merge-base HEAD main)` (CI: `origin/$CI_DEFAULT_BRANCH`) and a 5–10 line
summary of the semantic change.

## Step 5: PR / merge
Merge through `/sprint-close` or `git merge --no-ff fix/<slug>` with the intent block. Record branch name,
commit SHAs and merge SHA (`git log --merges -1 --format=%H`).

## Step 6: Write the document
Use exactly the `scripts/fix_loop_agent.py` template (one `2.N`/`3.N` pair per attempt; do not add sections —
root cause and prevention go in the attempt summary and in Step 7):
```markdown
# Fix loop — <slug>

- **Date:** <UTC ISO timestamp>
- **Status:** FIXED | ESCALATED
- **Branch:** `fix/<slug>`
- **Command:** `cd <workdir> && <test command>`

## 1. Detect
<fenced failing output, trimmed to the relevant ~40 lines; trigger and AC/NFR ids above the fence>

## 2.1 Reproduce + fix (attempt 1)
<reproduction command, root cause in one sentence, owning agent, commit sha(s)>

## 3.1 Validate — PASS | FAIL
<fenced validation output>

## 4. Change set
<fenced `git diff --stat` + the semantic summary>

## 5. PR
Merge with `/sprint-close` or `git merge --no-ff fix/<slug>`. Merge SHA: <sha>
```

## Step 7: Feed the ratchet
- Append a dated entry to `.claude/state/failures.md` (symptom, root cause, fix sha).
- If the mistake class could recur, append a rule to `.claude/state/learned-rules.md` (monotonic, never
  delete) and run `/knowledge-deposit "<summary>"`.
- Commit docs on the fix branch before merging: `docs(fix-loop): record <slug>`.
