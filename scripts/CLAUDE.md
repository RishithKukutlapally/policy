# scripts/ — programmatic Claude Agent SDK automation

Standalone Python scripts with inline (PEP 723) dependencies — run with `uv run scripts/<name>.py`.

| Script | Purpose |
|--------|---------|
| `ac_audit_agent.py` | Deterministic AC → test matrix, then a read-only Claude agent judges test strength → `specs/reviews/ac-audit.md` |
| `fix_loop_agent.py` | Autonomous fix loop: detect failing tests → agent reproduces + fixes (never edits tests) → validates → commits on `fix/<slug>` with a trace in `docs/fix-loops/`. Requires a clean working tree |
| `fix_loop_guard.py` | Fix-loop guardrails: tool allow/deny lists, protected paths, base-commit tamper check |
| `fix_loop_trace.py` | Fix-loop trace model + markdown template (docs/conventions.md) |

## Rules

- Scripts use `claude_agent_sdk.query` with `ClaudeAgentOptions(setting_sources=["project"])` so the
  agent inherits this repo's CLAUDE.md, agents, skills and hooks.
- Read-only audits restrict `allowed_tools` to Read/Grep/Glob; only the fix loop may edit.
- Auth: the logged-in Claude Code session or `ANTHROPIC_API_KEY`. Never hard-code keys.
