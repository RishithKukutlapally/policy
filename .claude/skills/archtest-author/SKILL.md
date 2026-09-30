---
name: archtest-author
description: Author import-linter layer contracts in backend/pyproject.toml and pytest structural tests in backend/tests/architecture/ — layer direction, no float in money modules (AST), immutable rule versions and append-only repositories, no PII in log calls (NFR-01/02/03/08).
argument-hint: "[--contracts-only | --tests-only]"
context: fork
agent: archtest-author-agent
---

# Archtest Author

Encodes architecture rules as automated tests (NFR-08) so they fail in CI, not in review.
Tests live in `backend/tests/architecture/` and are **structural**: they read source/AST, not runtime behaviour.

## Step 1 — import-linter contracts (`backend/pyproject.toml`)

```toml
[tool.importlinter]
root_package = "src"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Layered architecture (one-way)"
type = "layers"
layers = [
    "src.api",
    "src.service",
    "src.repository",
    "src.config",
    "src.domain",
    "src.types",
]
ignore_imports = []           # never add entries without a knowledge-deposit entry

[[tool.importlinter.contracts]]
name = "Domain and types are framework-free"
type = "forbidden"
source_modules = ["src.domain", "src.types"]
forbidden_modules = ["fastapi", "sqlalchemy", "httpx", "src.lib", "logging"]

[[tool.importlinter.contracts]]
name = "API goes through services (no repository, no domain)"
type = "forbidden"
source_modules = ["src.api"]
forbidden_modules = ["src.repository", "src.domain"]

[[tool.importlinter.contracts]]
name = "Repository depends on types and config only"
type = "forbidden"
source_modules = ["src.repository"]
forbidden_modules = ["src.domain"]

[[tool.importlinter.contracts]]
name = "lib is standard library only"
type = "forbidden"
source_modules = ["src.lib"]
forbidden_modules = ["src.types", "src.domain", "src.config", "src.repository", "src.service", "src.api", "src.main"]
```
These mirror the layer import rules in `docs/conventions.md`: `src.lib` is cross-cutting and **stdlib only**;
config, repository, service and api may import it, while `types` and `domain` stay pure (no `src.lib`, no
`logging`) so premium and underwriting math stay deterministic. Ensure `import-linter` is in `[dependency-groups] dev`.

Verify: `cd backend && uv run lint-imports` → all contracts `KEPT`.

## Step 2 — Structural tests (≥3, target 5)

Shared helper `backend/tests/architecture/_ast_utils.py`: `iter_modules(pkg_dir) -> Iterator[tuple[Path, ast.Module]]`.

| File | Rule | How |
|------|------|-----|
| `test_layer_direction.py` | Lower layers never import higher ones (belt-and-braces over import-linter) | Walk `ast.Import/ImportFrom` in `src/<layer>/`; map `src.<x>` to rank; assert rank(target) ≤ rank(source) |
| `test_no_float_in_money.py` | NFR-01 | In money modules (`src/domain/premium_calculator.py`, `refund_rules.py`, `endorsement_rules.py`, `renewal_rules.py`, `src/service/quote*`, `endorsement*`, `renewal*`, `cancellation*`): no `ast.Name(id="float")`, no `ast.Constant` of type `float`, no `round(` call, no `Decimal(<float constant>)` |
| `test_rule_versions_immutable.py` | NFR-02/05 | (a) rule-file loader returns frozen dataclasses/`MappingProxyType`; (b) no function in `src/` opens `policy_rules/**` with mode `w`/`a`; (c) every PUBLISHED file's SHA-256 matches its `<sha256>  <relative path>` line in `backend/policy_rules/PUBLISHED.lock`, and every lock line points to a PUBLISHED file |
| `test_append_only_repositories.py` | NFR-02 | For classes in `src/repository/` named `*RuleSetVersion*`, `*UnderwritingDecision*`, `*Override*`, `*StateTransition*`, `*Endorsement*`, `*PremiumPayment*`, `*Refund*`, `*AuditRecord*` (the ✅ models of the Persistence table in `docs/conventions.md`): public API is `add(...)` + reads; no method matching `^(update|delete|remove|upsert|merge|append)`; no `session.delete(` / `.update(` calls; guard: each ✅ model has a matching class |
| `test_no_pii_in_logs.py` | NFR-03 | For every `ast.Call` whose func is `logger.<level>` / `logging.<level>` / `print`: no arg or f-string part references a name/attr matching `aadhaar|pan|pan_number|health|medical|declaration`; `extra={...}` keys checked too |
| `test_migrations_append_only.py` | NFR-05 | Existing files in `migrations/versions/` are unchanged: `git diff --name-status $BASE -- migrations/versions` has only `A`, with `BASE = git merge-base HEAD origin/$CI_DEFAULT_BRANCH` in CI (`git merge-base HEAD main` locally) |

Example (no-float):
```python
MONEY_GLOBS = ("domain/premium_calculator.py", "domain/refund_rules.py", "domain/endorsement_rules.py",
               "domain/renewal_rules.py", "service/quote*.py", "service/endorsement*.py",
               "service/renewal*.py", "service/cancellation*.py")

@pytest.mark.parametrize("path", money_modules(MONEY_GLOBS), ids=str)
def test_money_modules_use_no_float(path: Path) -> None:
    offenders = [f"{path}:{n.lineno}" for n in ast.walk(ast.parse(path.read_text()))
                 if (isinstance(n, ast.Name) and n.id == "float")
                 or (isinstance(n, ast.Constant) and type(n.value) is float)
                 or (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "round")]
    assert not offenders, "NFR-01 float usage:\n" + "\n".join(offenders)

def test_money_globs_match_something() -> None:
    assert money_modules(MONEY_GLOBS), "guard: globs matched no files — test would be vacuous"
```
Every structural test needs a **non-vacuity guard** (asserts the scan found ≥1 file/class).

## Step 3 — Prove the tests bite (mutation check)
Factor each scan into a pure function (`find_float_usages(source: str) -> list[int]`, etc.) and add a
self-test that feeds it a synthetic violating snippet — never touch real `src/` files to demo a failure:
```python
def test_float_scanner_detects_violation() -> None:
    assert sorted(find_float_usages("x: float = 1.5\ny = round(z, 2)\n")) == [1, 1, 2]
```
Record the self-test output in the PR description.

## Step 4 — Run
```bash
cd backend && uv run lint-imports
cd backend && uv run pytest tests/architecture -q
cd backend && uv run mypy tests/architecture
```
Add `lint-imports` and `pytest tests/architecture` as separate CI jobs in `.gitlab-ci.yml` (report only; do not edit CI here).

## Checklist
- [ ] Layers contract lists exactly `api > service > repository > config > domain > types`
- [ ] `lib` stdlib-only, api ↛ repository/domain and repository ↛ domain contracts present
- [ ] `uv run lint-imports` all KEPT
- [ ] ≥3 structural tests, each with non-vacuity guard
- [ ] Each test demonstrated failing against an injected violation
- [ ] No `ignore_imports` entries without a `docs/knowledge-deposits.md` justification
