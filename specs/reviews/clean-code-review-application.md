# Clean Code Review — chore/policyforge-substrate — 2026-09-30

Scope: `backend/src/**`, `backend/tests/**`, `frontend/src/**`, `e2e/**`, `scripts/**` (all four sprints).
Earlier substrate/script findings (`clean-code-review-substrate.md`, `clean-code-review-scripts.md`) are not repeated.

Counts: high 1 · medium 8 · low 4

Tool results: ruff ✓ · mypy ✓ (91 files, no issues) · lint-imports ✓ (**5/5 contracts KEPT**, 119 files /
693 dependencies analysed) · arch tests ✓ · eslint ✓ · tsc ✓

## What is genuinely good

Worth recording, because it is the bulk of the work and it holds up:

- **Layering is real, not aspirational.** All five import-linter contracts pass, including the two strict ones
  ("API goes through services", "types and domain stay pure"). `src/domain/**` imports nothing but stdlib
  (`re`, `datetime`, `decimal`, `types.MappingProxyType`) plus `src.types` — no FastAPI, no SQLAlchemy, no
  logging, no clock. Dates really are passed in (`refund_rules.refund_amount`, `endorsement_rules`).
- **One clock.** `date.today()` appears exactly once in the whole backend, inside
  `backend/src/lib/clock.py:33`, behind `today()` (DEC-012). No layer bypasses it.
- **Money discipline in the domain is correct.** `premium_calculator.py:146`, `refund_rules.py:47,50` and
  `endorsement_rules.py:116` each quantize exactly once, at the end, `ROUND_HALF_UP`; the pro-rata helper
  `refund_rules._pro_rata:19` is explicitly documented as returning an *unrounded* value.
- **Premium AC tests are honest.** `backend/tests/ac/test_ac01_premium.py:49-66` asserts hard-coded golden
  amounts (`14322.00`, `3536.30`, `9900.00`, `3000.63`) loaded from the real `policy_rules/*/v1.json`, never
  recomputing the formula the implementation uses, and additionally asserts `exponent == -2` and determinism
  over 1000 calls. This is the single most important test in the codebase and it is written properly.
- **Endpoint surface matches `docs/conventions.md`** method-for-method and path-for-path (all 23 routes),
  with `/health` the only un-prefixed route and an architecture test pinning that fact.
- **Enums match conventions exactly** — all nine documented enums, values verbatim.
- **Synthetic-data rule is clean.** Every Aadhaar in seeds, fixtures and tests starts `9999`; every PAN is
  `AAAAA####A`; the only other PAN-shaped strings are the expected masks `XXXXX0001X`.
- **No timing hacks and no typing escapes.** Zero `time.sleep` / `waitForTimeout` in project code; zero
  `any`, zero `@ts-ignore` in `frontend/src` and `e2e` — the only two `as unknown as` casts are in test
  harness plumbing (`frontend/src/test/setup.ts:22`, `__tests__/apiClient.test.ts:24`) and are legitimate.
- **E2E is traceable**: every Playwright title carries its `AC-NN`, and `playwright-report/`, `test-results/`
  are gitignored rather than committed.
- **The money architecture test survived the models split** — `MONEY_GLOBS` in
  `backend/tests/architecture/test_no_float_in_money.py:18` was correctly updated to
  `repository/models/*.py`, so the package split is still covered (but see [CC-009]).

## High

- [CC-001] `backend/src/service/cancellation_service.py:187-190` — the refund **breakdown re-implements the
  domain pro-rata maths in the service layer and rounds an intermediate**, against the money rule stated in
  `docs/conventions.md:280` ("quantized to `0.01` `ROUND_HALF_UP` **once at the end**") and NFR-01.
  `gross` is quantized, then `fee = min(admin_fee, gross)` is quantized again, and the two are presented next
  to an `amount` that came from `refund_rules.refund_amount` — a *different* computation
  (`quantize(premium × unused / total − admin_fee)`). Today the two agree only because every rule file
  `admin_fee` happens to be exact-cent; an `admin_fee` of `250.005`, or any reuse of `gross` as a real
  monetary figure, makes `gross_refund − admin_fee ≠ amount` with no test to catch it, and the duplicated
  formula is free to drift from `refund_rules._pro_rata:19`.
  **Fix:** delete the service-side arithmetic. Have `refund_rules.refund_amount` return the full breakdown
  (`gross`, `fee`, `amount`) computed at full precision and quantized once at the end, and let
  `_breakdown` map that value object straight onto `RefundBreakdownView`. Money maths belongs in `src/domain`.

## Medium

- [CC-002] `backend/src/service/endorsement_service.py:207-213`, `policy_service.py:136-140` and `:197-200`,
  `policy_query_service.py:187` — four byte-identical copies of the "CUSTOMER must own it, else 404" guard
  (`actor.role is ActorRole.CUSTOMER and X.customer_id != actor.actor_id` then `NotFoundError`), while
  `cancellation_service.py:91,110` and `payment_service.py:75` correctly call the shared `owned_policy(...)`.
  A no-existence-leak rule (`docs/conventions.md:147`) spread over six sites is one edit away from a leak.
  **Fix:** call the existing `owned_policy(...)` at the three policy sites, and add a sibling
  `owned_application(...)` for `policy_service.py:136` and `application_service.py:264`.
- [CC-003] `backend/src/service/renewal_service.py:79-99` — the cross-cutting guards `owned_policy`,
  `assert_live` and `advance_inputs` **live inside a sibling use-case service** and are imported from it by
  `cancellation_service.py:30` and `payment_service.py:21`. Cancellation has no business depending on
  renewal; this is an SRP / module-placement problem that will spread as more services need the guards.
  **Fix:** move the three helpers to a new `src/service/policy_access.py` and import from there.
- [CC-004] `backend/src/service/endorsement_service.py` — **303 lines, over the 300-line ceiling** in
  `CLAUDE.md`. It is the only file in the codebase that breaches it (next largest production file is
  `underwriting_service.py` at 296).
  **Fix:** move the change-shape validation (the blank/range/enum field rules the module docstring describes)
  into `src/domain/endorsement_rules.py`, where the rest of the endorsement rules already live.
- [CC-005] `backend/src/service/cancellation_service.py:107` `_cancel` (62 lines),
  `policy_service.py:133` `_issue_once` (55), `application_service.py:207` `submit` (53) — the only three
  functions over the 50-line limit. All three are long because of flat keyword-argument mapping, not branching.
  **Fix:** for `_cancel`, replace the 18-line `RefundView(...)` literal at `:153-167` with a
  `RefundView.from_row(refund)` classmethod; apply the same view-mapping extraction to the other two.
- [CC-006] `backend/src/api/schemas/endorsements.py:27-28` — `share_percent: Any` and
  `new_sum_insured: Any`. `new_sum_insured` is **money**, and typing it `Any` removes the one place a money
  string could be shape-checked at the boundary; it also makes `changes()` at `:30` return `dict[str, Any]`
  with no contract. mypy passes only because `Any` silences it.
  **Fix:** type them `str | None` (money as a two-decimal string per `docs/conventions.md:146`) and
  `int | str | None` for `share_percent`, keeping the "report every field error at once" behaviour in the
  service. If a deliberately loose type is needed to raise `422 MONEY_MUST_BE_STRING` rather than a Pydantic
  error, say so in the docstring — right now nothing explains the `Any`.
- [CC-007] `backend/src/api/routers/admin.py:1-27` — dead code whose **own removal condition has been met**:
  the docstring says "Remove the probe when those endpoints exist", and both named endpoints
  (`POST /api/admin/end-of-day`, `GET /api/admin/portfolio`) now exist in `end_of_day.py` and `portfolio.py`.
  `GET /api/admin/ping` is also absent from the authoritative endpoint table, which states at
  `docs/conventions.md:183` that no other paths exist. Reported here as dead code / drift; the exposure angle
  is owned by `security-reviewer` — cross-reference **APP-I06** in `specs/reviews/security-review-application.md`.
  **Fix:** delete the router and repoint `backend/tests/ac/test_ac22_auth_boundary.py:14` `PROBE_PATH` at a
  real ADMIN route (`/api/admin/portfolio`), which exercises the same 401/403/200 boundary.
- [CC-008] `docs/conventions.md:67,74,76` — the conventions table names three modules that **do not exist**:
  `src/repository/models.py` (now the `src/repository/models/` package: `policies.py`, `lifecycle.py`,
  `quotes.py`, `underwriting.py`, `rules.py`, `audit.py`, `_common.py`), `src/types/values.py` (Money helpers,
  never created) and `src/repository/append_only.py` (append-only base, never created). Spec-is-truth cuts
  both ways: a maintainer following the table looks for files that are not there.
  **Fix:** update line 67 to the `models/` package, and either delete lines 74/76 or create the two modules.
  Creating `src/types/values.py` would also resolve [CC-011].
- [CC-009] `backend/tests/architecture/test_no_float_in_money.py:14-19` — `MONEY_GLOBS` covers
  `domain/premium*`, `domain/refund*`, `domain/endorsement*` and `repository/models/*` but **no service
  module**, even though `cancellation_service`, `quote_service`, `portfolio_service`, `payment_service` and
  `endorsement_service` all do `Decimal` arithmetic. That blind spot is exactly where [CC-001] hid.
  **Fix:** add `service/*_service.py` plus `domain/renewal_rules.py` and `domain/term_days.py` to `MONEY_GLOBS`.

## Low

- [CC-010] `backend/src/service/application_service.py:196` `_rule_set`, `quote_service.py:235` `_rule_set`
  and `cancellation_service.py:215` `_recorded_rule_set` — three variants of "turn a `RuleSetVersion` row
  into a `RuleSet`". **Fix:** one `rule_set_of(row)` helper next to the guards from [CC-003]; keep
  `_recorded_rule_set` extra "latest PUBLISHED revision" lookup as a thin wrapper over it.
- [CC-011] `backend/src/api/schemas/quotes.py:22`, `service/quote_service.py:113`,
  `service/endorsement_service.py:73`, `service/portfolio_service.py:43` — the same
  `_CENT` + `quantize(..., ROUND_HALF_UP)` money helper written four times, in two spellings (positional and
  `rounding=`). **Fix:** one `money()` helper, ideally in the `src/types/values.py` the conventions already
  promise (see [CC-008]).
- [CC-012] `frontend/src/app/routes.tsx:24,26,28,35,45` — stale scaffolding comments
  ("the Product Catalog Manager **replaces its placeholder**") describing a migration that is finished; no
  `Placeholder` component exists anywhere in `frontend/src`. They read as open work.
  **Fix:** reduce each to the story id that owns the route, e.g. `// E2-S4 — Product Catalog Manager`.
- [CC-013] `backend/tests/ac/test_ac21_health.py:51-56` `test_ac21_health_responds_within_one_second` —
  asserts wall-clock `elapsed < 1.0`. Same class of fragility as a `sleep`: it will flake on a loaded CI
  runner and the failure will look like a product regression.
  **Fix:** keep the NFR-07 budget as a separate perf check (`performance-auditor`), and in the AC suite assert
  the property that actually makes `/health` fast — no DB session — which
  `test_ac21_health_does_no_database_work:59` already does well by monkeypatching `SessionLocal`.

## Notes

- `docs/conventions.md:61` omits `RuleSetStatus` from the list of enums in `src/types/enums.py`, although the
  enum exists at `enums.py:89` and is used for rule-version status. Folded into [CC-008].
- The twelve AC tests whose only assertion is a status code are almost all **role-guard** tests
  (401/403/404), where the status *is* the acceptance criterion — correctly written, not a finding. The one
  exception worth a future tidy is `test_ac12_quote_errors.py:70`, which asserts `404` but not the
  `NOT_FOUND` error code from the documented envelope.

VERDICT: CHANGES_REQUIRED
