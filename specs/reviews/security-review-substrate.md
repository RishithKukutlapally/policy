# Security Review — PolicyForge substrate — Round 2 (verification) — 2026-09-29

Branch `chore/policyforge-substrate`, uncommitted.

**In scope:**
- `scripts/fix_loop_agent.py`
- `scripts/ac_audit_agent.py`
- `.gitlab-ci.yml`
- `.claude/settings.json`
- `plugin.json`
- `.mcp.json`
- `.gitignore`
- `.claude/hooks/lib/policyforge-hook-utils.js`
- the 5 project hooks (`premium-precision-check`, `policy-immutability-check`, `pii-redaction-check`, `append-only-repository-check`, `shell-immutability-check`)
- `.claude/hooks/tests/run-hook-tests.js`
- the scratch file `%TEMP%\...\scratchpad\test_hooks2.js`

**Out of scope:** `.claude/agents`, `.claude/skills` and `.claude/commands`, which are being edited concurrently.

**Method:**
- Manual re-read of every file in scope.
- `node .claude/hooks/tests/run-hook-tests.js`: 45/45 pass.
- A separate bypass probe that sends crafted stdin payloads to the hooks against a throwaway git repo.
- A simulation of `fix_loop_agent.revert_protected()` in a throwaway repo that had uncommitted work.

## Summary

| Round-1 finding | Status |
|---|---|
| SUB-H1 fix-loop agent over-privileged | **PARTIAL** (residual is blocking; see below) |
| SUB-H2 CI reviewer runs MR-controlled config | **FIXED** (new variable-exposure issue, see R2-M1) |
| SUB-M1 cwd-relative hook commands | **FIXED** for the NFR guards; PARTIAL for harness hooks |
| SUB-M2 case-sensitive scope matching | **FIXED** (regression, see R2-L1) |
| SUB-M3 plugin project root | **FIXED** |
| SUB-M4 Bash/NotebookEdit bypass of guards | **PARTIAL** |
| SUB-M5 over-broad project allow list | **DEFERRED / ACCEPTED-RISK** (user decision) |
| SUB-M6 verdict gates | **FIXED** |
| SUB-M7 fix loop `git add -A` | **PARTIAL** |
| SUB-L1 fail-open on malformed input | **OPEN** |
| SUB-L2 immutability fails open when git errors | **OPEN** |
| SUB-L3 `#` in strings | **FIXED** |
| SUB-L4 camelCase PII | **FIXED** |
| SUB-L5 slug/workdir validation | **FIXED** |
| SUB-L6 `shell=True` test command | **OPEN (accepted, Low)** |
| SUB-L7 audit agent read-only | **FIXED** (minor residual) |
| SUB-L8 unpinned supply chain | **FIXED** |

New findings in this round: R2-H1 (High), R2-M1, R2-M2 (Medium), R2-L1 to R2-L4 (Low).

| Severity | Open count |
|---|---|
| High (BLOCK) | 2: R2-H1, SUB-H1 residual |
| Medium | 4: R2-M1, R2-M2, SUB-M4 residual, SUB-M7 residual |
| Low | 7: SUB-L1, SUB-L2, SUB-L6, R2-L1 to R2-L4 |
| Deferred | 1: SUB-M5 |

Hardcoded secrets: none in scope.

---

## Verification of Round-1 findings

### SUB-H1 — PARTIAL (residual is BLOCK)

**Evidence of the fix** (`scripts/fix_loop_agent.py`):
- Bare `Bash` has been replaced by scoped patterns (`:42-55`): `uv run pytest/ruff/mypy/lint-imports`, `git diff`, `git status`.
- There are deny rules for WebFetch, WebSearch, NotebookEdit, Task and Agent, for Edit/Write/MultiEdit on tests, specs, `.claude`, `scripts` and CI files, and for `.env*` (`:56-89`).
- `permission_mode="default"` and `max_budget_usd=5.0` are set (`:174-183`).
- Test output is fenced as untrusted data in the prompt (`:159-161`).
- There is a post-attempt tamper check and revert (`:143-152`, `:261-264`).
- Only non-protected files are committed, and only on FIXED (`:248-254`).

**Residual 1 (blocking): the project allow list re-grants what `ALLOWED_TOOLS` removed.**
- The agent is started with `setting_sources=["project"]` (`:180`), so it inherits every `permissions.allow` entry in `.claude/settings.json:17-41`.
- That includes `Bash(git commit:*)`, `Bash(git push:*)`, `Bash(git checkout:*)`, `Bash(git merge:*)`, `Bash(find:*)` (`-exec` gives arbitrary command execution), `Bash(docker compose:*)`, `Bash(curl localhost:*)` and `Bash(gh pr:*)`.
- `git commit -a` also defeats the tamper check. `changed_files()` only looks at `git diff --name-only` and untracked files, so protected edits that have already been committed are invisible to it, and a `git checkout` to another branch moves the whole loop.

This does not require changing M5. Deny rules beat allow rules, so the fix can stay local to this script:
- Add `Bash(git commit:*)`, `Bash(git push:*)`, `Bash(git checkout:*)`, `Bash(git merge:*)`, `Bash(git reset:*)`, `Bash(git switch:*)`, `Bash(find:*)`, `Bash(docker compose:*)`, `Bash(curl localhost:*)`, `Bash(gh issue:*)`, `Bash(gh pr:*)` and `Bash(npx playwright:*)` to `DENIED_TOOLS`.
- Set `strict_mcp_config=True`.
- Record the base SHA before the first attempt. After each attempt, require `git rev-parse HEAD` to still equal it and the current branch to be unchanged, and compute changes with `git diff --name-only <base>` plus untracked files.

**Residual 2 (Medium): the protected set is incomplete.**
`PROTECTED_PREFIXES`/`PROTECTED_FILES` (`:56-71`) do not cover test-weakening configuration:
- `backend/pyproject.toml` (pytest `addopts`, coverage `fail_under`, ruff/mypy/import-linter config)
- `backend/conftest.py`, or any `conftest.py` outside `backend/tests/`
- `frontend/**/*.test.*` and `*.spec.*` outside `__tests__/`
- `vitest.config.*` and `playwright.config.*`
- `.importlinter`
- `.gitignore`
- `backend/policy_rules/**`, which the agent could use to "fix" a premium test by editing a rule file

Fix: add these to both the deny rules and `is_protected()`.

**Inherent risk:** the agent can write production Python that `uv run pytest` then executes. That is code execution by design, so the recommendation from Round 1 still applies: run the loop in a container or worktree that has no credentials.

### SUB-H2 — FIXED
Evidence in `.gitlab-ci.yml:125-168`:
- `.claude`, `CLAUDE.md`, `AGENTS.md` and `.mcp.json` are deleted and then restored from `origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (`:135-136`). If the restore fails, nothing from the MR is left behind.
- A CI-owned settings file sets `disableAllHooks: true`, allows only Read/Grep/Glob, denies Bash, the edit tools and the web tools, and denies reads of `//proc/**`, `//etc/**`, `~/**` and `**/.env*` (`:137-148`).
- The command passes `--strict-mcp-config`, `--allowedTools` and `--disallowedTools` (`:157-160`).
- The CLI is pinned (`:12`, `:132`).
- An `sk-ant-` canary check is present (`:163`).
- `allow_failure` has been removed, and the gate now uses the exact last non-empty line (`:164`).

The MR author can no longer control hooks, permissions or MCP servers. See R2-M1 for the new variable-exposure problem created by the accompanying guidance.

### SUB-M1 — FIXED (NFR guards) / PARTIAL (harness hooks)
- `settings.json:61-86` uses `node "$CLAUDE_PROJECT_DIR/.claude/hooks/<x>.js"` for all 5 project hooks, and timeouts are set.
- **Residual (Low):** the pre-existing harness hooks are still cwd-relative (`settings.json:51, 98-175`). That includes the security-relevant `protect-env.js` and `detect-secrets.js`, which fail open with MODULE_NOT_FOUND when cwd is not the repo root. Fix: apply the same `$CLAUDE_PROJECT_DIR` prefix.

### SUB-M2 — FIXED (see R2-L1)
- `relativeToProject` (`policyforge-hook-utils.js:83-91`) lower-cases on win32 and darwin. The self-test covers `Backend/SRC` and `MOTOR`.
- Short 8.3 aliases such as `POLICY~1` are not a vector on this volume: `dir /x` shows no short names on E:.
- Symlinks and junctions are still not resolved. This is Low, because creating them needs a Bash command that is not allow-listed.

### SUB-M3 — FIXED
`findProjectDir()` (`utils:66-78`) now tries `CLAUDE_PROJECT_DIR`, then the payload `cwd` (only if it contains `.claude`), and only then `__filename`. `plugin.json` hooks use `${CLAUDE_PLUGIN_ROOT}` for the script path only.

### SUB-M4 — PARTIAL (Medium)
**Evidence of the fix:**
- `NotebookEdit` has been added to the matchers (`settings.json:57`, `plugin.json:239`).
- A new PreToolUse `Bash` hook, `shell-immutability-check.js`, covers committed migrations, committed PUBLISHED rule files and the `PUBLISHED.lock` ledger (`>>` append is allowed).
- The self-test cases pass.

**Residual, confirmed by probe (each returned exit 0 against a committed migration):**
- `sed -e … -i <file>`: `-i` is only detected when it is the first argument.
- `perl -p -i -e …`
- `echo x >| <file>`
- `echo x | dd of=<file>`
- `python -c "open('<file>','w')…"` and, by the same logic, `node -e`
- `rm backend/migrations/versions/*.py`: globs are not matched by `PATH_TOKEN`.
- `rm -r backend/migrations`: removing the parent directory.
- `f=<file>; rm $f`
- `cp -t <dir> <src>`
- `cd backend && rm migrations/versions/0001_init.py`, and a payload `cwd` of `backend/` with a relative path. The hook resolves relative paths against the project root, not against `input.cwd`, and does not follow `cd`.

**Coverage gaps:** the shell hook does not cover `backend/src/**` (NFR-01/03, float and PII via `sed`/heredoc) or `.claude/**`. An agent can run `sed -i` on `.claude/settings.json` to remove the guard hooks. No CI backstop exists yet, because `backend/tests/architecture/` is not present.

**False positive:** `grep -rn "rm" <migration>` is blocked, because `\brm\b` matches inside quotes.

**Fix:**
- Resolve relative paths against `input.cwd` and track a leading `cd X &&`.
- Detect `-i`/`--in-place` anywhere in `sed`/`perl` arguments.
- Handle `>|`, `dd of=`, `cp -t`, and `python|node|ruby -[ce]` containing a protected token.
- Treat `rm -r`/`mv` of any ancestor directory and glob tokens (`versions/*`) as protected.
- Add `.claude/**` (settings and hooks) and `CLAUDE.md` to the Bash guard.
- Strip quoted strings before matching verbs.

The guard stays best-effort by nature, so the architecture tests must be the authoritative backstop.

### SUB-M5 — DEFERRED / ACCEPTED-RISK
The allow list in `settings.json:17-41` is unchanged by design and awaits a user decision. Note that it is the root cause of the blocking SUB-H1 residual. That residual can be fixed inside `fix_loop_agent.py` without touching M5.

### SUB-M6 — FIXED
- `ac_audit_agent.final_verdict()` (`:139-143`) requires the last non-empty line to fully match `VERDICT: (PASS|FAIL)`. Anything else returns MISSING and exit 1.
- CI `:164` checks the exact last non-empty line, and `allow_failure` has been removed.

### SUB-M7 — PARTIAL (Medium)
**Fixed:**
- ESCALATED runs commit only the trace (`:250`).
- Protected paths are never staged.
- `.gitignore` now has `.env.*` with `!.env.example`.

**Still open:**
- There is no clean-tree precondition, so a FIXED run commits any pre-existing unrelated non-protected change, for example under `backend/src`.
- `protect-env.js` is still **PostToolUse** (`settings.json:103`), so it reports only after the write has happened.
- The missing precondition also causes R2-H1.

### SUB-L1 — OPEN (Low)
Confirmed by probe:
- Malformed stdin JSON leads to exit 0 in all hooks (`utils:14-21` returns null, and each hook calls `process.exit(0)`).
- A MultiEdit whose first `old_string` misses returns null and exit 0, even though a later edit adds `premium = float(x)`.

Fix: exit 2 on parse failure. When an edit misses, scan the concatenated `new_string` values instead of returning null.

### SUB-L2 — OPEN (Low)
`committedContent` (`utils:94-97`) still maps any git failure (git missing, timeout, not a repository) to "not committed", so the edit is allowed. On-disk content marked PUBLISHED is still not considered. Fix as in Round 1: distinguish `r.error` and statuses other than 0/128 and block with "cannot verify", and also block when the current on-disk rule file is PUBLISHED.

### SUB-L3 — FIXED
`commentStart()` (`utils:100-114`) is quote-aware. The self-test covers both the `s = "#"; premium = float(x)` bypass and the trailing-comment allow case.

### SUB-L4 — FIXED
- `PII` (`pii-redaction-check.js:14`) matches `\w*aadh?aar\w*`, `pan_?(no|num|number|card)`, `health_?decl`, `pre_?existing` and `kyc_?doc` case-insensitively.
- `bind` has been added to the log sinks.
- f-string and template-literal interpolations are inspected, and each mask call only launders its own argument.
- Minor residual: `sys.stderr.write` and `warnings.warn` sinks are not detected.

### SUB-L5 — FIXED
The slug is checked against `^[a-z0-9][a-z0-9-]{0,60}$` (`:40`, `:301`). `--workdir` is resolved and must be inside `REPO_ROOT` (`:305-307`). `--max-attempts` is bounded to 1–5.

### SUB-L6 — OPEN (accepted, Low)
`run()` still uses `shell=True` (`:113-115`). The rationale comment is accurate: the value comes only from the operator's argparse input. This is acceptable for a local operator tool.

### SUB-L7 — FIXED (minor residual)
- `disallowed_tools` now includes MultiEdit, NotebookEdit, Bash, WebFetch, WebSearch, Task and Agent (`ac_audit_agent.py:107-117`).
- `strict_mcp_config=True` and `max_budget_usd=2.0` are set.
- Residual: Read is not confined to `REPO_ROOT`. The output goes only to a local file, so this is Low.

### SUB-L8 — FIXED
The following are pinned:
- `@playwright/mcp@0.0.83` (`.mcp.json:6`)
- `uv==$UV_VERSION`
- `@anthropic-ai/claude-code@$CLAUDE_CODE_VERSION`
- the Playwright image tag

Informational: `node:22` and `python:3.12-slim` are floating tags. Pin them by digest if you need reproducible builds.

---

## New findings

### [R2-H1] Fix loop's tamper-revert destroys pre-existing uncommitted and untracked work under protected paths — BLOCK
File: `scripts/fix_loop_agent.py:137-152` (`changed_files`, `revert_protected`), `:276-282`, `:261`

**Description:** `revert_protected()` treats *every* changed or untracked protected file in the working tree as agent tampering. It then runs `git checkout --` on tracked files and **deletes** untracked ones. Nothing records which changes existed before the agent ran, and `loop()` carries the dirty tree onto the fix branch.

**Confirmed by simulation in a throwaway repo:**
- a pre-existing edit to `.claude/settings.json` was reverted;
- untracked `.claude/agents/new-agent.md` and `specs/new-spec.md` were deleted;
- the attempt was then marked "tampered".

**Impact:** on the current branch, a single failing-test run of the loop would do the following:
- delete all untracked substrate work: `specs/`, `backend/tests/`, `e2e/`, the new `.claude/agents|skills|commands|hooks` files and `scripts/` including the script itself;
- revert every modified `.claude/*` file;
- fail every attempt.

**Fix:**
- At startup, refuse to run unless `git status --porcelain` is empty. This also closes the SUB-M7 residual.
- Alternatively, snapshot the set of changed paths and their content hashes before the first attempt, and revert only paths whose state differs from that baseline.
- Never `unlink` a path that existed before the run.

### [R2-M1] CI guidance tells the operator to un-protect `ANTHROPIC_API_KEY`, which exposes it to every job on every branch
File: `.gitlab-ci.yml:121-123`

**Description:** the comment says to leave "Protected" off and claims "the hardening above is what makes that safe". That is not true:
- An unprotected project variable is injected into **all** jobs of **all** branch and MR pipelines.
- In an MR pipeline, `.gitlab-ci.yml` itself comes from the source branch. Any member with Developer role can add a job that sends the key out. Masking only hides verbatim matches in logs.
- `backend-test` and `e2e-test` also execute MR-controlled code (conftest, npm scripts) with the key in their environment.

The claude-review hardening protects only that one job.

**Fix:**
- Keep the variable **Protected** and **Masked**.
- Scope it to a dedicated environment: add `environment: claude-review` on the job, set the variable's environment scope to `claude-review`, and make that a protected environment with approval.
- As an alternative, run the job with `when: manual` restricted to maintainers.
- Correct the comment.

This is not a blocker for a single-maintainer repository. It becomes a real exposure as soon as other developers have push access.

### [R2-M2] Hook guards are not backed by any repository-level check yet
File: `.gitlab-ci.yml:56-60` (`hook-selftest`); `backend/tests/architecture/` (absent)

**Description:**
- CI only self-tests the hooks. It never scans the codebase for NFR-01/02/03/05 violations.
- Hooks run only inside Claude Code sessions, can be bypassed through Bash (SUB-M4 residual), and fail open (SUB-L1, SUB-L2).
- Nothing in CI would catch a float in money code, a PII log line, or an edited committed migration.

**Fix:**
- Add a CI job that runs each guard over every tracked file in scope. The guards can read file content directly or use `git diff origin/<target>...HEAD` for immutability.
- Implement the planned `backend/tests/architecture/` tests before relying on the hooks.

### [R2-L1] Lower-casing `rel` breaks `git show HEAD:<rel>` for committed files with upper-case names, so the check fails open
File: `policyforge-hook-utils.js:90` together with `:95`; `policy-immutability-check.js:32,60`; `shell-immutability-check.js:24-27`

**Description:** on win32 and darwin, `rel` is lower-cased and then passed to `git show HEAD:<rel>`. Git tree lookup is case-sensitive. As a result, a committed migration `0002_AddCol.py` is reported as "not committed" and can be overwritten. This was confirmed by probe: exit 0.

Alembic's default slugs are lower-case, which limits real-world impact.

**Fix:**
- Lower-case only for scope-regex matching, and pass the original-case path to git.
- Alternatively, resolve the real case with `git ls-files -- <path>` (with `core.ignorecase`) or `fs.realpathSync.native`.

### [R2-L2] `.git/config` is readable by the CI reviewer
File: `.gitlab-ci.yml:143-145`

**Description:** depending on runner version and feature flags, the GitLab runner may write the job token into the `origin` remote URL in `.git/config`. The reviewer can Read `.git/**`, and the output is saved as an artifact. The job token expires when the job ends, so the risk is Low.

**Fix:** add `Read(./.git/**)` to the deny list.

### [R2-L3] `shell-immutability-check` false positive on quoted verbs
File: `shell-immutability-check.js:18`

**Description:** `grep -rn "rm" backend/migrations/versions/0001_init.py` is blocked (confirmed). The same happens for any read-only command whose quoted text contains `rm`, `truncate` or `git restore`.

**Fix:** strip quoted strings before matching verbs.

### [R2-L4] NotebookEdit in the matcher is a no-op
File: `settings.json:57`; `utils:44-62`

**Description:** NotebookEdit's payload key is `notebook_path`, not `file_path`, and `proposedContent` returns null for it, so all 4 guards exit 0. There is no current impact, because every guard scope is `.py`, `.ts`/`.tsx` or rule `.json`, and notebooks are `.ipynb`.

**Fix:** remove it from the matcher to avoid a false sense of coverage, or explicitly block NotebookEdit under `backend/**`.

### Informational
- **Scratch file `…\scratchpad\test_hooks2.js`: harmless.**
  - It creates a temporary git repo under `os.tmpdir()` with dummy content and pipes synthetic payloads to the hooks.
  - It runs no network calls, uses no secrets, only reads the hooks under the hard-coded `E:/Policy_Forge` path, and deletes its temporary repo with `fs.rmSync` at the end.
  - It is fully superseded by `.claude/hooks/tests/run-hook-tests.js` and can be deleted.
- **`.claude/hooks/tests/run-hook-tests.js`** follows the same pattern: a temporary repo, `core.autocrlf=false`, no network and cleanup at the end. 45/45 pass. It is safe to run in CI (`hook-selftest`).
- **`plugin.json:7`** still publishes `krishith@virtusa.com`. Confirm this is intended before distribution.
- **Double registration:** `plugin.json` and `settings.json` both register the guard hooks, so they run twice if the plugin is installed into this repository. This is harmless.
- **Ruff autofix:** `uv run ruff check --fix .` (CLAUDE.md Quick Reference) can rewrite committed migrations. Exclude `migrations/versions` from ruff fix and format in `pyproject.toml` when it is generated.

---

## To reach PASS
1. **R2-H1:** add a clean-tree precondition, or a baseline-aware revert, to `fix_loop_agent.py`.
2. **SUB-H1 residual:** add explicit Bash deny entries for the inherited allow-list commands (git commit, push, checkout, merge, reset and switch; find; docker compose; curl; gh; npx playwright), set `strict_mcp_config=True`, and make the tamper check SHA/branch-anchored.

Everything else (R2-M1, R2-M2, the SUB-M4 and SUB-M7 residuals, and the Lows) is recommended but non-blocking. SUB-M5 remains deferred to the user.

VERDICT: FAIL
