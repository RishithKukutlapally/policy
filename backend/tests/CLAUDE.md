# backend/tests/ — pytest suites

| Folder | Purpose |
|--------|---------|
| `unit/` | Pure domain/service tests — premium math, rule branches, state machine (≥20 tests required) |
| `ac/` | One or more tests per acceptance criterion, via the API (TestClient) |
| `architecture/` | Structural tests (≥3): layering, no float in money code, append-only repos, immutable versions |
| `integration/` | Repository + migration tests against a temp SQLite DB |

## Rules

- **TDD:** write the failing test and commit it (`test: ... (red)`) before the implementation commit.
- **AC tagging:** name `test_acNN_<behaviour>`, decorate `@pytest.mark.ac("AC-NN")`, first docstring
  line `AC-NN: <criterion>`. Check with `/ac-coverage`.
- Never weaken or delete a test to make it pass — fix the code (harness self-healing policy).
- Fixtures build synthetic data only, in the formats of `docs/conventions.md` → "Synthetic data"
  (Aadhaar `9999…`, PAN `AAAAA0001A`, masked `XXXX-XXXX-0001`, fictional names/addresses).
- Money assertions compare `Decimal` to `Decimal("…")` exactly — no `pytest.approx`.
