# backend/src/api/ — controllers (FastAPI routers)

## Rules

- Routers only map HTTP ⇄ service calls: validate DTOs (Pydantic, `Decimal` fields as strings in JSON),
  call one service method, map typed errors to status codes (`InvalidPolicyStateException` → 409,
  validation → 422, not found → 404).
- **Auth boundary (NFR-04):** every router depends on `get_current_actor` (header `X-Actor-Id` +
  `X-Actor-Role` ∈ {CUSTOMER, UNDERWRITER, ADMIN} — a documented stub, no real IdP). Underwriter/admin
  endpoints use `require_role(...)`; the actor id is passed to the service for auditing.
- **Correlation (NFR-06):** middleware reads/creates `X-Correlation-ID`, binds it to the JSON logger and
  echoes it in the response.
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Content-Security-Policy` are set at the API layer by `CorrelationIdMiddleware` on every response.
- `GET /health` returns 200 `{"status": "ok"}` with no DB work so it answers within 1 s of startup (NFR-07).
- Do not import from `src.repository` directly — go through services (import-linter contract).
- Every endpoint appears in `specs/design/api-contracts.md` before it is implemented (spec is truth).
