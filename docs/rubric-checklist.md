# Rubric Traceability Checklist

Maps every requirement in the capstone brief (BC-AINE-004) to the artefact that satisfies it.
Status: ✅ done · 🔄 in progress · ⬜ not started. Updated 2026-09-30 after Sprint 4.

**Headline numbers:** 20,587 lines of generated production code · 11,686 lines of tests ·
697 backend tests + 98 frontend tests + 32 Playwright tests · 99 % backend coverage · 24 acceptance criteria, all traced.

## 7.1 Claude Code Specs (40 marks)

| Requirement | Artefact | Status |
|---|---|---|
| `specs/app_spec.md` + `specs/<feature>_spec.md` with AC sections | `specs/app_spec.md` + 6 feature specs (24 ACs, Given-When-Then) | ✅ |
| Layered CLAUDE.md (root + per-module + per-folder) | `CLAUDE.md` + 12 module/folder files (`backend/`, `backend/src/{domain,service,repository,api}/`, `backend/{policy_rules,migrations,tests}/`, `frontend/`, `e2e/`, `specs/`, `scripts/`) | ✅ |
| AGENTS.md as table of contents only | `AGENTS.md` | ✅ |
| ≥3 project skills | **6**: premium-calc-evaluator, policy-state-machine-generator, endorsement-validator, policy-version-validator, spec-to-test-generator, archtest-author | ✅ |
| ≥2 project commands | **6**: `/quote-check`, `/ac-coverage`, `/publish-policy-version`, `/sprint-close`, `/record-fix-loop`, `/knowledge-deposit` | ✅ |
| ≥2 project hooks | **5**: premium-precision-check, policy-immutability-check, pii-redaction-check, append-only-repository-check, shell-immutability-check — registered in `.claude/settings.json`, 58-case self-test run in CI | ✅ |
| ≥2 project agents | **11**: quote-engine, underwriting, endorsement, renewal-orchestrator, policy-version-validator, archtest-author, migration-coherence, clean-code-reviewer + bonus janitor, performance-auditor, doc-writer | ✅ |
| ≥1 Claude Agent SDK usage in `scripts/` | `scripts/ac_audit_agent.py`, `scripts/fix_loop_agent.py` (+ `fix_loop_guard.py`, `fix_loop_trace.py`, `build_features.py`) | ✅ |
| Own `plugin.json` (besides Harness's) | `plugin.json` at repo root | ✅ |
| Debugging log / post-mortem (environment-first) | `docs/debugging/2026-09-29-harness-hooks-silent-on-windows.md` | ✅ |
| Playwright MCP in `.mcp.json`, used by evaluator | `.mcp.json` (pinned v0.0.83); `evaluator.md` + `design-critic.md` tool lists extended with `mcp__playwright__*`. **Honest caveat:** the MCP server returns CONNECT_TIMEOUT on this machine every session, so the evaluator verified the UI through the committed Playwright suite (32 tests, 18 snapshots) rather than driving screens through MCP — the contracts' `design_checks` are therefore unscored. Retry on the office laptop: one evaluator pass saving screenshots to `specs/reviews/playwright-mcp/` closes this. | ⚠️ configured, not exercised |

## 7.2 Business Understanding (20 marks)

| Requirement | Artefact | Status |
|---|---|---|
| `docs/business-case.md` | Problem, users, 12 domain rules, metrics, value proposition | ✅ |
| ≥4 rule/validator files under `src/domain/` | **9**: premium_calculator, underwriting_rules, application_validator, policy_state_machine, endorsement_rules, renewal_rules, refund_rules, condition, term_days | ✅ |
| Frontend with ≥1 responsive layout | React + Vite + TS, 767.98 px breakpoint (nav collapses, tables → cards) across all 9 screens | ✅ |
| Testable ACs (GWT / AC-NN) in ≥4 specs | All 7 specs use AC-NN + Given-When-Then | ✅ |

## 7.3 Architectural Discipline (8 marks)

| Requirement | Artefact | Status |
|---|---|---|
| `tests/architecture/` with ≥3 structural tests | **6** modules: layering, no-float-in-money, append-only repositories, no-PII-in-logs, business-date-only-from-clock, migrations-append-only | ✅ |
| import-linter configured for layering | 5 contracts in `backend/pyproject.toml`, all KEPT | ✅ |
| `docs/tdd.md` + ≥10 test files showing red→green→refactor | `docs/tdd.md` (AC-04 worked example); **60+ test files**; `docs/commit-plan.md` fixes the `test:` → `feat:` commit order | ✅ |

## 7.4 Technical Implementation (26 marks)

| Requirement | Artefact | Status |
|---|---|---|
| `docs/architecture.md` with ≥1 diagram + layered structure | 4 Mermaid diagrams (C4 context, container, quote-to-bind sequence, end-of-day) + layer rules | ✅ |
| ≥3000 lines of meaningful generated code | **20,587** lines (backend + frontend) | ✅ |
| Playwright UI validation with a snapshot directory | `e2e/tests/*.spec.ts-snapshots/` — 18 PNG + 4 ARIA baselines, 32 tests green at 1280×800 and 390×844 | ✅ |
| Every spec AC has ≥1 tagged test | AC-01…AC-23 via `@pytest.mark.ac`; AC-24 via frontend + Playwright | ✅ |
| ≥20 unit tests + coverage artefact + tool declared | 697 backend tests; `backend/coverage.xml` at **99 %**; `pytest-cov` in `pyproject.toml` | ✅ |

## 7.5 CI/CD (6 marks)

| Requirement | Artefact | Status |
|---|---|---|
| `.gitlab-ci.yml` build + test pipeline | test (backend, frontend, e2e, hook self-test) → build → review | ✅ |
| Claude Code Action (or equivalent) wired in | `claude-review` job: Claude Code headless on MRs, config restored from the target branch, read-only tools, last-line verdict gate | ✅ |
| ≥3 PR-driven merges, zero direct commits to main | `docs/commit-plan.md` — branch + commit sequence, merged via GitLab MRs from the office laptop (DEC-008) | 🔄 user's git step |

## 8.1 Mandatory deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Working app, single command (`npm start`), seed data (3 products + 7 policies across all lifecycle states, 84 % auto-bind), README quick-start | ✅ |
| 2 | `docs/business-case.md` | ✅ |
| 3 | `specs/app_spec.md` + 6 feature specs | ✅ |
| 4 | Layered CLAUDE.md + AGENTS.md | ✅ |
| 5 | `.claude/{agents,skills,commands,hooks}` harness + project additions | ✅ |
| 6 | Harness installed, scaffolded, full sprint cycles; `sprint-contracts/`, `specs/reviews/` | ✅ 4 contracts (30 api_checks, schema-valid) + 10 review reports; evaluator `VERDICT: PASS` |
| 7 | Root `plugin.json` + `.mcp.json` with Playwright | ✅ |
| 8 | Unit, architecture, AC-tagged, Playwright tests + coverage report | ✅ |
| 9 | CI pipeline with Claude review | ✅ (runner needs the IT ticket at the office) |
| 10 | ≥3 PR-driven merges, zero direct pushes to main | 🔄 user's git step |

## 8.2 Good-to-have

| # | Item | Status |
|---|---|---|
| 11 | `docs/architecture.md` (C4 + sequence) + `docs/tdd.md` with the AC-04 worked example | ✅ |
| 12 | Autonomous fix-loop trace in `docs/fix-loops/` | ✅ real defect: `2026-09-30-published-version-not-loadable.md` |
| 13 | `docs/knowledge-deposits.md` | ✅ KD-001…KD-012 |
| 14 | Multiple sprint cycles (catalog → quote+underwriting → issuance+endorsement → renewal+cancellation) | ✅ 4 sprints, 4 contracts |
| 15 | Bonus agents (janitor, performance-auditor, doc-writer) | ✅ |

## Extra evidence beyond the rubric

| Item | Where |
|---|---|
| Engineering decision log with accepted risks | `docs/decisions.md` (DEC-001…DEC-016) |
| Canonical naming/contract source | `docs/conventions.md` |
| Security + clean-code review reports | `specs/reviews/` |
| Guard-hook self-test (58 cases) run in CI | `.claude/hooks/tests/run-hook-tests.js` |
| Commit plan preserving TDD order for the human git operator | `docs/commit-plan.md` |
