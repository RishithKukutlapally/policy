# Evaluator Report — PolicyForge

**Phase:** `/evaluate` — **re-verification pass** (independent, sceptical mode)
**Date:** 2026-09-30
**Scope:** sprint contracts `S1`–`S4` (`sprint-contracts/S*.json`), all 30 `api_checks`, the 20 project guard
hooks, static gates, money and NFR spot-checks
**Verification mode:** `local` — API `uvicorn src.main:app` on `127.0.0.1:8011`, run against a throw-away
database under `POLICYFORGE_BUSINESS_DATE=2027-06-10`
**Prior run:** returned `VERDICT: FAIL` on two substrate defects (guard hooks failed open; 10 sprint-contract
checks drifted from the specs). Both were claimed fixed. This pass re-verifies them from scratch and carries
forward the earlier run's evidence where that evidence was not invalidated by the fixes.
**Method:** every number in sections 2–6 was produced by a command run during *this* pass. Nothing was taken
from a build report, a generator summary, or from reading source for reassurance. Section 7 is explicitly
labelled as carried forward.

---

## 1. Summary

| Sprint | `api_checks` | Passed | Failed |
|--------|--------------|--------|--------|
| S1 | 7 | **7** | 0 |
| S2 | 8 | **8** | 0 |
| S3 | 7 | **7** | 0 |
| S4 | 8 | **8** | 0 |
| **Total** | **30** | **30** | **0** |

| Gate | Result |
|------|--------|
| **Failure 1 — project guard hooks** | **FIXED** — self-test 58/58, exit 0; hooks block with exit 2 (§2) |
| **Failure 2 — sprint-contract drift** | **FIXED** — 30/30 `api_checks` pass verbatim from the JSON (§4) |
| Backend tests | **PASS** — `697 passed, 1 warning in 56.53s`, exit 0 |
| Coverage | **PASS** — `TOTAL 4107 statements, 58 missed, 99 %` (floor 80 %) |
| `alembic heads` | **PASS** — `0006 (head)`, exactly one head |
| Contract schema validation (all four) | **PASS** — 4/4 VALID incl. `approved`, `notes` |
| Performance budgets | **PASS** — all four budgeted endpoints, worst 53 ms against a 2000 ms budget |
| No PII in logs (NFR-03) | **PASS** — 0 matches in 96 log lines of this run |
| Playwright **MCP** browser driving / `design_checks` | **NOT VERIFIED** — server still unreachable (§6) |

---

## 2. Failure 1 re-verified — the guard hooks now block

### 2.1 The mechanism

`.claude/hooks/package.json` exists and contains `"type": "commonjs"`. Node resolves module type from the
nearest ancestor `package.json`, so this confines the root `package.json`'s `"type": "module"` (still present,
still needed by `scripts/start.mjs` and the Playwright config) and the 20 CommonJS hooks load again. No file
was renamed to `.cjs`, and `.claude/settings.json` paths are unchanged — a strictly smaller fix than the one
the previous report proposed.

### 2.2 Self-test

```
$ node .claude/hooks/tests/run-hook-tests.js
...
PASS premium-precision-check.js       block backend\src\domain\rates.py  [scientific float literal]

58/58 passed
exit=0
```

58/58, exit **0**. The previous run's `ReferenceError: require is not defined in ES module scope` is gone.

### 2.3 All 20 hooks load

Every `.claude/hooks/*.js` was invoked with a neutral payload and grepped for
`require is not defined` / `Cannot use import statement` / `MODULE_NOT_FOUND`. **0 of 20** produced a load
error; all 20 exited 0 on a payload they do not govern:

`append-only-repository-check`, `check-architecture`, `check-file-length`, `check-function-length`,
`detect-secrets`, `enforce-length-pre`, `lint-on-save`, `pii-redaction-check`, `policy-immutability-check`,
`pre-commit-gate`, `premium-precision-check`, `protect-env`, `require-review`, `scope-directory`,
`shell-immutability-check`, `sprint-contract-gate`, `task-completed`, `teammate-idle-check`, `track-writes`,
`typecheck`.

### 2.4 Three hooks driven with real violating payloads — exit 2 + `BLOCKED` on stderr

A self-test passing is not proof that the hook blocks a live tool call, so each of the three
domain-invariant guards named in CLAUDE.md was fed a hand-built `PreToolUse` payload on stdin. Verbatim
output:

**`premium-precision-check.js`** (NFR-01) — a `float` annotation and a bare float literal in a money
expression, written to `backend/src/service/premium_service.py`:

```
BLOCKED by premium-precision-check (NFR-01): backend/src/service/premium_service.py
  line 1: float type annotation — def compute(base: float) -> float:
  line 2: bare float literal in money expression — premium = base * 1.05
Fix: Use decimal.Decimal built from strings (Decimal("0.05")), Numeric columns, and quantize(...)
>>> EXIT=2
```

**`pii-redaction-check.js`** (NFR-03) — an Aadhaar value passed into a log call:

```
BLOCKED by pii-redaction-check (NFR-03): backend/src/service/kyc_service.py
  line 7: PII identifier in log call — logger.info("kyc received aadhaar=%s", kyc.aadhaar)
Fix: Never log Aadhaar, PAN or health declarations. Log an opaque reference ... or wrap with mask_pii(...)
>>> EXIT=2
```

**`append-only-repository-check.js`** (NFR-02) — a SQLAlchemy `update()` against the append-only
`Endorsement` model:

```
BLOCKED by append-only-repository-check (NFR-02): backend/src/repository/endorsement_repository.py
  line 8: SQLAlchemy update()/delete() on append-only model — session.execute(update(Endorsement)...)
Fix: Append a new row instead (RuleSetVersion, ..., Endorsement, PremiumPayment, Refund, AuditRecord)
>>> EXIT=2
```

**Clean counterpart payloads** (Decimal + `quantize`; the redacting logger from `src.lib` with only an
`application_id`; `session.add(row)`) were fed to the same three hooks: **exit 0, no output** in all three
cases. So the hooks discriminate — they are not blocking indiscriminately.

**Exit codes observed: 2 on every violation, 0 on every clean payload.** Exit 2 is the blocking code Claude
Code feeds back to the model, so the guards now fail *closed*.

### 2.5 Unsolicited live confirmation

Mid-evaluation, `scope-directory.js` blocked one of my own tool calls — a scratch file write outside the
project root — with `BLOCKED: Write outside project directory: ...\scratchpad\replay.py`. That is a hook
intercepting a real, unplanned tool call in this session, which is stronger evidence than any payload I
could construct.

### 2.6 CI wiring

`.gitlab-ci.yml:58-62` runs the self-test as its own job, so a regression of this defect fails the pipeline:

```yaml
hook-selftest:
  stage: test
  image: node:22
  script:
    - node .claude/hooks/tests/run-hook-tests.js  # guard hooks (NFR-01/02/03/05) block/allow cases
```

**Failure 1 is genuinely fixed.**

---

## 3. Static gates re-checked

| Command | Output |
|---------|--------|
| `uv run alembic heads` | `0006 (head)` — **exactly one head** |
| `uv run pytest -q -o addopts=""` | **`697 passed, 1 warning in 56.53s`**, exit 0 |
| coverage (from the same suite's `--cov` run) | `TOTAL 4107 statements, 58 missed, **99 %**`, `coverage.xml` rewritten |
| contract schema validation (ajv, draft-07) | `S1 VALID · S2 VALID · S3 VALID · S4 VALID`, exit 0 |

Note on the test count: `pyproject.toml:54` already sets `addopts = "-q ..."`, so a bare `pytest -q` becomes
`-qq` and suppresses the summary line entirely. The count above comes from a re-run with `-o addopts=""`.
Anyone scripting this gate should not rely on `pytest -q` printing a count.

Schema validation also confirms the extension the fix depended on: all four contracts carry
`approved: true` and a `notes` string and validate under `additionalProperties: false`. The optional
`business_date` property is now *allowed* by the schema but **is not set in any of the four contracts** — so
the business date the S4 checks need (§4.2) is still implicit, not declared. See §5.

---

## 4. Failure 2 re-verified — all 30 `api_checks` replayed verbatim

### 4.1 Method

A driver script parsed `sprint-contracts/S1..S4.json` and issued **every** `api_checks` entry with its
`method`, `path`, `headers` and `body` taken **verbatim from the JSON** — no hand-edited request bodies this
time. The recorded `expected_status` was compared exactly, and every `expected_body` was checked as a
recursive subset of the real response. Only `{{placeholder}}` tokens were substituted, with prerequisites
created through the API or taken from the seed.

Environment: a fresh `backend/policyforge-reval.db` created with `uv run alembic upgrade head` (0001→0006) and
seeded with `uv run python -m src.seed`, served under `POLICYFORGE_BUSINESS_DATE=2027-06-10`. The committed
`backend/policyforge.db` was never opened — its md5 was `ed9312b1a9e1150ea95c48d52b38cc8f` before and after.
Health check passed on the first attempt (200 in 13.3 ms).

Seed output, this run — identical to the previous pass, so the fixture is deterministic:

```json
{"event": "seed_portfolio_completed", "inserted": true, "products": 3, "quotes": 25, "applications": 25,
 "applications_by_decision": {"AUTO_BIND": 21, "DECLINE": 1, "MANUAL_REVIEW": 3},
 "policies": 7, "policies_by_status": {"ACTIVE": 3, "CANCELLED": 1, "ENDORSED": 1, "LAPSED": 1, "RENEWED": 1},
 "endorsements": 1, "payments": 7, "refunds": 1}
```

21/25 = **84 % auto-bind**, over the ≥ 70 % the S4 notes require.

### 4.2 Results — 30/30

| Check | Method + path (after substitution) | Expected | Actual | Key fields observed |
|---|---|---|---|---|
| S1-API-01 | `GET /health` | 200 `{status:ok}` | **200** | `{"status":"ok"}`, 4.5 ms |
| S1-API-02 | `GET /api/products` CUSTOMER | 200 | **200** | `TERM_LIFE/1`, `MOTOR/1`, `HOUSEHOLD/1`, all `currency INR` |
| S1-API-03 | `GET /api/products` no headers | 401 | **401** | `UNAUTHENTICATED` — "Header X-Actor-Id is required" |
| S1-API-04 | `POST /api/products/MOTOR/versions` CUSTOMER | 403 | **403** | `FORBIDDEN` — "Role CUSTOMER is not allowed on this route" |
| S1-API-05 | `GET /api/products/MOTOR/versions` ADMIN | 200 | **200** | `version 1, revision 1, PUBLISHED, is_active true, actor_id SYSTEM`, full rule body |
| S1-API-06 | `POST /api/products/MOTOR/versions/1/publish` | 409 `VERSION_IMMUTABLE` | **409** | code matched — "MOTOR v1 is PUBLISHED and can no longer change" |
| S1-API-07 | `GET /api/products/UNKNOWN/versions` | 404 `NOT_FOUND` | **404** | code matched — "unknown product 'UNKNOWN'" |
| S2-API-01 | `POST /api/quotes` (`vehicle_age_years`) | 201 `premium 14322.00`, `rule_version 1` | **201** | `premium "14322.00"`, `rule_version 1`, `sum_insured "500000.00"` — both expected keys matched |
| S2-API-02 | `POST /api/quotes` sum_insured 50000 | 422 `VALIDATION_ERROR` | **422** | `details [{sum_insured, OUT_OF_RANGE}]` |
| S2-API-03 | `POST /api/applications` (kyc **with** `address`) | 201 | **201** | `status AUTO_BIND`, `status_history [SUBMITTED, UNDERWRITING, AUTO_BIND]`, `aadhaar_masked XXXX-XXXX-0001`, `pan_masked XXXXX0001X` |
| S2-API-04 | `GET /api/underwriting/queue?status=MANUAL_REVIEW` | 200 | **200** | 3 cases, reason codes `MO-UW-002`, `HH-UW-002`, `TL-UW-003` with descriptions |
| S2-API-05 | `POST .../{app}/decision` `MO-UW-900` | 200 | **200** | new decision `decided_by uw-001`, `reason_codes [MO-UW-900]`, comment stored, status → `AUTO_BIND` |
| S2-API-06 | `POST .../{declined}/override` `TL-UW-901` | 200 | **200** | `from_status DECLINED → to_status AUTO_BIND`, `reason_code TL-UW-901`, `actor_id admin-001`, original decision row retained |
| S2-API-07 | `POST .../{app}/override` as UNDERWRITER | 403 `FORBIDDEN` | **403** | code matched — "Role UNDERWRITER is not allowed on this route" |
| S2-API-08 | `GET /api/quotes/{id}/reprice` | 200 `stored_premium/recomputed_premium 14322.00`, `matches true` | **200** | `{stored_premium "14322.00", recomputed_premium "14322.00", matches true, rule_version 1}` — all three expected keys matched |
| S3-API-01 | `POST /api/applications/{auto_bind}/issue` | 201 `status ACTIVE` | **201** | `MO-2027-000001`, `ACTIVE`, `sum_insured 500000.00`, `premium 14322.00`, `effective 2027-06-10`, `expiry 2028-06-09` |
| S3-API-02 | `POST /api/applications/{manual_review}/issue` | 409 `INVALID_APPLICATION_STATE` | **409** | code matched, `details {current: MANUAL_REVIEW, required: AUTO_BIND}` (see §4.3) |
| S3-API-03 | `GET /api/policies` | 200 | **200** | 7 policies for `cust-001`, each with status + `premium_due_date`; 8.5 ms |
| S3-API-04 | `GET /api/policies/{policy}` as `cust-002` | 404 `NOT_FOUND` | **404** | code matched — "Policy not found", no existence leak |
| S3-API-05 | `POST .../endorsements` `{type, new_sum_insured}` | 201 | **201** | `endorsement_id` issued, `before {500000.00, 14322.00}` → `after {600000.00, 17186.40}`, `premium_delta 2864.40`, policy → `ENDORSED` |
| S3-API-06 | `POST .../endorsements?preview=true` | 200 | **200** | `preview true`, `premium_delta 2864.40`, `endorsement_id null`, `created_at null`, `policy null` — **nothing persisted** |
| S3-API-07 | `POST .../endorsements` on the CANCELLED policy | 409 `INVALID_POLICY_STATE` | **409** | code matched, `details {current: CANCELLED, target: ENDORSED}` (AC-10) |
| S4-API-01 | `GET /api/policies/{policy}/renewal` | 200 | **200** | `renewable true`, `renewal_premium 23017.50`, `due_date 2027-07-01`, `grace_end_date 2027-07-31`, `renewal_window_opens 2027-05-31`, `paid false` |
| S4-API-02 | `POST .../payments` `amount 23017.50` | 201 | **201** | `payment_id`, `amount 23017.50`, `actor_id cust-001`, `paid_at 2027-06-10` — amount now matches the premium due |
| S4-API-03 | `POST .../renew` | 201 `status ACTIVE` | **201** | successor `MO-2027-000002`, `ACTIVE`, `effective 2027-07-01`, `expiry 2028-06-30`, `previous_policy_number MO-2026-000003` |
| S4-API-04 | `POST /api/admin/end-of-day` `as_of 2027-02-15` | 200 | **200** | `{renewed 0, lapsed 0, in_grace 0, not_renewable 0, failed 0}` |
| S4-API-05 | same request again | 200 `{renewed 0, lapsed 0}` | **200** | `renewed 0, lapsed 0` — expected body matched (see §5 for the caveat) |
| S4-API-06 | `GET .../cancellation-preview?date=2026-10-01` | 200 | **200** | `PRO_RATA`, `premium_paid 2073.60`, `term_days 365`, `days_elapsed 92`, `unused_days 273`, `gross_refund 1550.94`, `admin_fee 250.00`, `amount 1300.94` |
| S4-API-07 | `POST .../cancel` `2026-07-05` | **200** `status CANCELLED` | **200** | `status CANCELLED`, `refund_type FREE_LOOK`, `days_elapsed 4`, `admin_fee 0.00`, `amount 21483.00`, `actor_id cust-001` — the contract's 200 matches `specs/renewal-cancellation_spec.md:152` |
| S4-API-08 | `GET /api/admin/portfolio?as_of=2026-10-15` | 200 | **200** | `active_by_product {TERM_LIFE 1, MOTOR 2, HOUSEHOLD 1}`, `sum_insured_by_product`, `premium_collected 98841.60`, `refunds_paid 19530.00`, `renewal_pipeline`, `lapse_forecast` |

All eight drift items the previous run listed are corrected in the JSON and confirmed executable:
`vehicle_age_years`, `kyc.address`, reason code `TL-UW-901` on the TERM_LIFE declined case,
`{type, new_sum_insured}` / `{type, address}` endorsement bodies, the `stored_premium`/`recomputed_premium`/
`matches` reprice keys, payment `23017.50`, cancellation dates `2026-10-01` and `2026-07-05`, and cancel
expecting **200**. **No application code was needed, and none changed.**

### 4.3 One honest wrinkle in the replay (not a contract or code defect)

My first pass scored 29/30: `S3-API-02` returned **404** rather than 409, because I had bound
`{{manual_review_application_id}}` to a *seeded* MANUAL_REVIEW application that belongs to a different
customer, while the check sends `X-Actor-Id: cust-001`. Ownership scoping correctly refuses to disclose it.
I then created a `cust-001`-owned MANUAL_REVIEW application through the API (a MOTOR quote with
`vehicle_age_years: 12` → `MO-UW-002`) and re-ran the check **verbatim**:

```
POST /api/applications/2c861a90-48a1-48e8-93d7-ee5e4275a38e/issue   HTTP=409
{"error":{"code":"INVALID_APPLICATION_STATE","message":"Only an AUTO_BIND application can be issued",
 "details":{"current":"MANUAL_REVIEW","required":"AUTO_BIND"}}}
```

That is a **PASS**, so the tally is 30/30. The 404 was my prerequisite choice, not a defect — but it is a
real trap for whoever automates this gate, and it is recorded in §5 rather than buried.

### 4.4 Performance budgets — measured this pass

| Endpoint | Budget | Measured |
|---|---|---|
| `GET /health` (S1, S4) | 1000 ms | **4.5 ms** |
| `POST /api/quotes` (S2) | 2000 ms | **33.1 ms** |
| `GET /api/policies` (S3) | 2000 ms | **8.5 ms** |
| `GET /api/admin/portfolio` (S4) | 2000 ms | **53.2 ms** |

### 4.5 Money and PII, re-confirmed on live responses

- **MOTOR golden premium.** `14322.00` appeared identically on `POST /api/quotes`, on reprice as both
  `stored_premium` and `recomputed_premium` with `matches: true`, and as the issued policy's `premium`.
- **Household pro-rata refund.** `2073.60 × 273 ÷ 365 = 1550.94`, `− 250.00 = 1300.94`; the API returned
  `gross_refund "1550.94"`, `admin_fee "250.00"`, `amount "1300.94"`.
- **Free-look refund.** `days_elapsed 4`, `admin_fee "0.00"`, `amount "21483.00"` — the full premium, no fee,
  exactly as a free-look cancellation should behave.
- Every money field in every response is a JSON **string**, never a number. No float drift anywhere.
- **NFR-03:** the 96 log lines this run produced were scanned for `9999[0-9]{8}`, `AAAAA[0-9]{4}A`,
  `"aadhaar"` and `health_declaration` → **0 matches**, even though Aadhaar `999900000001` / PAN `AAAAA0001A`
  were posted twice. 46 lines carry a `correlation_id` (NFR/AC-23).

---

## 5. Not verified, and caveats — read this before trusting the gate

1. **Playwright MCP browser driving, and therefore every `design_checks` block, remains UNSCORED.** The
   server declared in `.mcp.json` (`npx -y @playwright/mcp@0.0.83 --headless`) was again not connectable
   (`CONNECT_TIMEOUT`); no `mcp__playwright__*` tool was surfaced to this run. **No screenshots exist under
   `specs/reviews/playwright-mcp/` — the directory has not been created.** Consequently
   `visual_hierarchy`, `accessibility`, `responsiveness` and `interaction_feedback` in all four contracts
   are **neither passed nor failed**; they are unmeasured. Stated plainly: this report does **not** certify
   the design criteria. The only visual evidence in the repo is the 18 committed snapshots carried forward
   in §7, which is weaker than a scored rubric.
2. **The literal `playwright_checks` step lists were not replayed**, for the same reason — the
   `data-testid` selectors the contracts name (`role-switcher`, `quote-premium`, `endorsement-delta`,
   `refund-preview`, `portfolio-cards`, …) were not driven selector-by-selector this pass.
3. **`S4-API-05` proves idempotency only trivially.** Both runs use `as_of 2027-02-15`, where the *first*
   run already reports `{renewed 0, lapsed 0}` — so `{renewed 0, lapsed 0}` on the second run would also
   hold if the logic were absent. Genuine idempotency was proved in the earlier pass on a date that does
   something (§7). The contract would be stronger with an `as_of` that actually transitions policies.
4. **No contract declares its `business_date`.** The schema now permits `business_date`, but none of the
   four contracts sets it, and `S4-API-01/02/03` are only reachable inside the renewal window. This pass
   supplied `POLICYFORGE_BUSINESS_DATE=2027-06-10` out of band. An unattended runner given only the JSON
   would fail those three checks.
5. **Four `{{placeholder}}` tokens are unresolvable from the JSON alone** —
   `{{application_id}}`, `{{declined_application_id}}`, `{{manual_review_application_id}}`,
   `{{free_look_policy_number}}` — and one of them has a non-obvious constraint: the target must be owned by
   `cust-001`, or the check returns 404 instead of the expected status (§4.3). The contracts do not say this.
6. **Frontend gates, the Playwright e2e suite and the backend lint/type/import gates were not re-run** this
   pass; the fixes touched only `.claude/hooks/package.json` and three contract JSON files, neither of which
   any of those gates reads. Their results are carried forward in §7 and are labelled as such.
7. **Git state.** Instructed not to run git, so I cannot confirm what is committed — only what is on disk.
8. **`GET /api/underwriting/queue?status=DECLINED` requires ADMIN**, not UNDERWRITER (`FORBIDDEN` —
   "Role UNDERWRITER may only list MANUAL_REVIEW cases"), and `status=AUTO_BIND` is rejected with
   `UNKNOWN_CODE`. Discovered while building prerequisites; consistent with the spec, but no contract
   covers it.

---

## 6. Carried forward from the previous run (2026-09-30, earlier pass)

These were verified by command in the earlier pass and are **not** re-measured here, because the two fixes
(`.claude/hooks/package.json`, three contract JSON files) cannot affect them. Flagged so no one mistakes
them for fresh measurements.

| Gate | Result (earlier pass) |
|------|------------------------|
| `uv run ruff check .` | `All checks passed!` — 0 findings |
| `uv run mypy src/` | `Success: no issues found in 93 source files` |
| `uv run lint-imports` | `Analyzed 121 files, 715 dependencies` · **`Contracts: 5 kept, 0 broken`** |
| Frontend `npm run lint` / `npm run typecheck` | both clean, 0 findings / 0 errors |
| Frontend `npm test -- --run` | `Test Files 11 passed (11)` · `Tests 98 passed (98)` |
| Frontend `npm run build` | Vite 6.4.3, 117 modules, `index-CABCbGtd.js 275.44 kB` (gzip 80.26 kB), 1.74 s |
| Playwright e2e `npm run e2e` | **32 passed** (16 specs × desktop 1280×800 + mobile 390×844), 0 failed, 0 flaky |
| Committed snapshots | **18** (9 screens × 2 projects, AC-24); **0 rewritten** by that run — all baselines matched |
| `GET /health` | 200 in **12.8 ms** (this pass independently measured 4.5 ms) |
| Money recomputed independently with `decimal` from `backend/policy_rules/*/v1.json` | `500000.00 × 0.0310 × 1.00 × 1.10 × 1.05 × 0.80 = 14322.00` exact; `2073.60 × 273 ÷ 365 − 250.00 = 1300.94` exact |
| PII in logs | 0 matches across that run's 102 log lines |
| Security headers (NFR-06) | `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `content-security-policy: default-src 'self'`, `x-correlation-id` |
| End-of-day idempotency (AC-18), non-trivially | `as_of 2027-08-05`: 1st run `lapsed 2 ["MO-2026-000001","TL-2026-000001"]`; 2nd run `lapsed 0, renewed 0` |
| Seed | synthetic only (`Test Customer NN`, Aadhaar `9999…`, PAN `AAAAA00NNA`); re-run reported `inserted: false`; **21/25 = 84 % auto-bind** (this pass reproduced 84 %) |
| Append-only (NFR-02) | republish → 409 `VERSION_IMMUTABLE`; DECLINE row retained alongside the override row; second end-of-day added nothing |
| Auth (NFR-04 / AC-22) | 401 with no headers; CUSTOMER → 403 on the ADMIN version route; UNDERWRITER → 403 on the override route; `actor_id` on override / decision / payment / refund rows |

---

## 7. Verdict reasoning

Both previously reported failures are fixed, and both fixes were verified by execution rather than by
reading the diff:

1. **Guard hooks.** `.claude/hooks/package.json` with `"type": "commonjs"` restores all 20 CommonJS hooks
   under a root `package.json` that is still `"type": "module"`. The self-test is **58/58, exit 0**; all 20
   hooks load without error; and three separate domain-invariant guards returned **exit 2 with a `BLOCKED`
   reason on stderr** for real violating payloads while returning **exit 0** for clean ones. A fourth hook,
   `scope-directory.js`, blocked one of my own tool calls unprompted. The guards fail **closed** now.
   `.gitlab-ci.yml:58-62` pins this with a `hook-selftest` job.
2. **Contract drift.** All **30/30** `api_checks` across `S1`–`S4` now pass when replayed **verbatim from
   the JSON**, against a freshly migrated and seeded throw-away database. All eight drift items are
   corrected in `sprint-contracts/S2.json`, `S3.json` and `S4.json`, and no application code changed —
   consistent with project rule 2, since in every case the implementation had matched
   `docs/conventions.md` / `specs/*_spec.md` all along.

Supporting gates are green: `697 passed` with 99 % line coverage, a single Alembic head (`0006`), 4/4
contracts valid against the extended schema, all four performance budgets met by a factor of 20 or more,
exact `Decimal` arithmetic on three money figures, and 0 PII across 96 log lines.

The one criterion I cannot certify is the `design_checks` rubric: the Playwright MCP server is still
unreachable, so those blocks are **unscored**, and no screenshots were captured. I am calling this a PASS
rather than a FAIL because the design criteria were never scored in either run — they are a
tooling gap that is unchanged by this sprint, not a regression and not a failing check — whereas both
defects that actually caused the previous FAIL are now demonstrably fixed. That gap should be closed
before the design criteria are claimed as met; it is recorded as item 1 of §5 so it is not quietly lost.

The app was stopped (nothing listening on 8011; `/health` unreachable), the temporary
`backend/policyforge-reval.db` was deleted, and `backend/policyforge.db` was verified byte-identical
(md5 `ed9312b1a9e1150ea95c48d52b38cc8f`) before and after. The only project file this pass wrote is this
report, plus `backend/coverage.xml`, which the pytest coverage gate rewrites by design.

VERDICT: PASS
