# Clean Code Review — chore/policyforge-substrate (scripts/ fix-loop + ac-audit) — 2026-09-29
Scope: scripts/fix_loop_guard.py (164 lines), scripts/fix_loop_trace.py (77), scripts/fix_loop_agent.py (191), scripts/ac_audit_agent.py (189)
Counts: high 0 · medium 3 · low 5
Tool results: ruff ✓ (caller-reported) · mypy --strict ✓ (caller-reported) · lint-imports n/a · arch tests n/a
Size/shape: every file is under 300 lines, every function is under 50 lines, nesting is at most 3 and every function takes at most 4 parameters. Splitting the fix loop into guard, trace and agent modules gives each module one clear job.

## High
(none)

## Medium
- [CC-001] scripts/fix_loop_guard.py:106-110 — `git()` ignores the return code and stderr. If `reset`, `checkout` or `ls-tree` fails inside `revert_protected`/`discard_changes`, nothing reports it, so the tamper check can look like it succeeded when it did not. — Fix: add a `check: bool = True` parameter that raises on a non-zero exit. Use `check=False` only for the read-only queries that are expected to fail.
- [CC-002] scripts/ac_audit_agent.py:33 — `test(?:\.\w+)?\(` also matches `test.skip(`, `test.fixme(` and `test.describe(`. A skipped test or a describe title therefore counts as AC coverage, which goes beyond docs/conventions.md:105 ("AC-NN in the `test(...)` title"). — Fix: match only `test(` and `test.only(`, or explicitly exclude `skip`/`fixme`/`describe`.
- [CC-003] scripts/CLAUDE.md:5-8 — The script table does not list the new helper modules `fix_loop_guard.py` and `fix_loop_trace.py`. Also, the "standalone PEP 723 scripts" rule does not hold for them: they have no PEP 723 header and are imported through `sys.path.insert`. — Fix: update the substrate doc (humans edit it) to list both modules as import-only helpers for `fix_loop_agent.py`.

## Low
- [CC-004] scripts/ac_audit_agent.py:33 — The title pattern `[^"'`]*` stops at the first quote character. A title such as `"customer's quote AC-03"` is cut off before the AC id, and the AC is reported as MISSING when it is covered. — Fix: capture up to the matching closing quote with a backreference, e.g. `(["'`])(.*?)\1`.
- [CC-005] scripts/fix_loop_trace.py:61 and scripts/fix_loop_agent.py:179 — Each call reads the clock separately, so near midnight the trace **Date** and the filename date can disagree, and `render_trace` is not deterministic. — Fix: compute the timestamp once in `main` and pass it into `render_trace`.
- [CC-006] scripts/fix_loop_agent.py:103-105 — `Attempt(...)` is built with a positional boolean expression, which is hard to read. — Fix: use keyword arguments (`passed=..., tampered=...`).
- [CC-007] scripts/ac_audit_agent.py:121-123 and scripts/fix_loop_agent.py:85 — Budget and turn limits are written inline (`2.0`, `40`, `60`), while fix_loop uses a named constant for its budget. — Fix: name them as module constants in both scripts so they are handled the same way.
- [CC-008] scripts/fix_loop_trace.py:24 — `Trace.base` starts as `""` and is set later by `loop()`. `render_trace` would print an empty base if it were called earlier. — Fix: make `base` a required field, or assert that it is set in `render_trace`.

Behaviour check: both scripts use `setting_sources=["project"]` and `strict_mcp_config`. The audit agent is limited to Read/Grep/Glob, and only the fix loop can edit (scripts/CLAUDE.md:12-14). Trace sections 1, 2.N, 3.N, 4 and 5 match docs/conventions.md:150-151. ac-audit counts every id in a multi-id marker, and its report always ends with `VERDICT: PASS|FAIL` (docs/conventions.md:115-119). Neither script hard-codes an API key. The `shell=True` call in `run()` is left to security-reviewer.

VERDICT: APPROVE_WITH_NITS

## Delta — 2026-09-29 (CC-001, CC-002, CC-004 follow-up)
- CC-001 resolved: scripts/fix_loop_guard.py:106-110 `git(..., check: bool = False)`. `reset` (l.149) and both `checkout` calls (l.154, l.163) now pass `check=True`, so a failed restore raises instead of passing silently. Read-only queries keep the non-raising default. That default is the reverse of the suggested fix, but it is explicit and documented, so it is acceptable.
- CC-002 and CC-004 resolved: scripts/ac_audit_agent.py:34-36 now matches only `test(` and `test.only(`, so skip, fixme and describe titles no longer count as coverage. A single-quoted title allows escaped `\'`, and a double-quoted or backtick title can now contain apostrophes.
- [CC-009] low — scripts/fix_loop_guard.py:151 — `ls-tree` still runs with `check=False`, and its output decides between restoring and deleting at l.153-156. If it fails, `in_base` is empty and tracked protected files get unlinked when they should be restored. — Fix: pass `check=True` to this call.
- [CC-010] low — scripts/fix_loop_guard.py:108-110 — `check=True` with `capture_output` raises `CalledProcessError`, but git's stderr is not in the message, so the failure is hard to diagnose. — Fix: catch it in `git()` and re-raise with `proc.stderr` included.
Counts after delta: high 0 · medium 1 (CC-003) · low 6 (CC-005..CC-010)

VERDICT: APPROVE_WITH_NITS
