/**
 * Renewal, end-of-day and cancellation — AC-07, AC-17, AC-18, AC-08, AC-19
 * (stories E7-S2…E7-S4 / E8-S3 / E9-S4).
 *
 * The suite runs on the fixed business date pinned in `playwright.config.ts`, which is what makes these
 * journeys deterministic (DEC-012): the seeded 2026-07-01 terms are inside their renewal window, the
 * unpaid one is past its grace period, and a policy issued during the test is inside its free-look days.
 *
 * Order matters inside this file: the renewal journey consumes a seeded renewable policy before the
 * end-of-day run sweeps the rest, and end-of-day runs last because it moves policies to terminal states.
 */
import { test, expect, screenshotScreen, statusBadge, BUSINESS_DATE } from '../fixtures/app';
import { MOTOR_AUTO_BIND, RUPEES, arrangePolicy } from '../fixtures/data';

/**
 * Seeded demo portfolio (backend/src/seed_data/timeline.py): four live terms that started 2026-07-01 and
 * expire 2026-06-30 + 12 months, i.e. inside their renewal window on the configured business date.
 *
 * Renewing a policy is irreversible, so the two projects run the same journey on *different* seeded
 * policies — the database is shared by both projects of one run.
 */
const RENEWED_BY_UI: Readonly<Record<string, string>> = {
  desktop: 'MO-2026-000001',
  mobile: 'MO-2026-000003',
};
const RENEWED_BY_END_OF_DAY: Readonly<Record<string, string>> = {
  desktop: 'HH-2026-000001',
  mobile: 'TL-2026-000001',
};
/**
 * After the seeded terms expired (2027-06-30) but inside their 30-day grace (ends 2027-07-31): the paid
 * term renews and the unpaid ones are only reported `IN_GRACE`, so this run never takes a policy the
 * other project still needs.
 */
const END_OF_DAY_DATE = '2027-07-10';

const MONEY = /₹\d{1,3}(,\d{2,3})*\.\d{2}/;

interface RenewalQuote {
  readonly renewable: boolean;
  readonly renewal_premium: string;
  readonly due_date: string;
}

test.describe('Renewal, end-of-day and cancellation (AC-07, AC-08, AC-17, AC-18, AC-19)', () => {
  test('AC-07 AC-17 customer pays the renewal premium and renews the policy', async ({
    page,
    asRole,
    apiAs,
  }, testInfo) => {
    const policyNumber = RENEWED_BY_UI[testInfo.project.name] ?? '';
    const quote = (await apiAs('CUSTOMER').get(
      `/api/policies/${policyNumber}/renewal`,
    )) as RenewalQuote;
    expect(
      quote.renewable,
      `${policyNumber} must be inside its renewal window on business date ${BUSINESS_DATE} — check the seeded demo calendar`,
    ).toBe(true);

    await asRole('CUSTOMER');
    await page.goto(`/policies/${policyNumber}/renew`);

    await expect(page.getByRole('heading', { name: `Renew ${policyNumber}` })).toBeVisible();
    await expect(page.getByTestId('renewal-premium')).toHaveText(RUPEES);
    await expect(page.getByTestId('due-date')).toHaveText(quote.due_date);
    await expect(page.getByTestId('payment-status')).toHaveText('UNPAID');

    await page.getByRole('button', { name: 'Pay premium' }).click();
    await expect(page.getByTestId('payment-status')).toHaveText('PAID');
    await expect(page.getByRole('status').filter({ hasText: 'Renewal premium' })).toBeVisible();

    await page.getByRole('button', { name: 'Renew now' }).click();

    const successor = page.getByTestId('successor-link');
    await expect(page.getByTestId('successor')).toBeVisible();
    await expect(successor).toHaveText(/^(TL|MO|HH)-\d{4}-\d{6}$/);
    await expect(page.getByTestId('successor-status')).toHaveText('ACTIVE');
    const successorNumber = (await successor.textContent()) ?? '';
    expect(successorNumber).not.toBe(policyNumber);

    // The old term is terminal and points at the new one; the new term starts ACTIVE (AC-07).
    await page.goto(`/policies/${policyNumber}`);
    await expect(statusBadge(page)).toHaveText('RENEWED');
    await expect(page.getByTestId('policy-detail')).toContainText(successorNumber);

    await page.goto(`/policies/${successorNumber}`);
    await expect(statusBadge(page)).toHaveText('ACTIVE');
    await expect(page.getByTestId('policy-detail')).toContainText(policyNumber);
  });

  test('AC-08 AC-19 customer cancels inside the free-look window and the refund matches the preview', async ({
    page,
    asRole,
    apiAs,
  }) => {
    const policy = await arrangePolicy(apiAs('CUSTOMER'), MOTOR_AUTO_BIND, 51);

    await asRole('CUSTOMER');
    await page.goto(`/policies/${policy.policy_number}/cancel`);
    await expect(page.getByRole('heading', { name: `Cancel ${policy.policy_number}` })).toBeVisible();

    await page.getByLabel('Cancellation date').fill(BUSINESS_DATE);
    await page.getByLabel('Reason').fill('Bought cover elsewhere');

    const sentence = page.getByTestId('refund-sentence');
    await expect(sentence).toBeVisible();
    await expect(sentence).toContainText('Full refund');
    const previewed = MONEY.exec((await sentence.textContent()) ?? '')?.[0] ?? '';
    expect(previewed).not.toBe('');
    await screenshotScreen(page, 'cancel');

    await page.getByRole('button', { name: 'Confirm cancellation' }).click();
    const dialog = page.getByRole('dialog', { name: `Cancel ${policy.policy_number}?` });
    await expect(dialog).toContainText(previewed);
    await page.getByTestId('dialog-confirm').click();

    // The persisted refund row, not the preview, is what the confirmation renders (AC-19).
    await expect(page.getByTestId('cancel-confirmation')).toContainText(previewed);
    await expect(statusBadge(page)).toHaveText('CANCELLED');
    await expect(page.getByTestId('refund-amount')).toHaveText(previewed);

    await page.goto(`/policies/${policy.policy_number}`);
    await expect(statusBadge(page)).toHaveText('CANCELLED');
    await expect(page.getByTestId('refunds')).toContainText('FREE_LOOK');
    await expect(page.getByTestId('lifecycle')).toContainText('CANCELLED');
  });

  test('AC-18 admin runs end-of-day twice and the second run reports zeros', async ({
    page,
    asRole,
    apiAs,
  }, testInfo) => {
    const policyNumber = RENEWED_BY_END_OF_DAY[testInfo.project.name] ?? '';
    const quote = (await apiAs('CUSTOMER').get(
      `/api/policies/${policyNumber}/renewal`,
    )) as RenewalQuote;
    // Paid renewal premium → the scheduler renews this term at the end-of-day date below.
    await apiAs('CUSTOMER').post(`/api/policies/${policyNumber}/payments`, {
      amount: quote.renewal_premium,
    });

    await asRole('ADMIN');
    await page.goto('/admin/end-of-day');
    await expect(page.getByRole('heading', { name: 'Run end-of-day', level: 1 })).toBeVisible();
    await expect(page.getByTestId('eod-empty')).toBeVisible();

    await page.getByLabel('As of').fill(END_OF_DAY_DATE);
    await page.getByRole('button', { name: 'Run end-of-day' }).click();

    await expect(page.getByTestId('eod-result')).toBeVisible();
    await expect(page.getByTestId('count-renewed')).toHaveText(/^Renewed: [1-9]\d*$/);
    await expect(page.getByTestId('count-failed')).toHaveText('Failed: 0');
    await expect(page.getByTestId('eod-renewed')).toContainText(policyNumber);

    // Same date again: the job is idempotent, so there is nothing left to do (AC-18).
    await page.getByRole('button', { name: 'Run end-of-day' }).click();
    await expect(page.getByTestId('count-renewed')).toHaveText('Renewed: 0');
    await expect(page.getByTestId('count-lapsed')).toHaveText('Lapsed: 0');
    await expect(page.getByRole('status').filter({ hasText: 'already processed' })).toBeVisible();

    // The renewed term is terminal and its successor is live — the run really did the work once.
    await asRole('CUSTOMER');
    await page.goto(`/policies/${policyNumber}`);
    await expect(statusBadge(page)).toHaveText('RENEWED');
  });
});
