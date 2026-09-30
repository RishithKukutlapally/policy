---
name: build
description: Full SDLC pipeline. Runs all phases end-to-end with human gates on phases 1-3.
argument-hint: "[path-to-BRD] [--mode full|lean|solo]"
context: fork
---

# Build Skill

Full software development lifecycle pipeline. Orchestrates BRD creation, story specification, architecture design, state initialization, and autonomous build execution across 8 sequential phases.

---

## Usage

```
/build path/to/requirements.md
/build path/to/requirements.md --mode lean
/build path/to/requirements.md --mode solo
```

The `--mode` flag controls which ratchet gates `/auto` enforces. Default: `full`.

---

## 8-Phase Pipeline

### Phase 1 — Business Requirements [HUMAN APPROVAL]

Run `/brd` with the provided requirements document. Outputs are written to `specs/brd/`.

**Stop and wait for explicit human approval before proceeding.** Present a summary of the BRD and ask: "Approve BRD to proceed to Phase 2?"

Do NOT proceed without a clear "yes" or "approved" from the user.

### Phase 2 — Story Specification [HUMAN APPROVAL]

Run `/spec` using the approved BRD. Outputs are written to `specs/stories/` and `features.json`.

**Stop and wait for explicit human approval before proceeding.** Present the story count, dependency groups, and feature list. Ask: "Approve stories to proceed to Phase 3?"

Do NOT proceed without a clear "yes" or "approved" from the user.

### Phase 3 — Architecture Design [HUMAN APPROVAL]

Run `/design` using the approved stories. Outputs are written to `specs/design/` including `api-contracts.md`, `component-map.md`, and schema files.

**Stop and wait for explicit human approval before proceeding.** Present the architecture summary: tech stack, component count, API surface area. Ask: "Approve design to proceed to autonomous build?"

Do NOT proceed without a clear "yes" or "approved" from the user.

### Phase 4 — Initialize State

Create the following state files before entering the autonomous loop:

1. `.claude/state/coverage-baseline.txt` — Write `0` (initial baseline).
2. `.claude/state/iteration-log.md` — Write header: `# Iteration Log\n\nTracking all autonomous build iterations.\n`
3. `claude-progress.txt` — Write session 0 block:
   ```
   === Session 0 ===
   date: {ISO 8601 now}
   mode: {mode}
   groups_completed: []
   groups_remaining: [all group IDs from dependency-graph.md]
   current_group: none
   features_passing: 0 / {total features}
   coverage: 0%
   learned_rules: 0
   next_action: Begin autonomous build with /auto
   ```

### Phases 5-8 — Autonomous Execution

Run `/auto --mode {mode}` to enter the autonomous build loop. The `/auto` skill handles all remaining execution: sprint contracts, agent teams, ratchet gates, self-healing, and session chaining.

### Phase 9 — Generate README.md

After `/auto` completes (all groups done or stopping criteria met), generate a `README.md` for the built application. This is the developer-facing guide for running, understanding, and contributing to the generated project.

Read the following to build the README:
- `specs/brd/brd.md` — what the app does (project description)
- `specs/design/architecture.md` — system architecture
- `specs/design/api-contracts.md` or `api-contracts.schema.json` — API surface
- `specs/design/component-map.md` — module structure
- `project-manifest.json` — tech stack, verification mode
- `init.sh` — setup steps
- `docker-compose.yml` (if exists) — services
- `.env.example` (if exists) — required environment variables

**README must include these sections:**

```markdown
# {Project Name}

{1-2 sentence description from BRD}

## Architecture

{System diagram: layers, services, data flow. Use ASCII art or bullet list.
Show: frontend -> API -> service -> repository -> database.
Note external APIs if any.}

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | {from manifest} |
| Frontend | {from manifest} |
| Database | {from manifest} |
| Testing | {from manifest} |

## Prerequisites

- {language version}
- Docker + Docker Compose
- {any external API keys needed — reference .env.example}

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url> && cd {project-name}

# 2. Copy environment config
cp .env.example .env
# Edit .env with your API keys

# 3. Start everything
bash init.sh
# OR: docker compose up -d

# 4. Verify
curl http://localhost:{port}/health
```

## API Endpoints

{Table of all endpoints from api-contracts: method, path, description, auth required}

## Project Structure

```
{Directory tree showing key files and their responsibilities.
 Use component-map.md as source. Show backend/, frontend/, tests/}
```

## Running Tests

```bash
# Backend
cd backend && uv run pytest --cov=src -v

# Frontend
cd frontend && npm test
```

## Environment Variables

{Table from .env.example: variable name, description, required/optional, example value}

## Development

{Brief notes on: how to add a new endpoint, how to run linters,
 how to run the app locally without Docker}
```

**Rules:**
- README describes the GENERATED APP, not the harness. Do not mention Claude, the harness, `/auto`, or agents.
- All commands must be tested — run them mentally against the generated code to verify they work.
- API endpoint table must match the actual routes in the code, not just the spec.
- Environment variables table must match `.env.example` exactly.

Commit the README: `git add README.md && git commit -m "docs: add README with architecture, setup, and API reference"`

---

## Mode Reference

| Mode | Description |
|------|-------------|
| `full` | All ratchet gates including design critic and GAN loop |
| `lean` | Skip design critic and GAN loop; keep API + Playwright checks |
| `solo` | Generator works alone; skip evaluator, team, and Docker checks |

---

## Gotchas

- **Proceeding without approval:** Phases 1-3 each require explicit human approval. Silence is not consent. If the user has not clearly approved, ask again.
- **Skipping the design phase:** Phase 3 produces `component-map.md` and `api-contracts.md` which are required by `/auto` for sprint contracts and file ownership. Skipping design breaks the entire downstream pipeline.
- **Not initializing state files:** Phase 4 must create all three state files before `/auto` runs. Missing state files cause context recovery failures in session chaining.
- **Wrong mode passthrough:** Read the `--mode` flag from the user's invocation and pass it to `/auto` exactly. Do not default silently if the user specified a mode.
