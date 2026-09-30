# backend/ — PolicyForge API (FastAPI · Python 3.12 · uv)

Inherits the root `CLAUDE.md`. This module owns the policy lifecycle API, domain rules, persistence and migrations.

## Commands

| Task | Command |
|------|---------|
| Install | `uv sync` |
| Tests + coverage | `uv run pytest --cov=src --cov-report=xml:coverage.xml` |
| Only AC-tagged tests | `uv run pytest -m ac` |
| Architecture contracts | `uv run lint-imports` + `uv run pytest tests/architecture` |
| Lint / types | `uv run ruff check --fix . && uv run ruff format .` · `uv run mypy src/` |
| Migrate + seed | `uv run alembic upgrade head && uv run python -m src.seed` |
| Run | `uv run uvicorn src.main:app --port 8000` |

## Layout (imports flow downward only)

```
src/types/       enums, value objects, typed errors (InvalidPolicyStateException)   → imports nothing
src/domain/      pure business rules (premium, underwriting, state machine, refunds) → types
src/config/      settings, rule-file loader                                         → types, domain
src/repository/  SQLAlchemy models + append-only repositories                        → types, config
src/service/     use-case orchestration, transactions, audit                         → + repository, domain
src/api/         FastAPI routers (controllers), auth deps, DTOs, middleware          → + service
src/lib/         cross-cutting: JSON logger with PII redaction, correlation id       → stdlib only
policy_rules/    versioned product rule files (data, not code)
migrations/      Alembic — append-only
tests/           unit · ac · architecture · integration
```

Each layer folder has its own `CLAUDE.md` with local rules — read it before editing there.

## Module rules

- Names, paths, models, tables and rule-file fields: `docs/conventions.md` (canonical).
- **Float is banned across all of `src/` and `migrations/`, not only in money modules** — the
  `premium-precision-check` hook is intentionally stricter than the architecture test. There is no
  legitimate float in this domain; durations use `int` seconds/days, ratios use `Decimal`.

- `pyproject.toml` declares every dependency, including `pytest-cov` (coverage) and `import-linter`.
- `coverage.xml` is committed after each sprint (the rubric's coverage artefact).
- Money is `Decimal` end to end: request DTO → domain → `Numeric(12, 2)` columns → response.
- No `print()`; use `src.lib.logging.get_logger(__name__)`.
