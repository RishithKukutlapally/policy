/**
 * Issuance, My Policies, Policy Detail and endorsement — AC-05, AC-15, AC-06, AC-16
 * (stories E5-S3 / E6-S3 / E9-S4).
 *
 * The endorsement delta is previewed with `?preview=true` (nothing persisted) and the figure the
 * customer confirms is the same signed decimal string the server returns on the 201 — the append-only
 * history row is read back from the API-backed screen, not echoed optimistically (NFR-02).
 */
import { test, expect, screenshotScreen, statusBadge } from '../fixtures/app';
import {
  MOTOR_AUTO_BIND,
  MOTOR_POLICY_NUMBER,
  RUPEES,
  arrangeApplication,
  arrangePolicy,
} from '../fixtures/data';

test.describe('Policy lifecycle (AC-05, AC-06, AC-15, AC-16)', () => {
  test('AC-05 AC-15 customer issues a MOTOR policy and sees it ACTIVE on My Policies', async ({
    page,
    asRole,
    apiAs,
  }) => {
    const { application } = await arrangeApplication(apiAs('CUSTOMER'), MOTOR_AUTO_BIND, 41);
    expect(application.decision).toBe('AUTO_BIND');

    await asRole('CUSTOMER');
    await page.goto(`/policies?application=${application.application_id}`);
    await page.getByRole('button', { name: 'Issue policy' }).click();

    // Issuance navigates straight to the new policy's detail screen.
    await expect(page).toHaveURL(/\/policies\/MO-\d{4}-\d{6}$/);
    const policyNumber = (new URL(page.url()).pathname.split('/').pop() ?? '');
    expect(policyNumber).toMatch(MOTOR_POLICY_NUMBER);

    await expect(page.getByTestId('policy-detail')).toBeVisible();
    await expect(statusBadge(page)).toHaveText('ACTIVE');
    await expect(page.getByTestId('detail-status')).toContainText('Status ACTIVE');
    await expect(page.getByTestId('detail-premium')).toHaveText(RUPEES);
    await expect(page.getByTestId('detail-aadhaar')).toHaveText(/^XXXX-XXXX-\d{4}$/);
    await expect(page.getByTestId('payments')).toBeVisible();
    await expect(page.getByTestId('lifecycle')).toContainText('ACTIVE');
    await screenshotScreen(page, 'policy-detail');

    await page.getByRole('link', { name: '← Back to My Policies' }).click();
    await expect(page.getByRole('heading', { name: 'My Policies', level: 1 })).toBeVisible();
    await expect(page.getByTestId('policy-list')).toBeVisible();
    const row = page.locator(`[data-testid="policy-open"][data-policy-number="${policyNumber}"]`);
    await expect(row).toHaveText(policyNumber);
    await screenshotScreen(page, 'policies');
  });

  test('AC-06 AC-16 customer endorses the sum insured after previewing the pro-rated delta', async ({
    page,
    asRole,
    apiAs,
  }) => {
    const policy = await arrangePolicy(apiAs('CUSTOMER'), MOTOR_AUTO_BIND, 42);

    await asRole('CUSTOMER');
    await page.goto(`/policies/${policy.policy_number}/endorse`);
    await expect(page.getByRole('heading', { name: `Endorse ${policy.policy_number}` })).toBeVisible();

    await page.getByLabel('Endorsement type').selectOption('CHANGE_SUM_INSURED');
    await page.getByLabel('Sum insured', { exact: true }).fill('600000.00');
    await page.getByRole('button', { name: 'Preview premium change' }).click();

    const delta = page.getByTestId('preview-delta');
    await expect(page.getByTestId('preview-result')).toBeVisible();
    await expect(delta).toHaveText(/^\+₹\d{1,3}(,\d{2,3})*\.\d{2}$/);
    const previewed = (await delta.textContent()) ?? '';
    await expect(page.getByTestId('preview-result')).toContainText('nothing has been saved');
    await screenshotScreen(page, 'endorse');

    await page.getByRole('button', { name: 'Submit endorsement' }).click();

    // The confirmation quotes the persisted delta, which must equal the preview (AC-16).
    await expect(page.getByTestId('endorsement-confirmation')).toContainText(previewed);
    await expect(page.getByTestId('endorsement-confirmation')).toContainText('CHANGE_SUM_INSURED');
    await expect(page.getByTestId('endorsement-history')).toContainText('Sum insured ₹6,00,000.00');
    await expect(statusBadge(page)).toHaveText('ENDORSED');

    await page.goto(`/policies/${policy.policy_number}`);
    await expect(statusBadge(page)).toHaveText('ENDORSED');
    await expect(page.getByTestId('endorsement-history')).toContainText(previewed);
    await expect(page.getByTestId('lifecycle')).toContainText('ENDORSED');
  });
});
