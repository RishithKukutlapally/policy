# backend/migrations/ — Alembic (append-only, NFR-05)

- Create a new revision for every schema change: `uv run alembic revision -m "<change>"`.
- **Never edit a committed migration** — hook `policy-immutability-check` blocks it. Fix forward with a new revision.
- Never `op.drop_table` / `op.drop_column` on append-only tables (hook `append-only-repository-check`).
- Money columns: `sa.Numeric(12, 2)`. No `sa.Float`.
- Keep migrations consistent with `src/repository` models — agent `migration-coherence-agent` checks this.
