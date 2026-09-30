# PENDING — open items at hand-off

Everything the capstone asks for is built, tested and verified (evaluator `VERDICT: PASS`).
Three things remain. Two are yours to do at the office; one is optional and only partly achievable.

Last updated: 2026-09-30

---

## 1. ⚠️ Playwright MCP — configured but never exercised

**Status:** partially complete. One rubric bullet is affected.

### What the rubric asks

> §7.1 — *"Playwright MCP configured in `.mcp.json` **and actively used by the evaluator**"*

### Where we actually are

| Half of the requirement | State |
|---|---|
| Configured in `.mcp.json` | ✅ Done — pinned to `@playwright/mcp@0.0.83`, and the `evaluator` and `design-critic` agents have the `mcp__playwright__*` tools in their frontmatter |
| Actively used by the evaluator | ⚠️ **Not achieved** |

### Why

The Playwright MCP server **fails to start on the personal laptop** — every session reports:

```
playwright (CONNECT_TIMEOUT): "MCP server playwright connection timed out after 30000ms"
```

This persisted after pre-installing the package and downloading Chromium, so it looks like an
environment problem on that machine rather than a configuration error.

### What was done instead

The evaluator verified the UI through the **committed Playwright test suite** rather than by driving a
browser through MCP:

- 32 end-to-end tests, 16 specs × 2 viewports (desktop 1280×800, mobile 390×844)
- 18 committed PNG baselines + 4 ARIA snapshots in `e2e/tests/*.spec.ts-snapshots/`
- Every test title carries its `AC-NN` id

So the UI *is* genuinely verified and the snapshot-directory requirement (§7.4) is fully met. The gap is
narrow: the evaluator did not drive screens through the MCP server specifically, so the
`design_checks` blocks in the four sprint contracts are **unscored — neither passed nor failed**.

### How to close it at the office (optional, ~15 minutes)

```bash
npx playwright install chromium
npm start                      # leave running in one terminal
```

Then in Claude Code (in the project folder), check whether the MCP server connects — if it does, ask the
evaluator agent to drive 2–3 screens (quote, catalog, portfolio) at both viewports and save screenshots to
`specs/reviews/playwright-mcp/`. Commit them on a small branch, e.g.:

```bash
git checkout -b docs/playwright-mcp-evidence
git add specs/reviews/playwright-mcp/ specs/reviews/evaluator-report.md
git commit -m "docs: Playwright MCP evaluator screenshots"
git push gitlab docs/playwright-mcp-evidence
```

…then merge it through a Merge Request like the others.

### If it does not connect there either

**Leave it.** Do not fake the screenshots. The caveat is already written honestly into
`docs/rubric-checklist.md`, and an examiner who reads it will see a documented tooling limitation with
the work verified another way — which is worth more than a fabricated artefact.

---

## 2. 🔄 Push to GitLab and merge the branches

**Status:** not started — this is the main remaining task.
**Full instructions:** `OFFICE-SUBMISSION-GUIDE.md`

Short version:

```bash
git clone https://github.com/RishithKukutlapally/policy.git
cd policy
git remote add gitlab https://git.virtusa.com/cnl-projects/<your-repo>.git
git push gitlab "refs/remotes/origin/*:refs/heads/*"
```

Then open a Merge Request per branch into `main`, in the order listed in the guide, always using
**"Merge commit"**.

> **Squashing would destroy the 26 `test:` → `feat:` commit pairs** that prove red→green→refactor, and
> cost marks under §7.3. This is the single highest-risk step in the whole hand-off.

---

## 3. 🔄 CI runner (and optionally the Claude review key)

**Status:** not started. Affects §7.5 — "passing build on main".

The pipeline is written and correct, but sandbox repos under `cnl-projects` usually have **no runner
attached**, so it will sit at *pending* rather than running.

**Raise a ticket:**

> Project: `cnl-projects/<your-repo>`. Request: Enable shared runners for this project, OR attach a group
> runner with Node/Python executors. Reason: CI/CD pipelines for AI-native engineering training.
> (1) Do shared runners exist on git.virtusa.com? (2) If not, is there a sanctioned group runner I can
> request access to? (3) If neither exists, what is the approved process to attach a runner?

**Optional** — to make the `claude-review` job actually run, add `ANTHROPIC_API_KEY` under
Settings → CI/CD → Variables as **Masked + Protected**, and protect the `feat/*`, `chore/*`, `fix/*` and
`docs/*` branches so protected variables reach their pipelines. Without the key the job is skipped and
the pipeline still passes.

---

## Not pending — already complete

For contrast, so nothing is chased twice:

| | |
|---|---|
| Application | All 4 sprints, 34 stories, 3 products, full policy lifecycle |
| Tests | 697 backend + 98 frontend + 32 Playwright, all passing |
| Coverage | 99 % — `backend/coverage.xml` committed |
| Acceptance criteria | 24/24 traced to tests — `specs/reviews/ac-audit.md` says `VERDICT: PASS` |
| Architecture | 5 import-linter contracts kept + 7 structural tests |
| Guard hooks | 5 project hooks + 58-case self-test, run in CI |
| Evaluator | `specs/reviews/evaluator-report.md` — `VERDICT: PASS`, 30/30 contract checks |
| Reviews | Security (WARN, 0 blockers) and clean-code, both in `specs/reviews/` |
| Evidence | 4 sprint contracts · fix-loop trace · 13 knowledge deposits · 16 decisions · commit plan |
| Git history | 68 commits, 26 `test:` paired with 26 `feat:`, on 10 branches, already on GitHub |
