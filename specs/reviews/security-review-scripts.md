# Security Review — PolicyForge scripts (fix loop + AC audit) — 2026-09-29

Scope: `scripts/fix_loop_guard.py`, `scripts/fix_loop_trace.py`, `scripts/fix_loop_agent.py`,
`scripts/ac_audit_agent.py`. This is round 3 of `security-review-substrate.md` (R2-H1 and H1 residue).

## Summary
- BLOCK findings: 0
- WARN findings: 2
- INFO findings: 3
- Overall verdict: WARN

## Fix verification

| Item | Status | Evidence |
|---|---|---|
| R2-H1: clean-tree precondition | Fixed | `fix_loop_agent.py:162` refuses to start on a dirty tree, so every change since base belongs to the agent |
| Base-relative tamper check, agent commits undone | Fixed | `fix_loop_guard.py:140-157` resets to base when HEAD moves, then diffs worktree against base and adds untracked files |
| Inherited allow-list (DEC-005) | Fixed | `fix_loop_guard.py:60-78` denies every mutating or escaping entry in `.claude/settings.json` (git checkout/commit/push/merge/branch, docker, gh, curl, find, npm/npx). The remaining inherited entries (pytest, ruff, mypy, git log, mkdir, grep, wc) are read-only or equivalent to entries already allowed |
| strict_mcp_config | Fixed | `fix_loop_agent.py:84`, `ac_audit_agent.py:120` |
| Protected test config and co-located tests | Partial | See SCR-001 |
| Escalated run discards code, commits only the trace | Partial | `fix_loop_agent.py:176-177`, `134-137`. See SCR-002 |
| `--test-cmd` with shell=True | Accepted as Low | Operator-supplied, never taken from agent output (`fix_loop_agent.py:51`) |

## WARN Findings

### [SCR-001] The test-config protection can still be bypassed, so tests can be weakened without being detected
File: scripts/fix_loop_guard.py lines 44-58, 113-122, 133-137
Severity: WARN
Description: There is no `pyproject.toml` anywhere in the repo yet, and only `backend/pyproject.toml` is protected. pytest searches upward from `backend/` for config. The agent can use its Write tool to create either of these, and neither is protected:
- a repo-root `pyproject.toml`
- `backend/.pytest.ini` (pytest's hidden ini variant, which takes precedence over `pyproject.toml`)

Either file can add options that deselect or skip the failing tests. The tamper check does not flag the file, the validation run passes, and `commit_trace` commits it as a `fix:`.

A second route: `.gitignore` files (root or nested) are not protected. `changed_since` uses `--exclude-standard`, so the agent can add an ignore pattern and then create an ignored file. For example, an ignored `conftest.py` affects the validation run but is invisible to the tamper check and is never committed. The loop then reports FIXED for a change that the committed code does not reproduce.

Fix:
- Protect `pyproject.toml`, `.pytest.ini`, `pytest.toml` and `.pytest.toml` by name at any depth. Also protect `.gitignore` by name, and `vitest.config.*`, `vite.config.*` and `vitest.workspace.*` with any extension.
- In `changed_since`, also list ignored files: take `git ls-files --others --ignored --exclude-standard` before and after each attempt and compare the two snapshots, excluding known caches such as `.venv` and `__pycache__`.

### [SCR-002] Staged new files survive both the tamper check and the escalation discard
File: scripts/fix_loop_guard.py lines 147-164; scripts/fix_loop_agent.py line 141
Severity: WARN
Description: The Bash deny list stops the agent from running `git add` directly. But pytest executes code the agent wrote, so that code can stage files. The index is reset only when HEAD has moved.

For a staged new protected file, `revert_protected` deletes only the worktree copy. The staged blob stays in the index, and on later attempts the file no longer shows in the worktree diff at all. `discard_changes` has the same gap: `git checkout base -- .` leaves staged new paths alone, and `ls-files --others` does not list them.

`commit_trace` runs a plain `git commit`, which commits the whole index. That includes a staged `conftest.py`, a staged `.github/workflows/*` file, or unfixed code on an escalated run.

The same route through tests can also plant `.git/hooks/*` or change `core.hooksPath`. `commit_trace`'s commit would then run that hook after the tamper check.

Fix:
- Reset the index to base on every attempt (`git reset -q base`), whether or not HEAD moved. In `discard_changes`, use `git reset --hard base` plus a clean of untracked files.
- In `commit_trace`, commit with an explicit pathspec (the trace plus the allowed paths), or reset the index before `git add`. Pass `-c core.hooksPath=` pointing to an empty directory for that commit.

## INFO Findings

### [SCR-003] The detection test run happens before the base is recorded
File: scripts/fix_loop_agent.py lines 116-122
Severity: INFO
Description: Any non-ignored artifacts created by the detection run are treated as agent changes. On an escalated run they are deleted. This is harmless, but record the base right after the clean-tree check.

### [SCR-004] Agent-authored code runs with the operator's privileges
File: scripts/fix_loop_guard.py lines 24-27
Severity: INFO
Description: `uv run pytest` executes production code that the agent wrote. That code can reach anything the operator's shell can, including `.venv` and `.git`, which the tamper check does not cover. This is an inherent limit of a post-hoc check. Run the loop in a disposable container or worktree, and run validation in a fresh environment.

### [SCR-005] AC audit agent is correctly read-only
File: scripts/ac_audit_agent.py lines 105-124
Severity: INFO
Description: The agent has only Read, Grep and Glob. Bash, Write and Edit are denied, MCP is strict, and the budget is capped. The verdict is parsed only from the last line, and the script itself writes the report. No issues found.

## Delta (2026-09-29)

Scope: `git(check=...)` in scripts/fix_loop_guard.py (lines 106-111, 149, 154, 163) and the `PLAYWRIGHT_TITLE` regex in scripts/ac_audit_agent.py (lines 33-36).

- **fix_loop_guard.py:** The state-changing git calls (`reset --mixed`, `checkout base -- <path>` and `checkout base -- .`) now raise `CalledProcessError` on failure. scripts/fix_loop_agent.py (lines 101, 177, 182) does not catch it, so a failed revert or discard stops the run before `commit_trace`. This fails closed and closes a silent-continue path. Arguments are still passed as an argv list with no shell, so this adds no injection surface. SCR-002 is unchanged: staged new files still survive, because the delta does not reset the index. SCR-001 is also unchanged.
- **ac_audit_agent.py:** The regex now counts only `test(` and `test.only(` titles, which removes false coverage from `test.skip`, `test.fixme` and `test.describe`. The pattern uses negated character classes with no nested quantifiers, so it has no ReDoS risk. It only reads repo files, so it adds no new risk.
- New findings: none. SCR-001 and SCR-002 (WARN) are still open, so the overall verdict stays WARN.

VERDICT: WARN
