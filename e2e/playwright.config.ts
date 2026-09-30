/**
 * Playwright configuration — story E9-S4 (AC-24).
 *
 * Two projects drive the same specs at the two viewports the responsive layout is designed for
 * (`desktop` 1280×800 and `mobile` 390×844), so every committed screenshot exists twice and the
 * mobile-only behaviour (side nav behind "Open navigation", tables as stacked cards) is proven rather
 * than asserted on paper.
 *
 * Determinism (the committed baselines must match on a clean run):
 *  * `webServer` resets a dedicated SQLite file and boots API + UI through the repo's own `npm start`,
 *    pinning `POLICYFORGE_BUSINESS_DATE` so "today" — and therefore free-look refunds, renewal windows
 *    and lapse dates — is the same on every machine and in CI (DEC-012).
 *  * one worker and no retries: the specs create their own quotes, applications and policies, so their
 *    order is part of the fixture. Re-running them concurrently would change what the list screens show.
 *  * snapshots live next to the spec in `tests/<spec>.spec.ts-snapshots/` and are committed;
 *    `updateSnapshots: 'none'` in CI turns a drift into a failure instead of a silent rewrite.
 *
 * The baseline names carry the project but not the platform (AC-24 asks for 9 screens × 2 projects = 18
 * images), so the committed images are the ones rendered by the machine that generated them. Text
 * rasterisation differs between Windows and the CI Playwright image, so the first CI run on a new image
 * needs `npm run e2e:update` once and its images committed — `maxDiffPixelRatio` absorbs anti-aliasing,
 * not a different font stack. Every value shown in an image is also asserted as text, so a stale image
 * can never hide a behavioural regression.
 */
import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';

// The root `package.json` declares `"type": "module"`, so this config is ESM — no `__dirname`.
const ROOT = fileURLToPath(new URL('..', import.meta.url));
const UI_PORT = 3000;
const API_PORT = 8000;

/**
 * The fixed business date the stack runs on. It sits inside the renewal window of the seeded
 * 2026-07-01 terms (`backend/src/seed_data/timeline.py`) and inside the free-look days of anything the
 * specs issue themselves, which is what makes the renewal, lapse and refund journeys deterministic.
 */
export const BUSINESS_DATE = '2027-06-15';
// Vite binds `localhost`; using the same host everywhere keeps the UI and its /api proxy in one origin.
export const BASE_URL = `http://localhost:${UI_PORT}`;
export const API_URL = `http://localhost:${API_PORT}`;

const isCI = process.env.CI !== undefined && process.env.CI !== '';

export default defineConfig({
  testDir: './tests',
  // One committed image per screen per project, beside the spec that owns it.
  snapshotPathTemplate: '{testDir}/{testFileName}-snapshots/{arg}-{projectName}{ext}',
  outputDir: './test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: isCI,
  timeout: 90_000,
  updateSnapshots: isCI ? 'none' : 'missing',
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      // Font rasterisation differs slightly between machines; text content is asserted separately.
      maxDiffPixelRatio: 0.02,
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },
  reporter: [['list'], ['html', { outputFolder: './playwright-report', open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    timezoneId: 'Asia/Kolkata',
    locale: 'en-IN',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: 'node e2e/scripts/reset-db.mjs && npm start',
    cwd: ROOT,
    url: BASE_URL,
    reuseExistingServer: !isCI,
    timeout: 300_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      POLICYFORGE_BUSINESS_DATE: BUSINESS_DATE,
      POLICYFORGE_DATABASE_URL: 'sqlite:///./policyforge-e2e.db',
      POLICYFORGE_API_PORT: String(API_PORT),
      POLICYFORGE_UI_PORT: String(UI_PORT),
    },
  },
});
