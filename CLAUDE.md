# PolicyForge

PolicyForge, a policy issuance and lifecycle management platform for Horizon Insurance covering Term Life,
Motor and Household: quote, application, underwriting, issuance, endorsement, renewal and cancellation,
with versioned policy rule sets.

## Quick Reference

**Backend:** `cd backend && uv run pytest -x -q` | `uv run ruff check --fix .` | `uv run mypy src/`
**Frontend:** `cd frontend && npm test` | `npm run lint` | `npm run typecheck`
**Full stack:** Start backend + frontend (see init.sh)

## Architecture

Strict layered architecture: Types → Config → Repository → Service → API → UI.
One-way dependencies only. See `.claude/architecture.md` for full rules.

## Where to Find Things

| What | Where |
|------|-------|
| Architecture rules | `.claude/architecture.md` |
| Quality principles | `.claude/skills/code-gen/SKILL.md` |
| Testing patterns | `.claude/skills/testing/SKILL.md` |
| Evaluation rubric | `.claude/skills/evaluation/SKILL.md` |
| Sprint contract format | `.claude/skills/evaluation/references/contract-schema.json` |
| Playwright patterns | `.claude/skills/evaluation/references/playwright-patterns.md` |
| Human control knobs | `.claude/program.md` |
| Session recovery | `claude-progress.txt` |
| Feature tracking | `features.json` |
| Learned rules | `.claude/state/learned-rules.md` |

## Pipeline Commands

| Command | Purpose |
|---------|---------|
| `/brd` | Socratic interview → BRD |
| `/spec` | BRD → stories + features.json |
| `/design` | Architecture + schemas + mockups |
| `/build` | Full 8-phase pipeline |
| `/auto` | Autonomous ratcheting loop |
| `/implement` | Code gen with agent teams |
| `/evaluate` | Run app, verify contract |
| `/review` | Evaluator + security review |
| `/test` | Test plan + Playwright E2E |
| `/deploy` | Docker Compose + init.sh |

## Code Style

- TDD mandatory: test first, then implement
- 100% meaningful coverage target, 80% floor
- Functions < 50 lines, files < 300 lines
- Static typing everywhere (zero `any`)
- See `.claude/skills/code-gen/SKILL.md` for full rules

## Git

Branch: `<type>/<description>` (e.g., `feat/user-auth`)
Commits: conventional format (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
