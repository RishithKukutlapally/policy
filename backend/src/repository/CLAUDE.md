# backend/src/repository/ — persistence (SQLAlchemy 2 · SQLite)

Canonical model and table names: `docs/conventions.md` → "Persistence". Use them verbatim.

## Rules

- Money columns are `Numeric(12, 2)` (rates `Numeric(9, 6)`) mapped to `Decimal` — never `Float`
  (hook `premium-precision-check`).
- **Append-only tables (NFR-02):** `rule_set_versions`, `underwriting_decisions`, `underwriting_overrides`,
  `policy_state_transitions`, `endorsements`, `premium_payments`, `refunds`, `audit_records`.
  Their repositories expose `add(...)` and read methods only — no update, no delete
  (hooks `append-only-repository-check`, `shell-immutability-check`; architecture tests).
- `policies` and `applications` hold the *current* projection (status, sum insured, premium, address,
  nominee); history is reconstructable from the append-only tables.
- One repository per aggregate: `src/repository/<entity>_repository.py`; models in `src/repository/models.py`.
- Repositories take a `Session` in the constructor and never commit — services own the transaction.
- Schema changes need a new Alembic migration in `backend/migrations/versions/` (see that folder's CLAUDE.md).
- Imports allowed: `src.types`, `src.config`, `src.lib`, SQLAlchemy.
