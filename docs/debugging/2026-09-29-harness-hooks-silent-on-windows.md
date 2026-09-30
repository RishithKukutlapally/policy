# Post-mortem — Harness hooks silently disabled on Windows

| | |
|---|---|
| **Date** | 2026-09-29 |
| **Severity** | High — every guardrail hook (secrets, env protection, layering, length, lint, typecheck, review gate) was a no-op |
| **Detected by** | Environment check before scaffolding (reading the hook sources) |
| **Environment** | Windows 11, Node 22.14, Git 2.47, VS Code Claude Code extension; `sh` and `uv` not on PATH |
| **Fix commit** | `fix(hooks): make harness hooks run on Windows` (branch `chore/harness-scaffold`) |
| **Status** | Resolved, verified, encoded as a knowledge deposit |

## Summary

All 15 hooks shipped by `claude-harness-engine` v1 read their tool-call payload with
`fs.readFileSync('/dev/stdin', 'utf8')`. On Windows Node resolves `/dev/stdin` to `C:\dev\stdin`,
which does not exist, so the call throws `ENOENT`. Every hook wraps its body in
`try { … } catch (_) { /* silent */ } process.exit(0)`, so the failure was swallowed and the hook
**allowed** every action. Nothing in the UI indicated a problem.

## Environment-first investigation

We checked the environment before suspecting the harness logic:

1. **Toolchain inventory** — `git`, `node`, `python`, `java` present; `mvn`, `uv`, `sh` absent from PATH.
   Two hooks (`lint-on-save`, `typecheck`) shell out with `spawnSync('sh', ['-c', …])` and `uv run` —
   an immediate red flag for Windows.
2. **Read the hook I/O contract** — every hook reads stdin via the `/dev/stdin` path.
3. **Minimal reproduction, isolated from Claude Code:**

   ```text
   $ echo '{"tool_input":{"file_path":"C:/Windows/evil.py"}}' | node .claude/hooks/scope-directory.js; echo exit=$?
   exit=0                                   ← should have been BLOCKED (exit 2)

   $ node -e "require('fs').readFileSync('/dev/stdin','utf8')"
   ERR ENOENT                               ← root cause

   $ echo '{"a":1}' | node -e "console.log(require('fs').readFileSync(0,'utf8'))"
   {"a":1}                                  ← portable alternative works
   ```

4. **Second-order checks** — `node -e "spawnSync('sh',['-c','echo hi'])"` → `ENOENT` (no `sh` for Node);
   blocking messages were written to **stdout**, but Claude Code feeds a PreToolUse/PostToolUse
   exit-2 reason back to the model from **stderr**, so even on Linux the agent would not see *why* it was blocked.

## Root causes

| # | Cause | Effect |
|---|-------|--------|
| 1 | `readFileSync('/dev/stdin')` is POSIX-only | All 15 hooks crash → silent `exit 0` on Windows |
| 2 | `spawnSync('sh', ['-c', cmd])` assumes a POSIX shell on PATH | lint/typecheck never ran on Windows |
| 3 | Block reasons written to stdout | Agent gets a block without the explanation |
| 4 | Catch-all `catch (_) {}` with `exit 0` | Failures are fail-open and invisible |

## Fix

Mechanical, behaviour-preserving patch applied to the project copy of the hooks (the published harness
clone is untouched), committed separately from the scaffold so the diff is reviewable:

- `fs.readFileSync('/dev/stdin', 'utf8')` → `fs.readFileSync(0, 'utf8')` (fd 0 works on every OS).
- `spawnSync('sh', ['-c', CMD], {…})` → `spawnSync(CMD, { shell: true, … })` (cmd.exe on Windows, /bin/sh elsewhere).
- Blocking (`exit 2`) messages → `process.stderr.write`.
- Installed `uv` (user scope) and added its scripts folder to the user PATH so lint/typecheck hooks can run.

## Verification

```text
$ echo '{"tool_name":"Write","tool_input":{"file_path":"C:/Windows/evil.py","content":"x"}}' | node .claude/hooks/scope-directory.js; echo exit=$?
BLOCKED: Write outside project directory: C:\Windows\evil.py
exit=2
```

Live confirmation: after the patch, the harness `scope-directory` PostToolUse hook fired inside the
Claude Code session when a scratch file was written outside the repo.

## Prevention (encoded)

- **Knowledge deposit KD-001** in `docs/knowledge-deposits.md`.
- **Learned rule** appended to `.claude/state/learned-rules.md`: hooks must read fd 0, write block
  reasons to stderr, and be smoke-tested with a piped payload on the developer OS before first use.
- All PolicyForge project hooks share `.claude/hooks/lib/policyforge-hook-utils.js`, which uses fd 0 and
  stderr by construction. `.claude/hooks/tests/run-hook-tests.js` (45 block/allow cases, run in CI job
  `hook-selftest`) keeps them honest on every OS.
- Hook commands use `"$CLAUDE_PROJECT_DIR/.claude/hooks/…"` so a drifted working directory cannot make
  them fail open (follow-up from `specs/reviews/security-review-substrate.md` M1).
- Hook `timeout` values corrected from milliseconds to seconds (Claude Code's unit) for all hooks.

## Residual risk

- `scope-directory` flags writes to the OS temp dir and `~/.claude` (memory) as "outside project".
  It is a PostToolUse warning (the write still happens), so it is noise rather than a block. Relaxing it
  was left as a human decision rather than changed by the agent.
- Fail-open `catch` blocks remain in harness hooks; a future hardening pass could make parse failures
  fail-closed for the security hooks (`protect-env`, `detect-secrets`).
