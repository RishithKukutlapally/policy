/**
 * Shared fixtures for the PolicyForge end-to-end suite (story E9-S4).
 *
 * `test` is the Playwright test extended with:
 *  * `apiReady` — an auto-used worker fixture that waits for `GET /health` before the first test, so a
 *    spec never races the `npm start` boot sequence (install → migrate → seed → API → UI);
 *  * `asRole` — a page helper that pins the demo user in `localStorage` *before* the first render, which
 *    is what the app reads for `X-Actor-Id` / `X-Actor-Role` (docs/conventions.md → demo users).
 *
 * Every locator below is role-, label- or `data-testid`-based (the ids are the ones the components
 * actually render) and every wait is a web-first assertion — there is no `waitForTimeout` in the suite.
 */
import { test as base, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { API_URL, BUSINESS_DATE } from '../playwright.config';

export { expect, BUSINESS_DATE, API_URL };

export type ActorRole = 'CUSTOMER' | 'UNDERWRITER' | 'ADMIN';

/** `RoleContext.ROLE_STORAGE_KEY` — the key the UI reads the demo role from. */
const ROLE_STORAGE_KEY = 'policyforge.demoRole';

/** Demo users (docs/conventions.md). The role decides the actor id the UI sends. */
export const ACTOR_IDS: Readonly<Record<ActorRole, string>> = {
  CUSTOMER: 'cust-001',
  UNDERWRITER: 'uw-001',
  ADMIN: 'admin-001',
};

export interface PolicyForgeFixtures {
  /** Pins the demo role for every subsequent navigation of this page. */
  readonly asRole: (role: ActorRole) => Promise<void>;
  /** An API client that sends the headers of `role`; used to arrange preconditions. */
  readonly apiAs: (role: ActorRole) => ApiClient;
}

export interface ApiClient {
  get: (path: string) => Promise<unknown>;
  post: (path: string, body?: unknown) => Promise<unknown>;
  put: (path: string, body?: unknown) => Promise<unknown>;
  raw: (method: 'get' | 'post' | 'put', path: string, body?: unknown) => Promise<{ status: number; json: unknown }>;
}

function client(request: APIRequestContext, role: ActorRole): ApiClient {
  const headers = {
    'X-Actor-Id': ACTOR_IDS[role],
    'X-Actor-Role': role,
    'Content-Type': 'application/json',
  };
  const raw = async (
    method: 'get' | 'post' | 'put',
    path: string,
    body?: unknown,
  ): Promise<{ status: number; json: unknown }> => {
    const response = await request[method](`${API_URL}${path}`, {
      headers,
      ...(body === undefined ? {} : { data: body }),
    });
    const text = await response.text();
    return { status: response.status(), json: text === '' ? null : (JSON.parse(text) as unknown) };
  };
  const expectOk = async (method: 'get' | 'post' | 'put', path: string, body?: unknown): Promise<unknown> => {
    const { status, json } = await raw(method, path, body);
    if (status >= 400) {
      throw new Error(`${method.toUpperCase()} ${path} failed with ${status}: ${JSON.stringify(json)}`);
    }
    return json;
  };
  return {
    get: (path) => expectOk('get', path),
    post: (path, body) => expectOk('post', path, body),
    put: (path, body) => expectOk('put', path, body),
    raw,
  };
}

export const test = base.extend<PolicyForgeFixtures, { apiReady: void }>({
  apiReady: [
    async ({ playwright }, use) => {
      const request = await playwright.request.newContext();
      // The UI answers before uvicorn does; poll the only un-prefixed route until the API is up.
      await expect
        .poll(
          async () => {
            try {
              return (await request.get(`${API_URL}/health`)).status();
            } catch {
              return 0;
            }
          },
          { message: 'the API never became healthy', timeout: 180_000, intervals: [500] },
        )
        .toBe(200);
      await request.dispose();
      await use();
    },
    { scope: 'worker', auto: true },
  ],

  asRole: async ({ page }, use) => {
    await use(async (role: ActorRole): Promise<void> => {
      await page.addInitScript(
        ([key, value]) => window.localStorage.setItem(key, value),
        [ROLE_STORAGE_KEY, role] as const,
      );
    });
  },

  apiAs: async ({ request }, use) => {
    await use((role: ActorRole) => client(request, role));
  },
});

/**
 * Regions whose text legitimately changes between runs — UUIDs, policy numbers, dates and timestamps —
 * are masked out of the visual baselines. The values themselves are asserted as text by the specs, so
 * nothing is lost: only the pixels that cannot be stable are excluded.
 */
export function volatileRegions(page: Page): Locator[] {
  return [
    page.locator('code'),
    page.locator('.mono'),
    page.locator('.num'),
    page.locator('.hdrs'),
    page.locator('.timeline'),
    page.locator('time'),
  ];
}

/** One committed visual baseline per key screen, per project (AC-24). */
export async function screenshotScreen(page: Page, name: string): Promise<void> {
  await expect(page).toHaveScreenshot(`${name}.png`, {
    mask: volatileRegions(page),
    maskColor: '#c8c8c8',
    fullPage: false,
  });
}

/** The single policy-status badge of a screen (`StatusBadge` defaults to `status-badge`). */
export function statusBadge(page: Page): Locator {
  return page.getByTestId('status-badge').first();
}
