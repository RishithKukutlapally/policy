# Learned Rules
<!-- Monotonic — rules are NEVER deleted. Only add new rules. -->
<!-- Format: Each rule includes Impact, Pattern, Mistake description, Anti-Pattern code, Better Approach code, Rule, and Applied-in fields. See .claude/skills/auto/SKILL.md SECTION 12 for full format. -->

## Rule 1: Hooks must be portable — read fd 0, block via stderr, smoke-test on the host OS

- **Source:** Environment setup (pre-sprint), post-mortem `docs/debugging/2026-09-29-harness-hooks-silent-on-windows.md`
- **Impact:** All 15 harness guardrail hooks were silently disabled on Windows (secrets, env, layering, length, review gate).
- **Pattern:** `ENOENT` on `/dev/stdin` swallowed by a catch-all `exit 0`; `sh` missing on PATH.

### Mistake
Hooks assumed a POSIX host: they read the payload from `/dev/stdin` and shelled out through `sh -c`.
On Windows both fail, and the fail-open catch block turned every check into "allow".

### Anti-Pattern (Avoid This)
```js
const input = JSON.parse(fs.readFileSync('/dev/stdin', 'utf8'));
spawnSync('sh', ['-c', `uv run mypy "${filePath}"`]);
process.stdout.write('BLOCKED: ...'); process.exit(2);
```

### Better Approach
```js
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
spawnSync(`uv run mypy "${filePath}"`, { shell: true });
process.stderr.write('BLOCKED: ...'); process.exit(2);
```

- **Rule:** Any new or edited hook reads stdin via fd 0, writes block reasons to stderr with exit 2, uses `shell: true` for subprocesses, and is smoke-tested with a piped JSON payload (one block case, one allow case) before it is registered in `.claude/settings.json`.
- **Applied in:** all `.claude/hooks/*`, `knowledge-deposit` command, `janitor`, `clean-code-reviewer`.
