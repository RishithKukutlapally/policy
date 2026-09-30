# AGENTS.md — Table of Contents

Index only. Rules live in the linked files; start with `CLAUDE.md`, names in `docs/conventions.md`.
Items marked *(planned)* are produced by the `/brd` → `/spec` → `/design` → sprint pipeline.

## Context hierarchy (CLAUDE.md)

| Scope | File |
|-------|------|
| Root | `CLAUDE.md` |
| Backend module | `backend/CLAUDE.md` |
| Domain rules | `backend/src/domain/CLAUDE.md` |
| Services | `backend/src/service/CLAUDE.md` |
| Repositories | `backend/src/repository/CLAUDE.md` |
| API / controllers | `backend/src/api/CLAUDE.md` |
| Policy rule files | `backend/policy_rules/CLAUDE.md` |
| Migrations | `backend/migrations/CLAUDE.md` |
| Backend tests | `backend/tests/CLAUDE.md` |
| Frontend module | `frontend/CLAUDE.md` |
| E2E / UI validation | `e2e/CLAUDE.md` |
| Specs | `specs/CLAUDE.md` |
| Scripts (Agent SDK) | `scripts/CLAUDE.md` |

## Business, conventions & specs

| Document | File |
|----------|------|
| Canonical conventions | `docs/conventions.md` |
| Business case | `docs/business-case.md` |
| Root spec | `specs/app_spec.md` *(planned — /spec)* |
| Feature specs | `specs/{product-catalog,quote-engine,underwriting,policy-issuance,endorsement,renewal-cancellation}_spec.md` *(planned — /spec)* |
| Harness BRD / stories / design | `specs/brd/brd.md` (approved), `specs/stories/`, `specs/design/` *(planned)* |
| Sprint contracts | `sprint-contracts/` *(planned — per sprint)* |
| Review reports | `specs/reviews/` |

## Agents (`.claude/agents/`)

| Agent | Origin | Purpose |
|-------|--------|---------|
| `planner`, `generator`, `evaluator`, `test-engineer`, `security-reviewer`, `design-critic`, `ui-designer` | Harness | GAN pipeline roles |
| `quote-engine-agent` | Project | Premium computation from versioned rule files |
| `underwriting-agent` | Project | Intake, decision matrix, reason codes, manual queue, overrides |
| `endorsement-agent` | Project | Immutable endorsements with atomic policy updates |
| `renewal-orchestrator-agent` | Project | Renewal cycle, grace-period lapse, cancellation refunds, state machine |
| `policy-version-validator-agent` | Project | Validates and guards immutable rule-set versions |
| `archtest-author-agent` | Project | Import-linter contracts + structural architecture tests |
| `migration-coherence-agent` | Project | Append-only migrations consistent with models |
| `clean-code-reviewer` | Project | Clean-code/SOLID/layering review (required by `require-review` hook) |
| `janitor` | Project (bonus) | Dead code, drift and dependency hygiene |
| `performance-auditor` | Project (bonus) | Query/latency audit, health-endpoint budget |
| `doc-writer` | Project (bonus) | Keeps docs, CLAUDE.md and AGENTS.md in sync with code |

## Skills (`.claude/skills/`)

| Skill | Origin | Purpose |
|-------|--------|---------|
| `brd`, `spec`, `design`, `build`, `auto`, `implement`, `evaluate`, `review`, `test`, `deploy`, `fix-issue`, `refactor`, `improve`, `lint-drift`, `architecture`, `code-gen`, `testing`, `evaluation` | Harness | SDLC pipeline + quality references |
| `premium-calc-evaluator` | Project | Golden-case verification of premium math |
| `policy-state-machine-generator` | Project | Policy lifecycle state machine + exhaustive tests |
| `endorsement-validator` | Project | Endorsement rules, immutability and atomicity checks |
| `policy-version-validator` | Project | Schema + immutability validation of rule files |
| `spec-to-test-generator` | Project | AC-NN / Given-When-Then → tagged failing tests |
| `archtest-author` | Project | Import-linter contracts + pytest architecture tests |

## Commands (`.claude/commands/`)

| Command | Origin | Purpose |
|---------|--------|---------|
| `/scaffold` | Harness | Project initialisation |
| `/quote-check` | Project | Premium golden cases for a product/version |
| `/ac-coverage` | Project | Authoritative AC-NN → test traceability report |
| `/publish-policy-version` | Project | Validate and publish a new rule-set version |
| `/sprint-close` | Project | Reviews, evaluator verdict, `--no-ff` merge with intent block |
| `/record-fix-loop` | Project | Capture an autonomous fix loop under `docs/fix-loops/` |
| `/knowledge-deposit` | Project | Encode a recurring mistake into a rule/hook/skill |

## Hooks (`.claude/hooks/`)

| Hook | Origin | Event | Guards |
|------|--------|-------|--------|
| 15 harness hooks (`protect-env`, `detect-secrets`, `check-architecture`, …) | Harness (Windows-patched) | Pre/PostToolUse, Stop | Secrets, layering, length, lint, types, review |
| `premium-precision-check.js` | Project | PreToolUse Write/Edit | NFR-01 — no float in backend code |
| `policy-immutability-check.js` | Project | PreToolUse Write/Edit | NFR-02/05 — published rules, PUBLISHED.lock, committed migrations |
| `pii-redaction-check.js` | Project | PreToolUse Write/Edit | NFR-03 — no PII in log statements |
| `append-only-repository-check.js` | Project | PreToolUse Write/Edit | NFR-02 — no update/delete on append-only tables |
| `shell-immutability-check.js` | Project | PreToolUse Bash | NFR-02/05 — no shell mutation of append-only artefacts |
| Shared helper / self-test | Project | — | `hooks/lib/policyforge-hook-utils.js`, `hooks/tests/run-hook-tests.js` |

## Packaging, MCP, CI, automation

| Item | File |
|------|------|
| Project plugin manifest | `plugin.json` (harness manifest: `.claude/.claude-plugin/plugin.json`) |
| MCP servers (Playwright) | `.mcp.json` |
| CI pipeline + Claude review | `.gitlab-ci.yml` |
| Agent SDK automation | `scripts/ac_audit_agent.py`, `scripts/fix_loop_agent.py` |

## Engineering docs

| Document | File |
|----------|------|
| Architecture (C4 + sequence) | `docs/architecture.md` *(planned — /design)* |
| TDD discipline | `docs/tdd.md` *(planned — sprint 1)* |
| Debugging post-mortems | `docs/debugging/` |
| Autonomous fix loops | `docs/fix-loops/` *(planned — during sprints)* |
| Knowledge deposits | `docs/knowledge-deposits.md` |
| Decision log (incl. accepted risks) | `docs/decisions.md` |
| Commit plan for the human git operator | `docs/commit-plan.md` |
| Rubric traceability | `docs/rubric-checklist.md` |
| README / quick-start | `README.md` *(planned — sprint 1)* |
