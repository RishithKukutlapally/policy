# Commit Plan (for the human git operator)

Claude builds files only; **all git operations are done by Rishith** (DEC-008 variant: branches → GitLab
Merge Requests from the office laptop). This file lists, in order, the branch and commits to make so the
history shows the rubric evidence: TDD `test:` (red) before `feat:` (green) before `refactor:`, and one
MR per branch into `main` (merge-commit method = `--no-ff`).

MR description for every branch = intent block: **Intent / Why / Acceptance / Out of scope** (given below).

## Current local state (already in git — no action needed)

| Ref | Contents |
|-----|----------|
| `main` | `chore: initialize repository` + local `--no-ff` merge of `chore/harness-scaffold` |
| `chore/harness-scaffold` | `chore(harness): scaffold …` (pristine harness via `/scaffold`), `fix(hooks): make harness hooks run on Windows` |
| `chore/policyforge-substrate` | checked out; all substrate files below are **uncommitted** in the working tree |

## Branch 2 — `chore/policyforge-substrate`

Suggested commits (in order):

1. `docs: add canonical conventions, decision log and knowledge deposits`
   `docs/conventions.md docs/decisions.md docs/knowledge-deposits.md docs/rubric-checklist.md docs/commit-plan.md docs/debugging/`
2. `docs: layered CLAUDE.md hierarchy and AGENTS.md table of contents`
   `CLAUDE.md AGENTS.md backend/CLAUDE.md backend/src/*/CLAUDE.md backend/policy_rules/CLAUDE.md backend/migrations/CLAUDE.md backend/tests/CLAUDE.md frontend/CLAUDE.md e2e/CLAUDE.md specs/CLAUDE.md scripts/CLAUDE.md`
3. `feat(hooks): PolicyForge NFR guard hooks with self-test`
   `.claude/hooks/lib/ .claude/hooks/premium-precision-check.js .claude/hooks/policy-immutability-check.js .claude/hooks/pii-redaction-check.js .claude/hooks/append-only-repository-check.js .claude/hooks/shell-immutability-check.js .claude/hooks/tests/ .claude/settings.json`
4. `fix(hooks): harness layer hooks know the Domain layer; timeouts in seconds`
   `.claude/hooks/check-architecture.js .claude/hooks/pre-commit-gate.js .claude/hooks/task-completed.js .claude/architecture.md .claude/state/learned-rules.md`
5. `feat(agents): project agents, skills and commands`
   `.claude/agents/ .claude/skills/ .claude/commands/`
6. `feat: plugin manifest, Playwright MCP and GitLab CI with Claude review`
   `plugin.json .mcp.json .gitlab-ci.yml .gitignore`
7. `feat(scripts): Claude Agent SDK AC audit and autonomous fix loop`
   `scripts/`
8. `docs(reviews): security and clean-code review reports for the substrate`
   `specs/reviews/`

**MR intent block**
- Intent: Add the PolicyForge AI-native substrate on top of the harness (agents, skills, commands, NFR guard hooks, CLAUDE.md hierarchy, plugin, MCP, CI, Agent SDK scripts).
- Why: Rubric §7.1 project-specific substrate; guardrails for NFR-01/02/03/05 before any code is generated.
- Acceptance: hook self-test 58/58; security review WARN (no BLOCK); clean-code review APPROVE_WITH_NITS; ruff + mypy --strict clean on scripts.
- Out of scope: specs, application code.

## Branch 3 — `docs/brd-spec-design`

1. `docs: business case and approved BRD` — `docs/business-case.md specs/brd/brd.md`
2. `docs(spec): app spec, six feature specs and 24 acceptance criteria` — `specs/app_spec.md specs/*_spec.md`
3. `docs(spec): epics, 34 stories, dependency graph and features.json` — `specs/stories/ specs/features.json features.json scripts/build_features.py`
4. `docs(design): system design, API contracts, data models, folder structure, component map, deployment` — `specs/design/*.md specs/design/*.json`
5. `docs(design): nine responsive UI mockups` — `specs/design/mockups/`
6. `docs: architecture (C4 + sequence diagrams) and conventions` — `docs/architecture.md docs/conventions.md docs/decisions.md`

**MR intent** — Intent: capture requirements, specs and architecture before any code. Why: spec-is-truth; every AC must exist before a test references it. Acceptance: 24 ACs traced to 34 stories and 181 features; both design schemas valid. Out of scope: application code.

## Branch 4 — `feat/sprint-1-foundation-catalog`

**TDD ordering matters here** — for each story commit the failing tests first (`test:`), then the implementation (`feat:`). That pairing is the red→green evidence the rubric looks for.

| # | Commit | Paths |
|---|--------|-------|
| 1 | `test: platform skeleton and health endpoint (red)` | `backend/tests/ac/test_ac21_health.py backend/tests/unit/test_settings.py backend/tests/unit/test_clock.py backend/tests/integration/test_migrations.py backend/tests/integration/test_database.py backend/tests/conftest.py` |
| 2 | `feat: FastAPI skeleton, settings, clock, database, Alembic baseline, health` | `backend/pyproject.toml backend/uv.lock backend/alembic.ini backend/src/ backend/migrations/ package.json scripts/start.mjs` |
| 3 | `test: rule-file schema, published lock and rule types (red)` | `backend/tests/unit/test_rule_files_valid.py test_published_lock.py test_enums.py test_rule_types.py` |
| 4 | `feat: three versioned product rule sets, schema, lock ledger and types layer` | `backend/policy_rules/ backend/src/types/` |
| 5 | `test: JSON logging, correlation id and PII masking (red)` | `backend/tests/ac/test_ac23_logging.py backend/tests/unit/test_logging_masking.py` |
| 6 | `feat: structured JSON logs, correlation-id middleware, PII masking` | `backend/src/lib/logging.py backend/src/lib/correlation.py backend/src/lib/__init__.py backend/src/api/middleware.py backend/src/main.py` |
| 7 | `test: auth boundary and append-only audit trail (red)` | `backend/tests/ac/test_ac22_auth_boundary.py backend/tests/integration/test_audit_repository.py backend/tests/unit/test_audit_service.py` |
| 8 | `feat: controller-layer auth stub and audited actions` | `backend/src/api/deps.py backend/src/api/routers/admin.py backend/src/repository/models.py backend/src/repository/audit_repository.py backend/src/service/audit_service.py backend/migrations/versions/0002_audit_records.py backend/src/api/errors.py backend/src/api/routers/__init__.py` |
| 9 | `test: architecture contracts (red)` | `backend/tests/architecture/ backend/tests/__init__.py` |
| 10 | `feat: import-linter contracts enforcing the layer rules` | `backend/pyproject.toml` |
| 11 | `test: rule loader, version repository and seed (red)` | `backend/tests/ac/test_ac02_products.py backend/tests/unit/test_rule_loader.py backend/tests/integration/test_rule_set_version_repository.py backend/tests/integration/test_seed.py` |
| 12 | `feat: rule loader, versioned rule-set store and idempotent seed` | `backend/src/config/rule_loader.py backend/src/repository/rule_set_version_repository.py backend/src/seed.py backend/migrations/versions/0003_rule_set_versions.py` |
| 13 | `test: frontend shell and typed API client (red)` | `frontend/src/__tests__/AppShell.test.tsx apiClient.test.ts renderShell.tsx frontend/src/test/setup.ts` |
| 14 | `feat: React shell with role switcher and responsive layout` | `frontend/` (configs, `src/app`, `src/api/client.ts`, `src/types`, `src/pages`, `src/styles`) |
| 15 | `test: catalog service, API and manager screen (red)` | `backend/tests/ac/test_ac02_catalog_api.py backend/tests/ac/test_ac11_version_lifecycle.py backend/tests/unit/test_catalog_service.py backend/tests/integration/test_catalog_audit.py frontend/src/__tests__/CatalogPage.test.tsx` |
| 16 | `feat: product catalog — list, draft, replace draft, publish` | `backend/src/service/catalog_service.py backend/src/api/schemas/catalog.py backend/src/api/routers/products.py frontend/src/pages/CatalogPage.tsx frontend/src/components/ frontend/src/api/catalog.ts frontend/src/types/catalog.ts` |
| 17 | `chore: sprint 1 contract, evaluator and review reports, coverage` | `sprint-contracts/S1.json specs/reviews/ backend/coverage.xml` |

**MR intent** — Intent: platform foundation and the versioned product catalog. Why: every later sprint depends on auth, audit, logging, the rule store and the layer contracts. Acceptance: AC-02, AC-11, AC-21, AC-22, AC-23, AC-24 green; architecture contracts kept; coverage ≥80%. Out of scope: quoting, underwriting, policies.

## Branch 5 — `feat/sprint-2-quote-underwriting`

| # | Commit | Paths |
|---|--------|-------|
| 1 | `test: premium calculator golden cases (red)` | `backend/tests/ac/test_ac01_premium.py backend/tests/unit/test_premium_calculator.py test_condition.py test_term_days.py` |
| 2 | `feat: Decimal premium calculator, condition evaluator, term-day maths` | `backend/src/domain/premium_calculator.py condition.py term_days.py backend/src/types/errors.py` |
| 3 | `test: application validation and underwriting decisions (red)` | `backend/tests/ac/test_ac03_application_validation.py test_ac04_underwriting_decision.py backend/tests/unit/test_application_validator.py test_underwriting_rules.py` |
| 4 | `feat: application validator and underwriting decision matrix` | `backend/src/domain/application_validator.py underwriting_rules.py` |
| 5 | `test: quote service, errors and reprice (red)` | `backend/tests/ac/test_ac01_quote_api.py test_ac12_quote_errors.py test_ac13_quote_reprice.py backend/tests/unit/test_quote_service.py backend/tests/integration/test_quote_repository.py backend/tests/quote_helpers.py` |
| 6 | `feat: quote engine — deterministic pricing on the recorded rule version` | `backend/src/service/quote_service.py backend/src/repository/quote_repository.py backend/src/api/schemas/quotes.py backend/src/api/routers/quotes.py backend/migrations/versions/0004_quotes.py backend/src/repository/models/` |
| 7 | `test: application intake, decisions and admin override (red)` | `backend/tests/ac/test_ac03_application_api.py test_ac04_decision_api.py test_ac14_underwriter_decision.py test_ac09_admin_override.py backend/tests/unit/test_underwriting_*.py backend/tests/integration/test_underwriting_repository_db.py backend/tests/application_helpers.py` |
| 8 | `feat: application intake, manual queue and audited admin override` | `backend/src/service/application_service.py underwriting_service.py backend/src/repository/application_repository.py underwriting_repository.py backend/src/api/schemas/{applications,underwriting}.py backend/src/api/routers/{applications,underwriting}.py backend/migrations/versions/0005_applications_underwriting.py` |
| 9 | `test: quote, apply and workbench screens (red)` | `frontend/src/__tests__/QuotePage.test.tsx ApplyPage.test.tsx UnderwritingPages.test.tsx` |
| 10 | `feat: quote, apply, workbench and override screens` | `frontend/src/pages/{QuotePage,ApplyPage,WorkbenchPage,UnderwritingReviewPage}.* frontend/src/api/{quotes,applications,underwriting}.ts frontend/src/types/ frontend/src/components/{uw,quoteFields,QuoteField}* frontend/src/lib/{maskPii,apiIssues}.ts frontend/src/app/routes.tsx` |
| 11 | `chore: sprint 2 contract` | `sprint-contracts/S2.json` |

**MR intent** — Intent: quote-to-decision. Why: AC-01/03/04/09/12/13/14 are the commercial core. Acceptance: golden premiums exact to the paisa; all three underwriting outcomes with rule-version reason codes; override audited. Out of scope: issuance.

## Branch 6 — `feat/sprint-3-issuance-endorsement`

| # | Commit | Paths |
|---|--------|-------|
| 1 | `test: policy lifecycle state machine, all 25 pairs (red)` | `backend/tests/ac/test_ac10_state_transitions.py backend/tests/unit/test_policy_state_machine.py` |
| 2 | `feat: immutable policy state machine` | `backend/src/domain/policy_state_machine.py` |
| 3 | `test: endorsement rules and premium delta (red)` | `backend/tests/ac/test_ac16_endorsement_rules.py backend/tests/unit/test_endorsement_rules.py` |
| 4 | `feat: endorsement validation and pro-rated premium delta` | `backend/src/domain/endorsement_rules.py` |
| 5 | `refactor: split models.py into a package (477 tests unchanged)` | `backend/src/repository/models/ backend/tests/architecture/test_no_float_in_money.py` |
| 6 | `test: issuance, policy views and lifecycle guard (red)` | `backend/tests/ac/test_ac05_policy_issuance.py test_ac15_policy_views.py test_ac10_policy_state_api.py backend/tests/unit/test_policy_*.py backend/tests/integration/test_policy_*.py backend/tests/policy_helpers.py` |
| 7 | `feat: policy issuance, lifecycle tables and policy views` | `backend/src/repository/models/{policies,lifecycle}.py backend/src/repository/policy_*.py backend/src/service/policy_*.py backend/src/api/schemas/policies.py backend/src/api/routers/policies.py backend/migrations/versions/0006_policies_lifecycle.py` |
| 8 | `test: endorsement service and atomic rollback (red)` | `backend/tests/ac/test_ac06_endorsement.py test_ac16_endorsement_api.py backend/tests/integration/test_endorsement_service.py backend/tests/endorsement_helpers.py` |
| 9 | `feat: atomic, immutable endorsements` | `backend/src/service/endorsement_service.py backend/src/api/schemas/endorsements.py backend/src/api/routers/endorsements.py` |
| 10 | `test: policy and endorsement screens (red)` | `frontend/src/__tests__/PoliciesPage.test.tsx EndorsePage.test.tsx` |
| 11 | `feat: my policies, policy detail and endorse screens` | `frontend/src/pages/{PoliciesPage,PolicyDetailPage,EndorsePage}.* frontend/src/api/{policies,endorsements}.ts frontend/src/components/{policies,endorse,lifecycle}/` |
| 12 | `chore: sprint 3 contract` | `sprint-contracts/S3.json` |

**MR intent** — Intent: issue policies and change them safely. Why: AC-05/06/10/15/16; an endorsement must never half-apply. Acceptance: rollback test proves atomicity; all 25 transition pairs enforced. Out of scope: renewal, cancellation.

## Branch 7 — `feat/sprint-4-renewal-cancellation`

| # | Commit | Paths |
|---|--------|-------|
| 1 | `test: renewal schedule and refund rules (red)` | `backend/tests/ac/test_ac07_renewal_rules.py test_ac08_refund_rules.py backend/tests/unit/test_renewal_rules.py test_refund_rules.py` |
| 2 | `feat: renewal schedule, grace period and refund calculation` | `backend/src/domain/renewal_rules.py refund_rules.py` |
| 3 | `test: payments, renewal, end-of-day and cancellation (red)` | `backend/tests/ac/test_ac07_renewal_api.py test_ac17_payments.py test_ac18_end_of_day_idempotent.py test_ac08_cancellation_api.py test_ac19_refund_rules_api.py backend/tests/integration/test_renewal_cancellation_services.py backend/tests/renewal_helpers.py` |
| 4 | `feat: renewal, payments, idempotent end-of-day and cancellation` | `backend/src/service/{renewal_service,payment_service,cancellation_service}.py backend/src/jobs/ backend/src/api/schemas/{renewals,cancellations}.py backend/src/api/routers/{renewals,cancellations,end_of_day}.py` |
| 5 | `test: portfolio dashboard figures (red)` | `backend/tests/ac/test_ac20_portfolio.py backend/tests/unit/test_portfolio_service.py backend/tests/portfolio_helpers.py` |
| 6 | `feat: admin portfolio dashboard API` | `backend/src/service/portfolio_service.py backend/src/api/schemas/portfolio.py backend/src/api/routers/portfolio.py` |
| 7 | `test: seeded portfolio across every lifecycle state (red)` | `backend/tests/integration/test_seed_portfolio.py` |
| 8 | `feat: seed data and README quick-start` | `backend/src/seed.py backend/src/seed_data/ README.md` |
| 9 | `test: renew, cancel, end-of-day and portfolio screens (red)` | `frontend/src/__tests__/{Renew,Cancel,Portfolio}Page.test.tsx frontend/src/__tests__/fixtures.ts` |
| 10 | `feat: renew, cancel, end-of-day and portfolio screens` | `frontend/src/pages/{RenewPage,CancelPage,EndOfDayPage,PortfolioPage}.* frontend/src/api/{renewal,cancellations,portfolio}.ts frontend/src/components/admin/` |
| 11 | `test: Playwright journeys with committed snapshots` | `e2e/ package.json package-lock.json` |
| 12 | `chore: sprint 4 contract, coverage and evidence` | `sprint-contracts/S4.json backend/coverage.xml specs/reviews/ features.json specs/features.json` |

**MR intent** — Intent: complete the lifecycle and prove it in a browser. Why: AC-07/08/17/18/19/20/24 plus the mandatory one-command start with seed data. Acceptance: end-of-day idempotent; refunds exact; 32 Playwright tests green at two viewports with committed snapshots. Out of scope: none — this closes the scope.

## Branch 8 — `fix/published-version-not-loadable`

Recorded autonomous fix loop (`docs/fix-loops/2026-09-30-published-version-not-loadable.md`).

| # | Commit | Paths |
|---|--------|-------|
| 1 | `test: a published rule version must be loadable (red)` | `backend/tests/ac/test_ac11_published_version_is_loadable.py backend/tests/portfolio_helpers.py` |
| 2 | `fix: resolve rule sets database-first so UI-published versions load` | `backend/src/config/rule_loader.py backend/src/service/portfolio_service.py` |
| 3 | `docs: fix-loop trace and knowledge deposit KD-011` | `docs/fix-loops/ docs/knowledge-deposits.md` |

**MR intent** — Intent: fix a defect found by the E2E suite. Why: a version published through the UI became ACTIVE with no rule file, so quotes and the portfolio returned NOT_FOUND. Acceptance: new AC-11 test red then green; 655 tests pass; 99 % coverage. Out of scope: writing rule files from the server (rejected — violates NFR-02/05).

## Final branch — `docs/evidence`

`docs/rubric-checklist.md`, `docs/tdd.md`, `docs/decisions.md`, `docs/commit-plan.md`, `specs/reviews/` (evaluator + final reviews), `docs/knowledge-deposits.md`.
