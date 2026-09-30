# Folder Structure — PolicyForge

Produced by `/design` (planner). Backend module names are taken verbatim from `docs/conventions.md` →
"Backend modules" and "Persistence"; layer import rules from "Layer import rules". Files marked _(new vs
conventions)_ are additions this design needs; they respect the layer rules and should be added to
`docs/conventions.md` when approved. [`component-map.md`](component-map.md) says which story creates each file.

## Tree

```
Policy_Forge/
├── package.json                          # root: `npm start` (install → migrate → seed → API :8000 + UI :3000), `npm run e2e`
├── README.md                             # Quick start (E9-S3): prerequisites, `npm start`, URLs, demo users
├── init.sh                               # harness bootstrap (existing; `/deploy` keeps it in sync with `npm start`)
├── .gitlab-ci.yml                        # existing: backend-test, hook-selftest, frontend-test, e2e, build, claude-review
├── CLAUDE.md · AGENTS.md · features.json · claude-progress.txt
│
├── backend/                              # FastAPI API, domain rules, persistence (Python 3.12, uv)
│   ├── pyproject.toml                    # deps incl. fastapi, sqlalchemy 2, alembic, jsonschema, pytest-cov, import-linter, hypothesis; [tool.importlinter] contracts
│   ├── uv.lock
│   ├── alembic.ini                       # script_location = migrations; URL from Settings.database_url
│   ├── CLAUDE.md
│   │
│   ├── src/                              # application package, imported as `src.<layer>`
│   │   ├── __init__.py
│   │   ├── main.py                       # `src.main:app` — FastAPI app, middleware, exception handlers, router auto-registration, lifespan
│   │   ├── seed.py                       # `python -m src.seed` — imports PUBLISHED v1 rule files (E2-S2), demo data via services (E9-S3); idempotent
│   │   │
│   │   ├── types/                        # Layer 1 — imports nothing (pure data definitions)
│   │   │   ├── __init__.py
│   │   │   ├── enums.py                  # ProductCode, PolicyStatus, ApplicationStatus, Decision, EndorsementType, ActorRole, RefundType, EndOfDayAction, UnderwriterDecision (+ AuditAction)
│   │   │   ├── errors.py                 # PolicyForgeError base (code + http_status), InvalidPolicyStateException, AppendOnlyViolationError, RuleFileValidationError, … all typed errors
│   │   │   ├── rules.py                  # frozen RuleSet value objects (PremiumRules, Band, Eligibility, UnderwritingRule, …), Decimal money/rates
│   │   │   └── values.py                 # (new vs conventions) frozen domain I/O objects: Actor, FieldError, UnderwritingOutcome, RefundBreakdown, NextTerm, EndorsementResult
│   │   │
│   │   ├── domain/                       # Layer 2 — imports src.types + stdlib only; no logging, I/O or clock (NFR-08)
│   │   │   ├── __init__.py
│   │   │   ├── premium_calculator.py     # calculate_premium(rule_set, inputs) -> Decimal (E3-S1)
│   │   │   ├── application_validator.py  # validate_application(rule_set, kyc, risk) -> errors, kyc_status (E4-S1)
│   │   │   ├── condition.py              # (new vs conventions) parse/evaluate `<field> <op> <value> and …` rule conditions (E4-S1)
│   │   │   ├── underwriting_rules.py     # evaluate_underwriting(rule_set, risk) -> UnderwritingOutcome (E4-S1)
│   │   │   ├── policy_state_machine.py   # transition, is_terminal, allowed_targets (E5-S1)
│   │   │   ├── term_days.py              # (new vs conventions) term_days / days_elapsed / unused_days shared by endorsement + refund math
│   │   │   ├── endorsement_rules.py      # validate_endorsement, premium_delta (E6-S1)
│   │   │   ├── renewal_rules.py          # renewal_action, next_term, renewal_premium, advance_inputs (E7-S1)
│   │   │   └── refund_rules.py           # calculate_refund (E8-S1)
│   │   │
│   │   ├── config/                       # Layer 3 — types, domain, lib
│   │   │   ├── __init__.py
│   │   │   ├── settings.py               # Settings: database_url, api_port, ui_port, renewal_window_days, policy_rules_dir
│   │   │   └── rule_loader.py            # load_rule_file / parse_rule_content: JSON -> schema-validate -> RuleSet (E2-S2)
│   │   │
│   │   ├── lib/                          # cross-cutting — Python standard library ONLY; importable by config/repository/service/api
│   │   │   ├── __init__.py
│   │   │   ├── logging.py                # get_logger (JSON lines), mask_pii, PII-redacting filter (E1-S2)
│   │   │   ├── correlation.py            # contextvar holding the request correlation id (E1-S2)
│   │   │   └── clock.py                  # (new vs conventions) today()/now_utc() business-date provider, overridable in tests (A-RC-1)
│   │   │
│   │   ├── repository/                   # Layer 4 — types, config, lib, SQLAlchemy; never commits (services own transactions)
│   │   │   ├── __init__.py
│   │   │   ├── database.py               # (new vs conventions) engine, SessionLocal, DeclarativeBase, SQLite FK pragma (E1-S1)
│   │   │   ├── models.py                 # all 11 ORM models (docs/conventions.md → Persistence)
│   │   │   ├── append_only.py            # (new vs conventions) before_flush guard → AppendOnlyViolationError for append-only models (E1-S3)
│   │   │   ├── audit_record_repository.py             # ✅ add, list_for_entity
│   │   │   ├── rule_set_version_repository.py         # ✅ add, latest_status, list_for_product, active_for_product
│   │   │   ├── quote_repository.py                    # add, get
│   │   │   ├── application_repository.py              # add, get, list_by_status, set_status (projection)
│   │   │   ├── underwriting_decision_repository.py    # ✅ add, list_for_application, latest_for_application
│   │   │   ├── underwriting_override_repository.py    # ✅ add, list_for_application
│   │   │   ├── policy_repository.py                   # add, get_by_number, list_for_customer, list_in_force, next_sequence, save projection
│   │   │   ├── policy_state_transition_repository.py  # ✅ add, list_for_policy
│   │   │   ├── endorsement_repository.py              # ✅ add, list_for_policy
│   │   │   ├── premium_payment_repository.py          # ✅ add, get_for_due_date, list_for_policy, sum_amounts
│   │   │   └── refund_repository.py                   # ✅ add, get_for_policy, sum_amounts
│   │   │
│   │   ├── service/                      # Layer 5 — types, domain, config, repository, lib; transactions + audit; no fastapi
│   │   │   ├── __init__.py
│   │   │   ├── unit_of_work.py           # (new vs conventions) UnitOfWork: session scope + repository accessors (API never touches repositories)
│   │   │   ├── audit_service.py          # record(actor, action, entity_type, entity_id, detail) → AuditRecord (E1-S3)
│   │   │   ├── rule_import_service.py    # import_published_rule_files(): verify PUBLISHED.lock hashes, insert v1 rows (E2-S2)
│   │   │   ├── catalog_service.py        # list_products, list_versions, create_draft, replace_draft, publish (E2-S3)
│   │   │   ├── quote_service.py          # create_quote, get_quote, reprice (E3-S2)
│   │   │   ├── application_service.py    # submit_application, get_application (E4-S2)
│   │   │   ├── underwriting_service.py   # queue, decide, override, audit_trail (E4-S3, E4-S4)
│   │   │   ├── policy_issuance_service.py # issue (E5-S2)
│   │   │   ├── policy_query_service.py   # (new vs conventions) list_policies, get_policy_detail (E5-S3)
│   │   │   ├── endorsement_service.py    # endorse, preview (E6-S2)
│   │   │   ├── premium_payment_service.py # record_payment, is_paid (E7-S2)
│   │   │   ├── renewal_service.py        # renewal_quote, renew (customer early renewal), issue_successor (E7-S3, E7-S4)
│   │   │   ├── end_of_day_service.py     # run_end_of_day(as_of, actor) (E7-S3)
│   │   │   ├── cancellation_service.py   # preview_refund, cancel (E8-S2)
│   │   │   └── portfolio_service.py      # portfolio_summary(as_of) (E9-S1)
│   │   │
│   │   └── api/                          # Layer 6 — types, config, service, lib; NOT repository
│   │       ├── __init__.py
│   │       ├── deps.py                   # get_current_actor, require_role(...), get_uow (E1-S3)
│   │       ├── middleware.py             # X-Correlation-ID read/generate/echo + request logging (E1-S2)
│   │       ├── errors.py                 # (new vs conventions) exception handlers → {"error": {code, message, details}} envelope
│   │       ├── schemas/                  # (new vs conventions) Pydantic request/response DTOs; Money = 2-dp string
│   │       │   ├── __init__.py
│   │       │   ├── common.py             # Money, ErrorEnvelope, FieldErrorOut
│   │       │   ├── products.py · quotes.py · applications.py · underwriting.py · policies.py
│   │       │   └── endorsements.py · renewals.py · end_of_day.py · cancellations.py · admin.py
│   │       └── routers/                  # one module per resource; each exports `router`, auto-registered by main.py
│   │           ├── __init__.py           # discover_routers(): imports every module in this package (no shared edits per story)
│   │           ├── health.py             # GET /health (no /api prefix, no auth, no DB)
│   │           ├── products.py           # /api/products… (E2-S4)
│   │           ├── quotes.py             # /api/quotes… (E3-S3)
│   │           ├── applications.py       # POST/GET /api/applications (E4-S2)
│   │           ├── underwriting.py       # /api/underwriting/… (E4-S3, E4-S4)
│   │           ├── policies.py           # POST /api/applications/{id}/issue, GET /api/policies… (E5-S3)
│   │           ├── endorsements.py       # POST /api/policies/{n}/endorsements (E6-S3)
│   │           ├── renewals.py           # GET …/renewal, POST …/payments, POST …/renew (E7-S4)
│   │           ├── end_of_day.py         # POST /api/admin/end-of-day (E7-S4)
│   │           ├── cancellations.py      # GET …/cancellation-preview, POST …/cancel (E8-S3)
│   │           └── admin.py              # GET /api/admin/portfolio (E9-S1)
│   │
│   ├── migrations/                       # Alembic — append-only (NFR-05); never edit a committed revision
│   │   ├── env.py                        # target_metadata = src.repository.models Base.metadata
│   │   ├── script.py.mako
│   │   └── versions/                     # linear chain, one head
│   │       ├── 0001_baseline.py
│   │       ├── 0002_audit_records.py
│   │       ├── 0003_rule_set_versions.py
│   │       ├── 0004_quotes.py
│   │       ├── 0005_applications_underwriting_decisions.py
│   │       ├── 0006_underwriting_overrides.py
│   │       └── 0007_policy_lifecycle.py      # policies, policy_state_transitions, premium_payments, endorsements, refunds
│   │
│   ├── policy_rules/                     # versioned rule sets — DATA, not code
│   │   ├── CLAUDE.md
│   │   ├── PUBLISHED.lock                # "<sha256>  <folder>/v<N>.json" per published file; append-only
│   │   ├── schema/
│   │   │   └── rule-file.schema.json     # JSON Schema every rule file must satisfy
│   │   ├── term_life/
│   │   │   └── v1.json                   # TL rules (base_rate 0.0015, min 3000.00)
│   │   ├── motor/
│   │   │   └── v1.json                   # MO rules (base_rate 0.0310, min 2500.00)
│   │   └── household/
│   │       └── v1.json                   # HH rules (base_rate 0.0008, min 1500.00)
│   │
│   └── tests/                            # pytest; AC tests `test_acNN_*` + @pytest.mark.ac("AC-NN")
│       ├── conftest.py                   # temp SQLite DB, migrated session, TestClient, actor headers, frozen clock, rule-set fixtures
│       ├── fixtures/                     # synthetic builders (Aadhaar 9999…, PAN AAAAA0001A, Test Customer NN)
│       │   ├── __init__.py
│       │   ├── rule_sets.py              # load v1 RuleSets, mutated copies (v2 base_rate 0.0320, …)
│       │   └── factories.py              # quote / application / policy / payment builders via services
│       ├── unit/                         # pure domain + service unit tests (≥ 20)
│       ├── ac/                           # acceptance tests per AC, mostly via TestClient: test_acNN_<topic>.py
│       ├── architecture/                 # layering, domain purity, no-float, append-only repos, PUBLISHED.lock, migration immutability
│       └── integration/                  # migrations + repositories against a temp SQLite DB, rule import, npm start smoke
│
├── frontend/                             # React + Vite + TypeScript UI on :3000 (proxy /api and /health → :8000)
│   ├── package.json                      # dev, build, test (vitest), lint, typecheck
│   ├── vite.config.ts · vitest.config.ts · tsconfig.json · eslint.config.js · index.html
│   ├── CLAUDE.md
│   └── src/
│       ├── main.tsx                      # React root
│       ├── App.tsx                       # router + route table + role guards
│       ├── styles.css                    # mobile-first grid/flex, breakpoint 768 px, visible focus outlines
│       ├── api/                          # typed fetch client per resource; attaches X-Actor-Id / X-Actor-Role / X-Correlation-ID
│       │   ├── client.ts                 # request(), ApiError (error envelope), header injection
│       │   └── products.ts · quotes.ts · applications.ts · underwriting.ts · policies.ts · endorsements.ts · renewals.ts · endOfDay.ts · cancellations.ts · admin.ts
│       ├── pages/                        # one screen per route
│       │   ├── QuotePage.tsx                 # /quote (E3-S3)
│       │   ├── ApplyPage.tsx                 # /apply/:quoteId (E4-S5)
│       │   ├── UnderwriterWorkbenchPage.tsx  # /underwriter/queue (E4-S5)
│       │   ├── UnderwritingReviewPage.tsx    # /admin/underwriting (E4-S5)
│       │   ├── ProductCatalogPage.tsx        # /admin/catalog (E2-S4)
│       │   ├── MyPoliciesPage.tsx            # /policies (E5-S3)
│       │   ├── PolicyDetailPage.tsx          # /policies/:policyNumber (E5-S3)
│       │   ├── EndorsePage.tsx               # /policies/:policyNumber/endorse (E6-S3)
│       │   ├── RenewPage.tsx                 # /policies/:policyNumber/renew (E7-S4)
│       │   ├── CancelPage.tsx                # /policies/:policyNumber/cancel (E8-S3)
│       │   ├── EndOfDayPage.tsx              # /admin/end-of-day (E7-S4) — reachable from Portfolio (see component-map note)
│       │   ├── AdminDashboardPage.tsx        # /admin/portfolio (E9-S2)
│       │   ├── NotFoundPage.tsx              # "Page not found" (E1-S5)
│       │   └── NotAuthorisedPage.tsx         # "Not authorised" (E1-S5)
│       ├── components/                   # shared UI
│       │   ├── AppShell.tsx · SideNav.tsx · RoleSwitcher.tsx          # layout shell (E1-S5)
│       │   ├── StatusBadge.tsx · Money.tsx · FormField.tsx · ResponsiveTable.tsx · ConfirmDialog.tsx · ErrorAlert.tsx
│       │   └── EndOfDayControl.tsx       # date picker + "Run end-of-day" + result counts (E7-S4)
│       ├── lib/                          # (new vs frontend CLAUDE.md) pure helpers
│       │   ├── format.ts                 # Intl en-IN money/date formatting (strings in, strings out; no money arithmetic)
│       │   └── demoUsers.ts              # cust-001 / uw-001 / admin-001, persisted selection
│       ├── types/                        # DTO types mirroring specs/design/api-contracts.md (zero `any`)
│       │   └── api.ts · roles.ts
│       └── test/
│           └── setup.ts                  # vitest + Testing Library setup
│       # unit tests are co-located as *.test.ts(x) next to the file under test
│
├── e2e/                                  # Playwright suite (desktop 1280×800 + mobile 390×844 projects)
│   ├── package.json                      # @playwright/test, @axe-core/playwright
│   ├── playwright.config.ts              # projects desktop/mobile, webServer = root `npm start`, baseURL :3000
│   ├── CLAUDE.md
│   ├── fixtures/
│   │   ├── roles.ts                      # switchRole(page, 'Customer'|'Underwriter'|'Admin')
│   │   └── api.ts                        # seed helpers through the public API (quotes, applications, payments)
│   └── tests/                            # every test title contains ≥ 1 AC-NN
│       ├── shell.spec.ts                         # E1-S5
│       ├── catalog-manager.spec.ts               # E2-S4
│       ├── quote.spec.ts                         # E3-S3
│       ├── apply.spec.ts                         # E4-S5
│       ├── underwriter-workbench.spec.ts         # E4-S5, E9-S4
│       ├── policies.spec.ts                      # E5-S3
│       ├── endorse.spec.ts                       # E6-S3
│       ├── renew.spec.ts                         # E7-S4
│       ├── cancel.spec.ts                        # E8-S3
│       ├── admin-dashboard.spec.ts               # E9-S2, E9-S4
│       ├── customer-journey.spec.ts              # E9-S4
│       ├── lifecycle.spec.ts                     # E9-S4
│       ├── visual.spec.ts                        # E9-S4 — toHaveScreenshot for 9 screens
│       └── visual.spec.ts-snapshots/             # 18 committed baselines: <screen>-desktop-win32.png / <screen>-mobile-win32.png (+ linux for CI)
│
├── scripts/                              # automation
│   ├── start.mjs                         # (E1-S1) orchestrates `npm start`: uv sync → alembic upgrade head → seed → uvicorn :8000 + vite :3000
│   ├── e2e.mjs                           # (E1-S5, extended by E9-S4) boots the stack, waits for /health and :3000, runs Playwright
│   ├── ac_audit_agent.py · build_features.py · fix_loop_agent.py · fix_loop_guard.py · fix_loop_trace.py   # existing agent automation
│   └── CLAUDE.md
│
├── docs/                                 # human docs: business case, conventions (canonical), decisions, fix loops, debugging
│   ├── conventions.md · decisions.md · business-case.md · commit-plan.md · rubric-checklist.md · knowledge-deposits.md
│   ├── debugging/
│   └── fix-loops/                        # /record-fix-loop traces
│
├── specs/                                # spec is truth
│   ├── app_spec.md + 6 feature specs     # product-catalog, quote-engine, underwriting, policy-issuance, endorsement, renewal-cancellation
│   ├── brd/brd.md
│   ├── stories/                          # E1-S1 … E9-S4 + dependency-graph.md
│   ├── design/                           # system-design, api-contracts(.schema.json), data-models(.schema.json), folder-structure, component-map, deployment
│   │   ├── mockups/                      # E{n}-S{n}.html per UI story
│   │   └── amendments/                   # approved design changes
│   └── reviews/                          # evaluator, security, clean-code, ac-coverage, validator reports (docs/conventions.md → Reports)
│
└── sprint-contracts/                     # harness sprint contracts (existing)
```

## Layer placement rules (quick reference)

| Directory | May import | Must not |
|-----------|------------|----------|
| `src/types/` | nothing | anything in `src.*`, `logging` |
| `src/domain/` | `src.types`, stdlib (`decimal`, `dataclasses`, `typing`, `datetime.date` arithmetic) | `src.lib`, `logging`, `sqlalchemy`, `open`, `date.today()`/`datetime.now()`, `time` |
| `src/config/` | types, domain, lib, `jsonschema` | repository, service, api |
| `src/repository/` | types, config, lib, `sqlalchemy` | domain, service, api |
| `src/service/` | types, domain, config, repository, lib | api, `fastapi` |
| `src/api/` | types, config, service, lib, `fastapi`, `pydantic` | repository |
| `src/lib/` | standard library only | everything else |

## Notes

- **No shared "registration" edits.** Routers are discovered by `src/api/routers/__init__.py`, and every typed error
  carries its own `code`/`http_status` (base `PolicyForgeError` in `src/types/errors.py`), so the generic handler in
  `src/api/errors.py` never needs per-story edits. Stories in the same parallel group therefore only collide on
  append-style additions to `src/types/errors.py`, `src/types/values.py`, `src/repository/models.py`, `frontend/src/App.tsx`
  and `frontend/src/types/api.ts` — see `component-map.md` → "Shared files".
- Playwright snapshot names include the platform suffix; baselines are generated on the platform that runs CI
  (linux) plus locally (win32). E9-S4 AC-1 counts the 9 × 2 images per platform.
