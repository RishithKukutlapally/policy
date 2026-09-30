# Security Review — PolicyForge application code (all four sprints) — 2026-09-30

Scope: `backend/src/**`, `backend/migrations/**`, `frontend/src/**`, `backend/src/seed.py` +
`seed_data/**`, `e2e/**` config, `scripts/**`, `.gitlab-ci.yml`, `.claude/hooks/**`.
Standard applied: `CLAUDE.md` + `docs/conventions.md` (NFR-01…05).
Earlier substrate findings (`security-review-substrate.md`, `security-review-scripts.md`) are not
repeated; no application file reintroduces them.

## Summary
- BLOCK findings: 0
- WARN findings: 3
- INFO findings: 7
- Overall verdict: WARN

## BLOCK Findings

None. No exploitable injection, auth bypass, cross-tenant read, secret exposure or mutable
append-only path was found.

## WARN Findings

### [APP-W01] Audit `detail` PII guard inspects key names only, so a free-text comment is stored and returned verbatim
File: `backend/src/service/audit_service.py:27` (`_reject_pii`), written from
`backend/src/service/underwriting_service.py:182` and `:219`
Severity: WARN
Description: `_reject_pii` rejects a `detail` payload whose **keys** look like personal data, but it
never inspects the **values**, and it only walks the top level. The underwriter decision and admin
override paths put the operator's free-text `comment` (length-bounded, otherwise unconstrained)
straight into `audit_records.detail`, and `GET /api/underwriting/applications/{id}/audit` returns it
to any UNDERWRITER or ADMIN. An underwriter who types a health detail, an Aadhaar or a PAN into the
comment box persists it unmasked in an append-only table that by design can never be corrected
(NFR-02), which is exactly the outcome NFR-03 exists to prevent. The redacting logger would have
caught the same string had it only been logged.
Fix: in `AuditService.record`, recurse through `detail` and pass every string value through
`src.lib.logging.mask_pii(value)` (the no-`kind` branch, which masks Aadhaar/PAN shapes and leaves
ordinary prose intact) before handing the payload to the repository, and make `_reject_pii` walk
nested dicts and lists so a future caller cannot bypass the key check by nesting one level down.

### [APP-W02] Client-supplied `X-Correlation-ID` is neither validated nor length-bounded before being logged and reflected
File: `backend/src/api/middleware.py:50` (`_incoming_correlation_id`), reflected at `:44`
Severity: WARN
Description: Any non-blank inbound `X-Correlation-ID` is adopted verbatim, bound for the request,
written into every log line for that request and echoed in the response header. Nothing constrains
its length or character set, so a caller can inflate every log line of a request with an
arbitrarily large attacker-chosen string (log flooding / storage exhaustion) and can steer a value
of its choosing into a response header. The JSON formatter escapes control characters, so log
injection proper is not reachable, and the ASGI layer rejects CR/LF in header values, so response
splitting is not reachable — which is why this is a WARN and not a BLOCK.
Fix: accept the inbound value only when it matches a conservative pattern (a UUID, or
`^[A-Za-z0-9._-]{1,64}$`); otherwise mint a fresh id with `new_correlation_id()` and ignore the
client's.

### [APP-W03] No security response headers on any route
File: `backend/src/main.py:22` (middleware stack)
Severity: WARN
Description: The application installs only `CorrelationIdMiddleware`. No response carries
`Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options: nosniff`
or `Referrer-Policy`. Because the SPA is served same-origin through the Vite proxy and reads
policy and KYC-derived data, a missing `nosniff` plus a missing frame policy leaves the deployed
stack open to MIME-confusion and clickjacking/UI-redress framing of the admin and underwriting
screens.
Fix: add one small middleware that sets `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and a `Content-Security-Policy` of
`default-src 'self'` on every response (exempt `/docs` if the interactive schema is to stay usable).

## INFO Findings

### [APP-I01] Authentication is a header-declared stub — any client can claim ADMIN
File: `backend/src/api/deps.py:63` (`get_current_actor`)
Severity: INFO
Description: `X-Actor-Id` / `X-Actor-Role` are trusted as presented; there is no token, signature or
session, so role and identity are entirely client-asserted. This is the documented design
(`docs/conventions.md` -> "API / auth stub", contract §0.2) and is therefore not scored as a
finding against the project's own standard, but it is the single largest gap between this codebase
and a deployable one. The implementation of the stub is correct on the points that matter:
`HEADER_ROLES` excludes `ActorRole.SYSTEM`, so the scheduler role cannot be supplied from a header
(401 `UNAUTHENTICATED`, DEC-010), and role checks live only in `deps.py`.
Fix: before any non-demo deployment, replace `get_current_actor` with verification of a signed
token and derive `actor_id`/`role` from its validated claims; keep `require_role` unchanged.

### [APP-I02] Interactive OpenAPI schema is served without auth
File: `backend/src/main.py:17` (`FastAPI(...)` defaults)
Severity: INFO
Description: `/docs`, `/redoc` and `/openapi.json` are reachable unauthenticated and enumerate every
route, DTO and error code. Low risk given the auth stub already grants anything, but it is free
reconnaissance once real auth exists.
Fix: set `docs_url=None, redoc_url=None, openapi_url=None` when a production flag is set.

### [APP-I03] Cancellation free-text `reason` is persisted unmasked on the refund/transition row
File: `backend/src/service/cancellation_service.py:125`
Severity: INFO
Description: The customer-supplied cancellation `reason` is stored verbatim on an append-only row.
It is the caller's own data, is never logged and is returned only to the owner or staff, so this is
not an NFR-03 breach — but it is the same unscanned-free-text shape as APP-W01 and would be covered
by the same fix.
Fix: pass the value through `mask_pii` on the way in, once APP-W01 introduces that helper call.

### [APP-I04] Application name, date of birth and address are stored unmasked
File: `backend/src/repository/models/underwriting.py:49`–`:52`
Severity: INFO
Description: `full_name`, `date_of_birth` and `address` are stored in the clear; only
`aadhaar_masked` and `pan_masked` are masked. This matches the spec exactly (NFR-03 and the
conventions table name Aadhaar, PAN and health declarations as the protected set) and the fields are
owner/staff-scoped, so it is recorded only as a residual data-at-rest note.
Fix: none required by the spec; consider encrypting the KYC columns at rest if the protected set
ever widens.

### [APP-I05] Dependency versions are declared as open ranges
File: `backend/pyproject.toml:7`; `frontend/package.json:15`
Severity: INFO
Description: Backend dependencies use `>=` and frontend dependencies use `^`, so a fresh resolve can
pull an unreviewed version. Mitigated in practice: `backend/uv.lock` and `package-lock.json` are
both committed and pin the resolved graph. No known-vulnerable direct dependency was identified.
Fix: keep both lock files committed and install with `uv sync --frozen` / `npm ci` in CI so the
ranges are never re-resolved silently.

### [APP-I06] `/api/admin/ping` is not in the authoritative endpoint table
File: `backend/src/api/routers/admin.py:23`
Severity: INFO
Description: An auth-boundary probe route exists that `docs/conventions.md` -> "API endpoints" does
not list ("No other paths exist"). It is correctly ADMIN-gated and returns no data, so the exposure
is nil; this is spec drift with a security-surface flavour.
Fix: add the route to the conventions table or delete it and cover the auth boundary with a test.

### [APP-I07] Frontend `localStorage` holds the demo role selector
File: `frontend/src/app/RoleContext.tsx:32`
Severity: INFO
Description: Only the string `policyforge.demoRole` is persisted — no PII, no token. The server
re-derives authorisation from the request headers on every call and the role switcher cannot grant
anything the backend would refuse, so the switcher is a genuine demo convenience and the server
remains authoritative.
Fix: none.

## Verified Clean

Checked and found conforming; recorded so the next review need not re-derive it.

- **NFR-03 / PII.** `health_declaration.details` is never persisted, never logged and never returned:
  only the derived boolean `has_pre_existing_condition` crosses into underwriting
  (`service/application_service.py:286`). Aadhaar and PAN reach the database only through
  `mask_pii(..., "aadhaar"|"pan")` (`service/application_service.py:245`–`:246`). `lib/logging.py`
  masks PII *inside the formatter* by key name and by value shape, at any nesting depth, so a
  careless `extra=` cannot leak; `Application.__repr__` omits every KYC field; the access log carries
  no query values or bodies; `frontend/src/api/client.ts` logs no request or response body and the
  underwriter case view renders `aadhaar_masked` / `pan_masked` only.
- **NFR-04 / auth and audit.** Every router binds `require_role(...)` through a `Depends` alias, so
  no route is reachable without `get_current_actor`; `SYSTEM` is refused from the header. Every
  customer-scoped read and mutation compares the owning id and raises `NotFoundError` — 404, not 403
  — on a mismatch (`quote_service.py:191`, `application_service.py:264`, `policy_query_service.py:187`,
  `policy_service.py:137` and `:198`, `endorsement_service.py:210`, `renewal_service.py:83`). Every
  staff and admin action writes an audit row carrying `actor_id` and `actor_role` inside the same
  transaction (catalog draft/replace/publish, UW approve/decline/override, issuance, endorsement,
  cancellation, end-of-day). The UNDERWRITER queue is confined to `MANUAL_REVIEW`
  (`underwriting_service.py:274`).
- **NFR-02/05 / immutability.** The repositories for `rule_set_versions`, `underwriting_decisions`,
  `underwriting_overrides`, `policy_state_transitions`, `endorsements`, `premium_payments`, `refunds`
  and `audit_records` expose `add(...)` plus reads only — no update, delete or `setattr` path exists.
  The single mutating helper, `PolicyRepository.update_projection` (`policy_repository.py:105`), moves
  the `policies` current-state projection, which conventions explicitly mark as not append-only, and
  it rejects unknown attribute names. Migrations `0001`–`0006` are additive and none was edited.
  `src/seed.py:85` calls `verify_published_lock(rules_root)` before any insert, so a tampered
  PUBLISHED rule file aborts the seed.
- **Injection.** No raw SQL is built anywhere: every query is a SQLAlchemy `select()` with bound
  parameters, and the only `text()` uses are constant fragments (`rowid`, partial-index predicates).
  `domain/condition.py` is a regex-driven evaluator with no `eval`/`exec` and no arithmetic; a
  malformed clause, an unknown field or a non-numeric ordered comparison raises `ValidationError`.
  Rule bodies are validated against `rule-file.schema.json` by `build_rule_set` *before* being
  stored, on the create-draft, replace-draft and publish paths alike. Path traversal is structurally
  impossible in the loader: `rule_file_path` composes the root with a folder looked up from the
  `ProductCode` enum and `f"v{int(version)}.json"`, so no request string reaches the path.
- **NFR-01 / money.** No `float` appears in any money path; `application_validator.py:81` actively
  rejects a `float` input, and rule files are parsed with `parse_float=Decimal`. Client-supplied
  amounts are never trusted: `PaymentService._record` recomputes the renewal premium and rejects a
  mismatch with `AMOUNT_MISMATCH` (`service/payment_service.py:87`) after validating scale and sign,
  and refund amounts are computed server-side from the policy's own rule version — the cancel request
  body carries only a date and a reason.
- **Secrets, CORS, frontend.** No hardcoded credential, API key or token in `backend/src`,
  `frontend/src`, `scripts` or `.gitlab-ci.yml`; no `.env` is committed and `.gitignore` excludes
  `.env*` and `*.db`. No CORS middleware is installed at all (the SPA is same-origin via the Vite
  proxy), so no wildcard origin can be combined with the header auth stub. No
  `dangerouslySetInnerHTML`, `innerHTML` or `eval` in the frontend, and no bundled secret
  (`import.meta.env` is unused). Seed and e2e fixtures use only synthetic identifiers
  (Aadhaar `9999…`, PAN `AAAAA000NA`).
- **CI.** The `claude-review` job still restores `.claude/`, `CLAUDE.md`, `AGENTS.md` and `.mcp.json`
  from the merge target before invoking the reviewer, so MR-authored instructions cannot steer it,
  and it fails the pipeline if a secret-shaped token appears in the report.

VERDICT: WARN
