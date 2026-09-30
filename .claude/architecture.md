# Architecture

## Layer Hierarchy

The project follows a strict layered architecture. Dependencies flow **downward only** — a layer may import from layers below it but never from layers above it.

```
┌─────────────┐
│     UI      │  ← Layer 7 (highest)
├─────────────┤
│     API     │  ← Layer 6
├─────────────┤
│   Service   │  ← Layer 5
├─────────────┤
│ Repository  │  ← Layer 4
├─────────────┤
│   Config    │  ← Layer 3
├─────────────┤
│   Domain    │  ← Layer 2 (PolicyForge: pure business rules)
├─────────────┤
│    Types    │  ← Layer 1 (lowest)
└─────────────┘
```

### Layer Definitions

| Layer | Responsibility | May Import From |
|-------|---------------|-----------------|
| Types | Domain models, interfaces, enums, shared type definitions | (none) |
| Domain *(PolicyForge)* | Pure business rules: premium, underwriting, state machine, endorsement, renewal, refund | Types |
| Config | Environment variables, feature flags, constants, app configuration, rule-file loading | Types, Domain |
| Repository | Data access, persistence, external data sources | Types, Config |
| Service | Business logic orchestration, transactions, audit | Types, Domain, Config, Repository |
| API | Route handlers, request/response mapping, middleware, validation | Types, Config, Service (not Repository) |
| UI | Components, pages, client-side state, rendering | Types, Config, Service, API |
| Lib *(cross-cutting)* | Logger with PII masking, correlation id | standard library only — importable by every layer |

> **PolicyForge:** backend layers live in `backend/src/<layer>/` and import as `from src.<layer> ...`.
> The canonical rules are in `docs/conventions.md` ("Layer import rules") and are enforced by
> import-linter contracts, `backend/tests/architecture/`, and the `check-architecture` / `pre-commit-gate` hooks.

## One-Way Dependency Rule

**Never import from a higher layer.**

Violations:
- A `Service` importing from `API` — FORBIDDEN
- A `Repository` importing from `Service` — FORBIDDEN
- A `Config` importing from `Repository` — FORBIDDEN
- A `Types` importing from any other layer — FORBIDDEN

The `check-architecture` hook enforces this rule on every file save.

## Verification Commands

### Types layer
```bash
# No imports from Config, Repository, Service, API, or UI
grep -rn "from.*config\|from.*repository\|from.*service\|from.*api\|from.*ui" src/types/
```

### Config layer
```bash
# No imports from Repository, Service, API, or UI
grep -rn "from.*repository\|from.*service\|from.*api\|from.*ui" src/config/
```

### Repository layer
```bash
# No imports from Service, API, or UI
grep -rn "from.*service\|from.*api\|from.*ui" src/repository/
```

### Service layer
```bash
# No imports from API or UI
grep -rn "from.*api\|from.*ui" src/service/
```

### API layer
```bash
# No imports from UI
grep -rn "from.*ui" src/api/
```

### Full architecture audit
```bash
# Run the architecture check hook directly
.claude/hooks/check-architecture.sh
```

## Cross-Cutting Concerns

The following concerns span all layers and are handled via shared utilities, not inline in each layer:

| Concern | Implementation |
|---------|---------------|
| **Logging** | Centralized logger (e.g., `src/lib/logger`) — all layers import from `lib`, not from each other |
| **Authentication** | Auth context passed via dependency injection or middleware; never hardcoded per-layer |
| **Telemetry** | Instrumentation via a shared `src/lib/telemetry` module with span/trace helpers |
| **Error Handling** | Typed error classes in `Types`; caught and mapped at `API` boundary; never swallowed silently |

## Customization

Layer names, paths, and verification commands can be overridden for non-standard stacks (e.g., monorepos, microservices, full-stack frameworks) via `project-manifest.json` in the project root.

Example override:
```json
{
  "layers": [
    { "name": "domain", "path": "src/domain", "rank": 1 },
    { "name": "application", "path": "src/application", "rank": 2 },
    { "name": "infrastructure", "path": "src/infrastructure", "rank": 3 },
    { "name": "presentation", "path": "src/presentation", "rank": 4 }
  ]
}
```

When `project-manifest.json` is present, the `check-architecture` hook reads layer definitions from it instead of using the defaults above.

> **PolicyForge note:** the shipped `check-architecture`, `pre-commit-gate` and `task-completed` hooks do
> **not** read the manifest — they hard-code the layer list. PolicyForge updated that list to
> `types → domain → config → repository → service → api` plus explicit extra rules
> (repository ↛ domain, api ↛ repository/domain) to match `docs/conventions.md`; the manifest's `layers`
> block documents the same order for other tooling.
