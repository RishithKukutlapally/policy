/**
 * Get a Quote — AC-01 (story E3-S3 / E9-S4).
 *
 * The premium on screen must be the one the active PUBLISHED rule version produces, so the test asserts
 * the rendered figure *and* compares its digits with the same quote taken straight from `POST /api/quotes`.
 * The UI is allowed to format (`₹14,322.00`); it is not allowed to compute (NFR-01).
 */
import { test, expect, screenshotScreen } from '../fixtures/app';
import { MOTOR_AUTO_BIND, RUPEES, createQuote } from '../fixtures/data';

/** `₹14,322.00` → `14322.00`, so a display string can be compared with an API decimal string. */
function digitsOf(text: string): string {
  return text.replace(/[^\d.]/g, '');
}

test.describe('Get a Quote (AC-01)', () => {
  test('AC-01 customer quotes MOTOR and sees the premium and the rule version', async ({
    page,
    asRole,
    apiAs,
  }) => {
    await asRole('CUSTOMER');
    await page.goto('/quote');

    await expect(page.getByRole('heading', { name: 'Get a Quote', level: 1 })).toBeVisible();
    await expect(page.getByTestId('quote-empty')).toBeVisible();

    await page.getByLabel('Product', { exact: true }).selectOption('MOTOR');
    await page.getByLabel('Sum insured', { exact: true }).fill('500000.00');
    await page.getByLabel('Owner age', { exact: true }).fill('30');
    await page.getByLabel('Vehicle age (years)', { exact: true }).fill('3');
    await page.getByLabel('Engine cc', { exact: true }).fill('1200');
    await page.getByLabel('Zone', { exact: true }).selectOption('A');
    await page.getByLabel('NCB %', { exact: true }).selectOption('20');

    await page.getByRole('button', { name: 'Get quote' }).click();

    const premium = page.getByTestId('quote-premium');
    await expect(page.getByTestId('quote-result')).toBeVisible();
    await expect(premium).toHaveText(RUPEES);
    await expect(page.getByTestId('quote-rule-version')).toHaveText('Rule version v1');
    await expect(page.getByTestId('quote-apply')).toBeVisible();

    // The same risk through the API: identical premium, identical rule version (AC-01).
    const fromApi = await createQuote(apiAs('CUSTOMER'), MOTOR_AUTO_BIND);
    expect(digitsOf((await premium.textContent()) ?? '')).toBe(fromApi.premium);
    expect(fromApi.rule_version).toBe(1);

    await screenshotScreen(page, 'quote');
  });

  test('AC-01 an out-of-range sum insured is refused by the active rule version', async ({
    page,
    asRole,
  }) => {
    await asRole('CUSTOMER');
    await page.goto('/quote');

    // MOTOR v1 allows 100000.00 – 5000000.00; the server decides, the screen only reports.
    await page.getByLabel('Sum insured', { exact: true }).fill('50.00');
    await page.getByRole('button', { name: 'Get quote' }).click();

    await expect(page.getByTestId('quote-banner')).toContainText('VALIDATION_ERROR');
    await expect(page.getByTestId('field-error-sum_insured')).toContainText('OUT_OF_RANGE');
    await expect(page.getByTestId('quote-result')).toHaveCount(0);
  });
});
