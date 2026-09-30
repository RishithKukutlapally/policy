# Fix loop — published-version-not-loadable

- **Date:** 2026-09-30
- **Status:** FIXED
- **Branch:** `fix/published-version-not-loadable` (base `chore/policyforge-substrate`)
- **Command:** `cd backend && uv run pytest -q -o addopts=""`

## 1. Detect

Found by the E9-S4 Playwright run, `e2e/tests/catalog-admin.spec.ts`, whose spec stops short of
confirming publish so it does not brick the running app:

```
An ADMIN publishes a new rule-set version through the Product Catalog Manager.
catalog_service.publish appends a PUBLISHED row to rule_set_versions, so that version becomes the
product's ACTIVE version — but no backend/policy_rules/<product>/v<N>.json file exists for it.
The rule loader reads rule files from disk, so the next quote, portfolio or renewal call for that
product fails with: NOT_FOUND — no rule file for product HOUSEHOLD v2.
```

## 2.1 Reproduce + fix (attempt 1)

New AC test (written first): `backend/tests/ac/test_ac11_published_version_is_loadable.py` — drafts
and publishes HOUSEHOLD v2 over the API exactly as the admin UI does, records an in-force policy on
v2, then asks for the admin portfolio.

Failing output, verbatim:

```
    def test_ac11_published_version_is_loadable_by_the_portfolio(
        api_client: TestClient, seeded_engine: Engine
    ) -> None:
        """AC-11: the portfolio loads a UI-published version that has no file on disk."""
        _publish_household_v2(api_client)
        _seed_policy_on_v2(seeded_engine)

        response = api_client.get(
            "/api/admin/portfolio", params={"as_of": AS_OF.isoformat()}, headers=ADMIN
        )
>       assert response.status_code == 200, response.text
E       AssertionError: {"error":{"code":"NOT_FOUND","message":"no rule file for product HOUSEHOLD v2","details":null}}
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests\ac\test_ac11_published_version_is_loadable.py:79: AssertionError
=========================== short test summary info ===========================
FAILED tests/ac/test_ac11_published_version_is_loadable.py::test_ac11_published_version_is_loadable_by_the_portfolio
1 failed, 2 passed, 1 warning in 0.89s
```

### Root cause

`rule_set_versions` is the system of record for published versions (a publish appends a row with the
full body, NFR-02), but `src/config/rule_loader.load_rule_file` — used by `PortfolioService._schedule`
— still resolved a version only from `backend/policy_rules/<product>/v<N>.json`. A version published
through the API therefore becomes ACTIVE with no file behind it, so every disk-based read path 404s.
`quote_service`, `renewal_service`, `application_service` and `cancellation_service` already built
their rule set from `row.content`, which is why only the file-based path broke.

### Options considered

- **(a) chosen — database-first rule resolution.** `rule_loader.load_rule_set(product, version,
  source=...)` resolves the body from a `RuleContentSource` when a row exists and falls back to the
  on-disk file otherwise. The seeded `v1` files remain the source of truth for v1 and remain the only
  thing `verify_published_lock()` covers, so the append-only `PUBLISHED.lock` ledger keeps its
  meaning. Because `src.config` may not import `src.repository` (import-linter layered contract), the
  source is a structural `Protocol`; its database implementation, `RepositoryRuleContentSource`,
  lives in the service layer over `RuleSetVersionRepository`. All five contracts stay KEPT.
- (b) rejected — have the API write a new `v<N>.json` into the repo tree. It violates NFR-02/NFR-05
  (committed rule files are immutable; hook `policy-immutability-check` blocks writes to published
  files) and a server writing into its own source tree is not deployable (read-only image, no repo).

## 3.1 Validate — PASS

```
$ uv run ruff check --fix src tests   -> All checks passed!
$ uv run ruff format src tests        -> 184 files left unchanged
$ uv run mypy src/                    -> Success: no issues found in 91 source files
$ uv run lint-imports                 -> Contracts: 5 kept, 0 broken.
$ uv run pytest -q -o addopts=""      -> 655 passed, 1 warning in 59.47s
$ uv run pytest -q --cov=src --cov-report=xml:coverage.xml -> TOTAL 4062 58 99%
```

Before: 651 passed. After: 655 passed (the 4 new AC-11 tests). Nothing regressed; coverage 99%.

## 4. Change set

`git diff --stat` shows nothing for `backend/` because that tree is still untracked on this branch;
the touched files are:

```
backend/src/config/rule_loader.py                          +37  (RuleContentSource, load_rule_set)
backend/src/service/portfolio_service.py                    +22 -2 (RepositoryRuleContentSource, db-first _schedule)
backend/tests/ac/test_ac11_published_version_is_loadable.py +120 (new, 4 tests)
backend/tests/portfolio_helpers.py                          +2 -1 (seed_policy rule_version kwarg)
docs/fix-loops/2026-09-30-published-version-not-loadable.md  new
docs/knowledge-deposits.md                                  +1 (KD-011)
```

## 5. PR

Branch for the human to use: `fix/published-version-not-loadable` (off `main`), merged with
`git merge --no-ff`. Commit in TDD order:

1. `test: AC-11 a UI-published rule version must be loadable` —
   `backend/tests/ac/test_ac11_published_version_is_loadable.py`, `backend/tests/portfolio_helpers.py`
2. `fix: resolve rule sets database-first so published versions load` —
   `backend/src/config/rule_loader.py`, `backend/src/service/portfolio_service.py`
3. `docs: record the published-version fix loop` — `docs/fix-loops/2026-09-30-published-version-not-loadable.md`,
   `docs/knowledge-deposits.md`

Follow-up for `e2e`: `e2e/tests/catalog-admin.spec.ts` can now confirm publish and assert a quote on
the new version (out of scope here).
