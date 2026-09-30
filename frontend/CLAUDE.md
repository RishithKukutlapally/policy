# frontend/ — PolicyForge UI (React · Vite · TypeScript)

Inherits the root `CLAUDE.md`.

## Commands

`npm run dev -- --port 3000` · `npm test` (vitest) · `npm run lint` · `npm run typecheck` · `npm run build`

## Structure

```
src/api/         typed client for the backend (one module per resource)
src/pages/       Quote · Apply · MyPolicies · PolicyDetail · Endorse · UnderwriterWorkbench ·
                 ProductCatalog · AdminDashboard
src/components/  shared UI (forms, tables, status badges, layout shell)
src/types/       DTO types mirroring specs/design/api-contracts.md
```

## Rules

- **Responsive layout required** (rubric): mobile-first CSS grid/flex with at least one breakpoint;
  the layout shell collapses the side nav below 768 px.
- Money arrives as decimal strings — display with `Intl.NumberFormat`; never do money arithmetic with
  `number` (NFR-01). Calculations belong to the backend.
- Never `console.log` form data that may hold Aadhaar/PAN/health answers (hook `pii-redaction-check`);
  mask Aadhaar/PAN inputs on screen.
- Every interactive element has an accessible name / `data-testid` used by Playwright (`e2e/`).
- Zero `any`. Role is chosen via a demo role switcher that sets `X-Actor-Id` / `X-Actor-Role` headers.
