# e2e/ — Playwright UI validation

- `npx playwright test` from `e2e/` (or `npm run e2e` at the repo root, which boots API + UI).
- One spec file per user journey: quote, apply, view policies, endorse, renew/cancel, underwriter
  workbench, catalog manager, admin dashboard. Put the `AC-NN` id in each test title.
- **Snapshot directory is required** (rubric): visual/ARIA snapshots via `toHaveScreenshot()` /
  `toMatchAriaSnapshot()` live in `tests/<spec>.spec.ts-snapshots/` and are committed.
- Run at two viewports (desktop 1280×800, mobile 390×844) to prove the responsive layout.
- The harness evaluator drives the same flows interactively through Playwright MCP (`.mcp.json`).
- Seed data only; tests must not depend on execution order.
