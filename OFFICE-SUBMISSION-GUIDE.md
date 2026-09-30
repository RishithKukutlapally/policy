# Office Laptop — Submission Guide

**Read this first. It is the complete set of steps to get PolicyForge from GitHub onto Virtusa
GitLab as a properly merged, gradeable submission.**

---

## 1. The situation

The whole project was built on the **personal laptop** and pushed to a personal GitHub repository.
Nothing has been pushed to Virtusa GitLab yet.

| | |
|---|---|
| **Source (already done)** | https://github.com/RishithKukutlapally/policy |
| **Destination (your job)** | `https://git.virtusa.com/cnl-projects/<your-repo>` |
| **What exists** | 10 branches · 68 commits · 559 files · the complete working application |
| **What remains** | Push to GitLab, then merge the branches into `main` through Merge Requests |

### Why the branches matter

The capstone is graded partly on the **git history**, not just the code:

- **26 `test:` commits paired with 26 `feat:` commits** — each failing test committed *before* the code
  that makes it pass. That is the red→green→refactor evidence the rubric scores under §7.3.
- **Merge Requests into `main`** with no direct commits to `main` — scored under §7.5.

Both are already baked into the commits. You only have to move them across **without flattening them**.

> ### ⚠️ The one mistake that would cost real marks
>
> **Do not use "Squash and merge".** Squashing collapses a whole branch into a single commit and
> destroys all 26 test→feat pairs. Use **"Merge commit"** every time.
>
> Equally: **do not create empty branches and copy files into them.** That throws away the history.
> Pushing an existing branch creates it on the remote automatically — you never create branches by hand.

---

## 2. Before you start

- [ ] You are on the **corporate network or VPN** — `https://git.virtusa.com/` must load in a browser.
- [ ] You have a **personal sandbox repo** under `cnl-projects` (typically `t0_<empNo>-<name>`).
      If not, raise a ticket: *"Need a personal sandbox repository on git.virtusa.com under cnl-projects
      group for AI-native engineering training."*
- [ ] You have a **GitLab Personal Access Token**: avatar → Edit profile → Access Tokens →
      scopes `api`, `read_repository`, `write_repository`. **Copy it immediately — it is shown once.**
      It starts with `glpat-`.
- [ ] `git --version` works in a terminal.

---

## 3. Move the repository to GitLab

Open a terminal (PowerShell or Git Bash) and run these **four commands**:

```bash
git clone https://github.com/RishithKukutlapally/policy.git
cd policy
git remote add gitlab https://git.virtusa.com/cnl-projects/<your-repo>.git
git push gitlab "refs/remotes/origin/*:refs/heads/*"
```

**What each line does**

| Line | Purpose |
|---|---|
| `clone` | Downloads the full history — all commits, all branches |
| `cd` | Enters the folder |
| `remote add gitlab` | Registers your GitLab repo under the name `gitlab`. Replace `<your-repo>` |
| `push gitlab "refs/..."` | Pushes **all 10 branches at once**, creating each one on GitLab |

When prompted:
- **Username** — your corp username (the part before `@virtusa.com`)
- **Password** — paste the **`glpat-` token**, not your Windows password

### Confirm it worked

```bash
git ls-remote --heads gitlab
```

You should see **10 branches**. If you see fewer, push the missing ones individually:

```bash
git push gitlab refs/remotes/origin/<branch-name>:refs/heads/<branch-name>
```

---

## 4. Merge the branches — in this exact order

Each branch builds on the one before it, so the order matters. On GitLab: **Merge requests → New merge request**,
source = the branch, target = `main`.

| # | Source branch | What it adds |
|---|---|---|
| 1 | `chore/harness-scaffold` | Claude Harness Engine scaffold + the Windows hook fix |
| 2 | `chore/policyforge-substrate` | Agents, skills, commands, guard hooks, plugin, MCP, CI, SDK scripts |
| 3 | `docs/brd-spec-design` | BRD, business case, 7 specs, 34 stories, design docs, mockups, architecture |
| 4 | `feat/sprint-1-foundation-catalog` | Platform foundation + product catalog |
| 5 | `feat/sprint-2-quote-underwriting` | Quote engine + underwriting |
| 6 | `feat/sprint-3-issuance-endorsement` | Policy issuance + endorsements |
| 7 | `feat/sprint-4-renewal-cancellation` | Renewal, cancellation, dashboard, seed data, Playwright |
| 8 | `fix/published-version-not-loadable` | The recorded autonomous fix-loop |
| 9 | `docs/evidence` | TDD doc, evaluator report, final review reports |

> `main` already contains merge #1 from the personal laptop, so GitLab may show it as already merged.
> That is fine — carry on from #2.

### Set the merge method first — do this once

**Settings → Merge requests → Merge method → select "Merge commit"** → Save.
This is what keeps the individual commits and produces the merge commits the rubric looks for.

### What to write in each Merge Request

Open `docs/commit-plan.md` in the repo. Each branch has a ready-made **intent block** — copy it into the
MR description. The format is:

```
Intent: <what capability changes>
Why: <business or quality reason>
Acceptance: <observable outcome>
Out of scope: <what this does NOT include>
```

Reviewers approve at the intent level; the description is deliberately not a changelog.

### If `main` is a protected branch and the merge is blocked

Either ask for Maintainer rights on the project, or (simpler) unprotect `main` temporarily:
**Settings → Repository → Protected branches → `main` → Allowed to merge: Maintainers + Developers**.

---

## 5. After the merges

### a) Request a CI runner

The pipeline (`.gitlab-ci.yml`) will show as **pending** until a runner is attached — sandbox repos
usually have none. Raise a ticket:

> Project: `cnl-projects/<your-repo>`. Request: Enable shared runners for this project, OR attach a group
> runner with Maven/Node/Python executors. Reason: CI/CD pipelines for AI-native engineering training.
> (1) Do shared runners exist on git.virtusa.com? (2) If not, is there a sanctioned group runner I can
> request? (3) If neither, what is the approved process to attach a runner?

### b) (Optional) Enable the Claude review job

**Settings → CI/CD → Variables → Add variable**
- Key: `ANTHROPIC_API_KEY`
- Value: your Anthropic API key
- Flags: **Masked** *and* **Protected**

Protected variables only reach protected branches, so also protect the feature branches:
**Settings → Repository → Protected branches** → add `feat/*`, `chore/*`, `fix/*`, `docs/*`.

Without the key the `claude-review` job is skipped — the pipeline still passes.

### c) (Optional) Close the one open rubric caveat

The Playwright **MCP server never connected** on the personal laptop, so it is configured but was not
exercised by the evaluator. If it connects here, that bullet closes:

```bash
npx playwright install chromium
npm start                      # in one terminal
```
Then in Claude Code, ask the evaluator to drive 2–3 screens through Playwright MCP and save screenshots
to `specs/reviews/playwright-mcp/`. Commit them on a small branch and merge it.

If it does not connect, leave it — the honest caveat is already written into `docs/rubric-checklist.md`.

---

## 6. Verify the submission

```bash
git checkout main
git pull gitlab main
git log --oneline | head -20                       # merge commits visible
git log --oneline | grep -c "^[0-9a-f]* test:"     # expect 26
git log --oneline | grep -c "^[0-9a-f]* feat"      # expect 26
```

Then check on GitLab:

- [ ] `main` shows **merge commits**, not one flat squashed commit
- [ ] **No commits were pushed directly to `main`** (all arrived through MRs)
- [ ] At least **3 merged Merge Requests** (there will be 8)
- [ ] `README.md` renders on the project home page

### Prove the app still runs

```bash
npm start
```
Opens the API on http://localhost:8000 and the UI on http://localhost:3000, seeded with 3 products and
7 policies. Try: **Get a Quote → Apply → Issue → Endorse → Renew → Cancel**, and switch roles with the
header role switcher.

```bash
cd backend && uv run pytest        # 697 tests
cd ../frontend && npm test         # 98 tests
cd .. && npm run e2e               # 32 Playwright tests
```

---

## 7. If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `git.virtusa.com` will not load | Not on VPN | Connect to corporate VPN; if it still fails, raise an IT ticket |
| Push asks for credentials repeatedly | Credential helper not set | `git config --global credential.helper manager` |
| `403` / `pre-receive hook declined` | `main` is protected, or you are a Reporter | Unprotect `main` (§4) or request Developer/Maintainer access |
| Push rejected `(fetch first)` | The GitLab repo was created with a README | Push a branch instead and merge via MR, or delete the auto-created README commit |
| Pipeline stuck "pending" forever | No runner attached | Expected — raise the ticket in §5a |
| `RPC failed` then "Everything up-to-date" | Corporate proxy SSL inspection | The push often **did** succeed — refresh the GitLab repo page to check |
| Only some branches arrived | Partial push | Push the missing ones individually (§3) |

---

## 8. Where everything lives

| What you want | File |
|---|---|
| How to run the app | `README.md` |
| Rubric line → the file that satisfies it | `docs/rubric-checklist.md` |
| Branch and commit plan, MR intent blocks | `docs/commit-plan.md` |
| Business context (the reviewer reads this) | `docs/business-case.md` |
| Specs and the 24 acceptance criteria | `specs/app_spec.md` + `specs/*_spec.md` |
| Architecture with C4 and sequence diagrams | `docs/architecture.md` |
| TDD discipline + the AC-04 worked example | `docs/tdd.md` |
| Engineering decisions and accepted risks | `docs/decisions.md` |
| Lessons encoded back into rules and hooks | `docs/knowledge-deposits.md` |
| Evaluator verdict and review reports | `specs/reviews/` |
| Canonical names, endpoints, formulas | `docs/conventions.md` |

**Project state at hand-off:** 697 backend + 98 frontend + 32 Playwright tests passing · 99 % coverage ·
20,587 lines of generated code · 24/24 acceptance criteria traced · evaluator `VERDICT: PASS`.
