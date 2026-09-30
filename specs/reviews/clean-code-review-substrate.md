# Clean Code Review — chore/policyforge-substrate — 2026-09-29 — Round 2
Verdict: CHANGES_REQUIRED
Counts (open this round): high 1 · medium 8 · low 9
Tool results: ruff n/a · mypy n/a · lint-imports n/a · arch tests n/a (no backend/frontend code yet; ruff/mypy/uv are not
installed on this host, so the scripts were checked with an AST pass instead: every def is fully annotated and under 50 lines).
Hook self-test: `node .claude/hooks/tests/run-hook-tests.js` gives **45/45 PASS**. I also ran my own edge-case probes
against a throwaway repo; those results are marked "verified" below.

Scope (Round 2): scripts/fix_loop_agent.py, scripts/ac_audit_agent.py, .gitlab-ci.yml, .claude/settings.json, plugin.json,
.mcp.json, .claude/architecture.md, .claude/hooks/lib/policyforge-hook-utils.js, the 5 project hooks, .claude/hooks/tests/run-hook-tests.js,
check-architecture.js / pre-commit-gate.js / task-completed.js, the 13 CLAUDE.md files, AGENTS.md, docs/conventions.md,
docs/knowledge-deposits.md, docs/rubric-checklist.md, .gitignore, and the scratch file test_hooks2.js.
Not reviewed in this round: .claude/agents, .claude/skills and .claude/commands (a separate sweep is editing them).

## Round 1 findings — status

| ID | Status | Evidence |
|----|--------|----------|
| CC-001 | FIXED (in scope) · rest DEFERRED (sweep) | docs/conventions.md:8-14 sets the folders to lower snake_case. backend/policy_rules/CLAUDE.md:5 matches. The hook regexes are `/i` (policy-immutability-check.js:13, shell-immutability-check.js:15). The self-test "CC-001 casing" case blocks `MOTOR/v1.json`. The agent, skill and command references are deferred. |
| CC-002 | FIXED (in scope) · rest DEFERRED (sweep) | append-only-repository-check.js:14-21 MODELS/TABLES equal conventions.md:60-72. The self-test blocks `UnderwritingDecision` and `premium_payment`. The skill and archtest globs are deferred. |
| CC-003 | PARTIAL | Staging is now scoped (fix_loop_agent.py:250-251). The script commits `fix:` only when fixed and `docs:` otherwise, and runs a tamper check (:143-152). What is still open is carried as a medium below. |
| CC-004 | FIXED (in scope) · rest DEFERRED | conventions.md:46; backend/CLAUDE.md:20; service/CLAUDE.md:15 all use `src.types.errors`. |
| CC-005 | FIXED (in scope) · rest DEFERRED | conventions.md:50 `src/config/rule_loader.py`; service/CLAUDE.md:13. |
| CC-006 | FIXED (in scope) · rest DEFERRED | conventions.md:54 and backend/CLAUDE.md:15 both use `src.main:app`. |
| CC-007 | FIXED (in scope) · rest DEFERRED | conventions.md:20-38 is the single rule-file shape (adds `endorsement`, `renewal.term_months`). domain/CLAUDE.md:23 and policy_rules/CLAUDE.md:10-11 conform. |
| CC-008 | FIXED (in scope) · rest DEFERRED | conventions.md:74 and repository/CLAUDE.md:11 both use `add(...)`. |
| CC-009 | FIXED (in scope) · rest DEFERRED | There is one table list (conventions.md:60-72). repository/CLAUDE.md:9-10 and the hook match it. |
| CC-010 | FIXED (in scope) · rest DEFERRED | ac_audit_agent.py:27-36 is scoped to the section and counts only the marker or the Playwright title. specs/CLAUDE.md:19-21 names `ac-coverage.md` as the authoritative report. |
| CC-011 | DEFERRED (sweep) | Located only in review skill / sprint-close command. |
| CC-012 | PARTIAL (low, see below) | The project root is now resolved from `CLAUDE_PROJECT_DIR`, then `cwd`, then a walk-up (policyforge-hook-utils.js:64-78). The manifest location is still open. |
| CC-013 | FIXED | Word-bounded MONEY (premium-precision-check.js:13), camelCase PII (pii-redaction-check.js:14) and string-literal stripping are in place. Self-test cases "CC-013" pass. |
| CC-014 | FIXED | .gitlab-ci.yml:25-30 standard workflow rules; :121-123 non-protected masked variable documented. |
| CC-015 | FIXED, but see CC-035 | shell-immutability-check.js is registered at settings.json:81-90 and plugin.json:54-59. |
| CC-016 | FIXED (in scope) · skill layout DEFERRED | The ledger is documented (policy_rules/CLAUDE.md:7,20), guarded by the prefix check (policy-immutability-check.js:46-58) and by the Bash hook (:20-23). There are 4 self-test cases. |
| CC-017 | DEFERRED (sweep) | docs/knowledge-deposits.md:6 is unchanged and is the correct target schema. The command still needs aligning. |
| CC-018 | PARTIAL, see CC-038 | architecture.md:9-41 now has Domain and Lib, and the 3 harness hooks add `domain`. The hooks are still hard-coded, linear, and two of them never scan backend/src. |
| CC-019 | FIXED | All settings.json timeouts are now in seconds (5/10/15/30). |
| CC-020 | FIXED | `POLICYFORGE_AGENT_MODEL` env override in both scripts (:37 / :38). |
| CC-021 | FIXED | ac_audit_agent.py:179 computes `missing` from the dicts. The `(__doc__ or "")` guard is at :164 and in fix_loop :293. |
| CC-022 | FIXED (in scope) · command DEFERRED | fix_loop_agent.py:276-282 reuses an existing branch. conventions.md:125-126 defines a single trace template. |
| CC-023 | DEFERRED (sweep) | .gitlab-ci.yml:43 is correct; only the agent remains. |
| CC-024 | FIXED (in scope) · rest DEFERRED | conventions.md:112-119; tests/CLAUDE.md:16-17. |
| CC-025 | FIXED (in scope) · skill DEFERRED | conventions.md:102-103. |
| CC-026 | FIXED (in scope) · rest DEFERRED | conventions.md:110, backend/CLAUDE.md:26 and architecture.md:36 all say stdlib only. |
| CC-027 | FIXED | .mcp.json:6 `@playwright/mcp@0.0.83`; .gitlab-ci.yml:11-13 pins uv / Claude Code / Playwright image. |
| CC-028 | PARTIAL (low, see below) | .gitignore:20 covers pending-reviews.jsonl. |
| CC-029 | FIXED (in scope) · rest DEFERRED | conventions.md:123-124. |
| CC-030 | DEFERRED (sweep) | command only. |
| CC-031 | DEFERRED (sweep) | command only. |
| CC-032 | FIXED | backend/CLAUDE.md:37-39 documents the intentional strictness. |
| CC-033 | FIXED | pii-redaction-check.js:45-47 masks each call separately. The self-test "CC-033" case blocks. |
| CC-034 | PARTIAL, see CC-040 | AGENTS.md marks the missing docs *(planned)*, and docs/decisions.md now exists. The CI jobs still depend on files that do not exist yet. |

## High
- [CC-035] .claude/hooks/shell-immutability-check.js:69 (via policyforge-hook-utils.js:83-91). Every relative path in a Bash
  command is resolved against the project root, not the directory the command runs in after `cd`. So
  `cd backend && sed -i "s/1/2/" migrations/versions/0001_init.py` resolves to `migrations/versions/...`, which fails
  `MIGRATION`, and is **allowed** (verified). Root CLAUDE.md and backend/CLAUDE.md teach `cd backend && uv run ...` as the
  standard idiom, so this bypasses NFR-05 (and NFR-02 through `cd backend/policy_rules && ... motor/v1.json`) with the most common command shape.
  — Fix: track `cd <dir>` segments and resolve later paths against that directory. Or protect by suffix: treat any token
  ending in `migrations/versions/<f>.py` or `policy_rules/<p>/v<N>.json` as a candidate under both the root and `backend/`.
  Add both forms to run-hook-tests.js.

## Medium
- [CC-003 residual] scripts/fix_loop_agent.py:254 still commits with `check=False`, so a failed commit is reported as success.
  :250 stages every changed file that is not protected, including anything that was already dirty before the run, and
  :282 aborts with an uncaught `CalledProcessError` when the tree is dirty and the branch already exists.
  — Fix: refuse to start unless `git status --porcelain` is empty, and use `check=True` on the commit.
- [CC-036] policyforge-hook-utils.js:90 lower-cases the relative path on win32/darwin, and :95 then passes it to
  `git show HEAD:<path>`, which is case-sensitive. A committed file whose name has any uppercase letter is therefore treated
  as uncommitted. Verified: Write and `sed -i` on committed `backend/migrations/versions/0002_Add_Policy.py` are both
  **allowed** (policy-immutability-check.js:60, shell-immutability-check.js:24). This is a hook bypass on Windows.
  — Fix: keep the original-case path for git lookups. Match case-insensitively only for scope tests, or resolve the real
  name with `git ls-files -- <path>` (which honours core.ignorecase). Add a mixed-case fixture to the self-test.
- [CC-037] pii-redaction-check.js:34 strips TS/JS comments with `//.*$` before it removes string literals, so a `//` inside a
  string cuts off the rest of the line. `console.log("http://x", form.pan)` is **allowed** (verified). This is an NFR-03
  bypass for any log call that includes a URL.
  — Fix: call `stripStringText` first, or use a quote-aware comment scanner like `commentStart` in utils. Add the case to the self-test.
- [CC-038] (CC-018 residual) pre-commit-gate.js:114 and task-completed.js:107 scan `<projectDir>/src`. That folder does not
  exist; the code lives in `backend/src`. So the `domain` addition in both hooks never runs: the commit gate always exits 0
  and task-completed always prints "PASS (no src/ directory found)". All three hooks also use a linear `LAYERS` order
  (check-architecture.js:10, pre-commit-gate.js:10, task-completed.js:10). That order allows `repository -> domain` and
  `api -> repository/domain`, which conventions.md:108-110 forbids, and `src/lib` gets no stdlib-only check.
  architecture.md:119 claims check-architecture reads project-manifest.json, but it does not.
  — Fix: read `project-manifest.json` `layers[].path`, and encode the allowed-imports table from conventions.md as an explicit
  map instead of a rank order. Add `lib` as its own rule. Until then, correct architecture.md:39-40,119 so it does not claim enforcement that is not happening.
- [CC-039] .gitlab-ci.yml:135-136 restores `.claude CLAUDE.md AGENTS.md .mcp.json` in one `git checkout`. If any pathspec is
  missing on the target branch, git restores **nothing**, and `|| true` hides the failure. That is the case for this MR:
  `main` has no AGENTS.md or .mcp.json (verified in a worktree, exit 1, with .claude/ and CLAUDE.md left deleted). The
  reviewer then runs without CLAUDE.md or the reviewer agent files its prompt tells it to read. This fails safe, but the review quality drops silently.
  — Fix: restore each path separately with its own `git checkout origin/<target> -- <path>` and log any path that is absent
  on the target, and fail the job if CLAUDE.md or .claude/agents cannot be restored.
- [CC-040] (CC-034 residual) .gitlab-ci.yml:34-108. `backend-test`, `frontend-test`, `e2e-test` and `build` have no guards,
  but `backend/pyproject.toml`, `frontend/package.json` and a root `package.json` do not exist yet. Every pipeline on this
  substrate MR (and on `main` after the merge) will fail. That conflicts with the rubric item "passing build on main" and
  with PR-driven merges.
  — Fix: add `rules: - exists: [backend/pyproject.toml]` (or the frontend/root package.json) to each job, so the substrate
  pipeline runs only hook-selftest + claude-review.
- [CC-041] scripts/fix_loop_agent.py is 333 lines, over the 300-line file limit.
  — Fix: move the trace model and rendering (`Attempt`, `Trace`, `render_attempt`, `render_trace`, about 75 lines) into
  `scripts/fix_loop_trace.py`, or move the permission lists into a small module.
- [CC-042] scripts/fix_loop_agent.py:56-71. The protected set leaves out test configuration and co-located frontend tests. The
  agent can still "fix" a failure by editing `backend/pyproject.toml` (`[tool.pytest.ini_options] addopts = -k "not ..."`,
  `--cov-fail-under`), `frontend/vitest.config.*`, `e2e`-adjacent `playwright.config.*`, or the default co-located Vitest
  tests `frontend/src/**/*.test.ts(x)` (only `__tests__/` is covered). The "never weaken a test" promise (:8-9,
  scripts/CLAUDE.md:8) does not cover these paths.
  — Fix: add these paths to `PROTECTED_PREFIXES`/`is_protected`, and match `*.test.ts`, `*.test.tsx`, `*.spec.ts` and `conftest.py` by filename.

## Low
- [CC-043] append-only-repository-check.js:67. The fix text names `PolicyVersion` and `StateTransition`, which are not
  canonical names (conventions.md uses `RuleSetVersion`, `PolicyStateTransition`). :22-24 SNAKE matches substrings, so
  `session.delete(quote_override_flag)` is blocked (verified false positive), and `rule_version` is an alias that is not in
  conventions. — Fix: derive the snake names from MODELS, match whole `_`-delimited words, and update the message.
- [CC-044] premium-precision-check.js:23 FLOAT_LITERAL misses scientific notation: `premium = x * 1e-2` is allowed
  (verified). — Fix: extend the literal pattern with an exponent alternative (`\d+(\.\d+)?[eE][+-]?\d+`).
- [CC-045] settings.json:57 and plugin.json:46 add `NotebookEdit` to the matcher, but `proposedContent` (utils:47-61)
  returns null for it, so all four hooks exit 0. The entry does nothing, and AGENTS.md:82-86 says "Write/Edit".
  — Fix: drop NotebookEdit, or handle `new_source` for `.ipynb` under the scoped paths.
- [CC-046] check-architecture.js, pre-commit-gate.js and task-completed.js were converted from CRLF to LF. `git diff --stat`
  shows about 355 changed lines per file for a 1-line change (`git diff -w --ignore-cr-at-eol` shows 3). The other harness
  hooks are still CRLF. — Fix: add `.gitattributes` (`*.js text eol=lf`) and renormalise in a separate `chore:` commit, or restore CRLF.
- [CC-047] backend/CLAUDE.md:24-25 uses cumulative arrows (`-> + repository, domain`, `-> + service`). Read literally, this
  lets api import repository and domain, which contradicts conventions.md:109 and api/CLAUDE.md:14. domain/CLAUDE.md:21
  ("src.types and stdlib only") leaves out `src.lib`, which conventions.md:110 allows everywhere. architecture.md:98 says
  `src/lib/logger`, while conventions.md:56 says `src/lib/logging.py`. — Fix: list explicit allowed imports per layer, or link to conventions.md.
- [CC-048] docs/rubric-checklist.md:78 says "KD-001…KD-005", but docs/knowledge-deposits.md has KD-001…KD-008. — Fix: update the range.
- [CC-049] scripts/ac_audit_agent.py:146-157. With `--no-agent`, or when the agent leaves out its verdict, the last line of
  the report is not a verdict, which conventions.md:98 requires ("Every verdict is the last line of the report"). :31 counts
  only the first id in `@pytest.mark.ac("AC-01", "AC-02")`. — Fix: append a computed `VERDICT: PASS|FAIL` (missing ACs or
  agent FAIL gives FAIL), and parse every quoted `AC-NN` inside the marker.
- [CC-012 residual] plugin.json is at the repo root, as the rubric requires, but the Claude Code loader reads
  `.claude-plugin/plugin.json`. The `dependencies` key is non-standard. Installing it in this repo would also run the NFR hooks
  twice (settings.json + plugin). — Fix: note in AGENTS.md:93 that the root file is the rubric artefact, or mirror it under `.claude-plugin/`.
- [CC-028 residual] .mcp.json:6 writes to `specs/reviews/playwright-mcp/`. .gitignore has no rule for it, and no document
  says the screenshots are committed evidence. docs/rubric-checklist.md:20 only implies it. — Fix: state the decision in specs/CLAUDE.md.

## Notes
- The scratch file `...\scratchpad\test_hooks2.js` (80 lines) is fully covered by `.claude/hooks/tests/run-hook-tests.js`. All
  31 of its cases have an equivalent in the committed suite. It hard-codes `E:/Policy_Forge` and omits `core.autocrlf=false`,
  so it should be deleted rather than kept. It is outside the repo, so this is not scored.
- run-hook-tests.js is clean: it is data-driven, isolated in a temp repo, removes that repo afterwards, and exits non-zero on
  failure. It runs in CI (`hook-selftest`, .gitlab-ci.yml:56-60). Add regression cases for CC-035, CC-036, CC-037 and CC-044.
- Known shell-hook limits worth documenting in the hook header (the CI arch tests are the backstop): `python -c "open(...,'w')"`,
  `git apply`/`patch`, and `dd of=` are not detected (verified allowed).

Cross-reference for security-reviewer (not scored here): in the `claude-review` job, nested `backend/**/CLAUDE.md`,
`frontend/CLAUDE.md` and `docs/conventions.md` still come from the MR branch, and the prompt tells Claude to read
conventions.md (.gitlab-ci.yml:152). fix_loop_agent.py:113-115 still uses `shell=True` for an operator-supplied `--test-cmd`.

CHANGES_REQUIRED
