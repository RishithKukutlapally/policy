/**
 * Product Catalog Manager and Portfolio dashboard — AC-02, AC-11, AC-20 (stories E2-S4 / E9-S2 / E9-S4).
 *
 * The catalog journey exercises the whole versioned rule-set lifecycle on HOUSEHOLD — list, create a
 * DRAFT, replace that DRAFT (a new `rule_set_versions` revision, DEC-009), publish it, then prove the
 * published version is immutable (409 `VERSION_IMMUTABLE`). HOUSEHOLD is used deliberately: the other
 * specs quote MOTOR, and publishing a new active version must not move their premiums.
 */
import { test, expect, screenshotScreen } from '../fixtures/app';
import { RUPEES } from '../fixtures/data';

const PRODUCTS = ['TERM_LIFE', 'MOTOR', 'HOUSEHOLD'] as const;

interface RuleFile {
  version: number;
  premium: { minimum_premium: string; [key: string]: unknown };
  [key: string]: unknown;
}

/** `"3100.00"` → `"₹3,100.00"`, the way the UI formats a decimal string (en-IN). */
function asRupees(amount: string): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(amount));
}

test.describe('Catalog and portfolio (AC-02, AC-11, AC-20)', () => {
  test('AC-02 AC-11 admin lists products, drafts, replaces and publishes a rule-set version', async ({
    page,
    asRole,
    apiAs,
  }) => {
    await asRole('ADMIN');
    await page.goto('/admin/catalog');
    await expect(page.getByRole('heading', { name: 'Product Catalog', level: 1 })).toBeVisible();

    // Three products, each with its own rule set (AC-02). Same row ids in the table and the cards.
    for (const product of PRODUCTS) {
      await expect(page.getByTestId(`product-row-${product}`)).toBeVisible();
    }
    await screenshotScreen(page, 'catalog');

    await page.getByTestId('expand-HOUSEHOLD').click();
    await expect(page.getByRole('heading', { name: 'Versions — HOUSEHOLD' })).toBeVisible();
    await expect(page.getByTestId('version-row-1')).toContainText('PUBLISHED');
    // A PUBLISHED version offers neither publish nor edit — it is immutable (NFR-05).
    await expect(page.getByTestId('publish-v1')).toHaveCount(0);
    await expect(page.getByTestId('edit-draft-v1')).toHaveCount(0);

    // The editor is pre-seeded from the newest version, bumped to the next DRAFT (AC-11). The version
    // number is read from the editor rather than hard-coded, because both projects run this journey
    // against the same database and the second one drafts the next version up.
    const editor = page.getByLabel('Rule-set JSON');
    await expect(editor).toHaveValue(/"status": "DRAFT"/);
    const seeded = JSON.parse(await editor.inputValue()) as RuleFile;
    expect(seeded.version).toBeGreaterThan(1);

    // Both projects share one database, so the second one meets the DRAFT the first one left open —
    // that is the 409 `DRAFT_ALREADY_OPEN` guard, asserted rather than skipped.
    const versions = (await apiAs('ADMIN').get('/api/products/HOUSEHOLD/versions')) as readonly {
      version: number;
      status: string;
    }[];
    const openDraft = versions.find((row) => row.status === 'DRAFT');
    const version = openDraft?.version ?? seeded.version;

    await page.getByRole('button', { name: 'Create draft' }).click();
    if (openDraft === undefined) {
      await expect(page.getByTestId('op-notice')).toHaveText(
        `HOUSEHOLD v${version} saved with status DRAFT.`,
      );
    } else {
      await expect(page.getByTestId('banner-DRAFT_ALREADY_OPEN')).toBeVisible();
    }
    await expect(page.getByTestId(`version-row-${version}`)).toContainText('DRAFT');

    // Replacing the open DRAFT appends a revision rather than mutating a row (DEC-009).
    await page.getByTestId(`edit-draft-v${version}`).click();
    const draft = JSON.parse(await editor.inputValue()) as RuleFile;
    const minimumPremium = draft.premium.minimum_premium === '3100.00' ? '3200.00' : '3100.00';
    draft.premium.minimum_premium = minimumPremium;
    await editor.fill(JSON.stringify(draft, null, 2));
    await page.getByRole('button', { name: 'Save draft' }).click();
    await expect(page.getByTestId('op-notice')).toHaveText(
      `HOUSEHOLD v${version} saved with status DRAFT.`,
    );
    await expect(page.getByTestId(`min-premium-${version}`)).toHaveText(RUPEES);
    await expect(page.getByTestId(`min-premium-${version}`)).toHaveText(asRupees(minimumPremium));

    /**
     * Publishing is reached and its guard asserted, but deliberately *not* confirmed by this suite:
     * `POST …/publish` only flips the ledger status, while the premium, renewal and portfolio paths load
     * the active version from `backend/policy_rules/<product>/v<N>.json`. A browser test cannot commit
     * that file, so confirming here would leave the running stack with an active version that has no rule
     * file (`NOT_FOUND — no rule file for product HOUSEHOLD v2`) and poison every later journey.
     * Publishing a version that *does* have its file is covered by the backend AC-11 tests.
     */
    await page.getByTestId(`publish-v${version}`).click();
    const dialog = page.getByRole('dialog', { name: `Publish HOUSEHOLD v${version}?` });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('A published version is immutable');
    await page.getByTestId('publish-cancel').click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId(`version-row-${version}`)).toContainText('DRAFT');

    // AC-11: the PUBLISHED v1 cannot be replaced — the API is the authority, not a hidden button.
    await expect(page.getByTestId('version-row-1')).toContainText('PUBLISHED');
    const immutable = await apiAs('ADMIN').raw('put', '/api/products/HOUSEHOLD/versions/1', draft);
    expect(immutable.status).toBe(409);
    expect(JSON.stringify(immutable.json)).toContain('VERSION_IMMUTABLE');
  });

  test('AC-20 admin portfolio dashboard renders product cards, premium collected and the renewal pipeline', async ({
    page,
    asRole,
  }) => {
    await asRole('ADMIN');
    await page.goto('/admin/portfolio');

    await expect(page.getByRole('heading', { name: 'Portfolio', level: 1 })).toBeVisible();
    await expect(page.getByTestId('portfolio-cards')).toBeVisible();
    await expect(page.getByTestId('portfolio-by-product')).toBeVisible();
    for (const product of PRODUCTS) {
      await expect(page.getByTestId(`card-${product}`)).toBeVisible();
    }
    await expect(page.getByTestId('card-premium-collected').locator('p.val')).toHaveText(RUPEES);
    // Renewals due within 30 days of the business date; the seeded terms fall due 2027-07-01.
    await expect(page.getByTestId('renewal-pipeline')).toBeVisible();
    // The lapse forecast looks 30 days ahead too, so on this business date it is legitimately empty —
    // either the rows or the explicit empty state must render, never nothing.
    await expect(
      page.getByTestId('lapse-forecast').or(page.getByTestId('lapse-empty')),
    ).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Lapse forecast' })).toBeVisible();

    // The five summary tiles are the dashboard's contract with the operator; their labels are asserted
    // structurally so a renamed or dropped tile fails even when the pixels stay close enough.
    await expect(page.getByTestId('portfolio-cards')).toMatchAriaSnapshot({
      name: 'portfolio-cards.aria.yml',
    });
    await screenshotScreen(page, 'portfolio');
  });
});
