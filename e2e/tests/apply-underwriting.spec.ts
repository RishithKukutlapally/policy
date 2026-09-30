/**
 * Apply and underwriting — AC-03, AC-04, AC-14, AC-09 (stories E4-S2…E4-S5 / E9-S4).
 *
 * The three journeys are the customer applying with synthetic KYC, the underwriter deciding a
 * MANUAL_REVIEW case from the Workbench, and the admin overriding a DECLINE from Underwriting Review.
 * Aadhaar and PAN only ever appear masked (NFR-03) and every privileged action leaves an audit row
 * carrying the actor id (NFR-04).
 */
import { test, expect, screenshotScreen, statusBadge, ACTOR_IDS } from '../fixtures/app';
import {
  MASKED_AADHAAR,
  MASKED_PAN,
  MOTOR_AUTO_BIND,
  MOTOR_MANUAL_REVIEW,
  arrangeApplication,
  createQuote,
  kycFor,
} from '../fixtures/data';

interface AuditRow {
  readonly action: string;
  readonly actor_id: string;
}

test.describe('Apply and underwriting (AC-03, AC-04, AC-09, AC-14)', () => {
  test('AC-03 AC-04 customer applies with synthetic KYC and is auto-bound', async ({
    page,
    asRole,
    apiAs,
  }) => {
    await asRole('CUSTOMER');
    const quote = await createQuote(apiAs('CUSTOMER'), MOTOR_AUTO_BIND);
    const kyc = kycFor(31);

    await page.goto(`/apply?quote=${quote.quote_id}`);
    await expect(page.getByRole('heading', { name: 'Apply', level: 1 })).toBeVisible();
    // The quoted premium is read-only on this screen and must match the quote (NFR-01).
    await expect(page.getByTestId('apply-premium')).toHaveText(/^₹/);
    await expect(page.getByTestId('apply-decision-empty')).toBeVisible();

    await page.getByLabel('Full name', { exact: true }).fill(kyc.full_name);
    await page.getByLabel('Date of birth', { exact: true }).fill(kyc.date_of_birth);
    await page.getByLabel('Aadhaar', { exact: true }).fill(kyc.aadhaar);
    await page.getByLabel('PAN', { exact: true }).fill(kyc.pan);
    await page.getByLabel('Address', { exact: true }).fill(kyc.address);

    await screenshotScreen(page, 'apply');

    await page.getByRole('button', { name: 'Submit application' }).click();

    await expect(page.getByTestId('application-result')).toBeVisible();
    await expect(statusBadge(page)).toHaveText('AUTO_BIND');
    await expect(page.getByTestId('aadhaar-masked')).toHaveText(MASKED_AADHAAR);
    await expect(page.getByTestId('pan-masked')).toHaveText(MASKED_PAN);
    await expect(page.getByTestId('issue-policy')).toBeVisible();
  });

  test('AC-14 underwriter approves a MANUAL_REVIEW case with a reason code', async ({
    page,
    asRole,
    apiAs,
  }) => {
    const { application } = await arrangeApplication(apiAs('CUSTOMER'), MOTOR_MANUAL_REVIEW, 32);
    expect(application.decision).toBe('MANUAL_REVIEW');

    await asRole('UNDERWRITER');
    await page.goto('/underwriter/queue');
    await expect(page.getByRole('heading', { name: 'Workbench', level: 1 })).toBeVisible();

    const openCase = page.locator(
      `[data-testid="case-open"][data-case-id="${application.application_id}"]`,
    );
    await expect(openCase).toBeVisible();
    await openCase.click();

    await expect(page.getByTestId('case-detail')).toBeVisible();
    await expect(page.getByTestId('case-aadhaar')).toHaveText(MASKED_AADHAAR);
    // The automatic decision is already audited with `decided_by SYSTEM`.
    await expect(page.getByTestId('audit-trail')).toContainText('SYSTEM');

    await screenshotScreen(page, 'workbench');

    await page.getByTestId('reason-MO-UW-900').check();
    await page.getByLabel('Comment', { exact: true }).fill('Inspection report reviewed, risk acceptable.');
    await page.getByRole('button', { name: 'Approve' }).click();

    await expect(page.getByTestId('case-closed')).toBeVisible();
    await expect(page.getByTestId('audit-trail')).toContainText(ACTOR_IDS.UNDERWRITER);
    await expect(page.getByTestId('audit-trail')).toContainText('UW_APPROVE');
    // An approved case leaves the manual review queue.
    await expect(openCase).toHaveCount(0);

    const detail = (await apiAs('UNDERWRITER').get(
      `/api/applications/${application.application_id}`,
    )) as { status: string };
    expect(detail.status).toBe('AUTO_BIND');
  });

  test('AC-09 admin overrides a DECLINE and the audit trail lists both actor ids', async ({
    page,
    asRole,
    apiAs,
  }) => {
    const { application } = await arrangeApplication(apiAs('CUSTOMER'), MOTOR_MANUAL_REVIEW, 33);
    // The underwriter declines first, so the admin has a DECLINED case to override (§2.14).
    await apiAs('UNDERWRITER').post(
      `/api/underwriting/applications/${application.application_id}/decision`,
      { decision: 'DECLINE', reason_codes: ['MO-UW-902'], comment: 'Vehicle age outside appetite.' },
    );

    await asRole('ADMIN');
    await page.goto('/admin/underwriting');
    await expect(page.getByRole('heading', { name: 'Underwriting Review', level: 1 })).toBeVisible();

    const override = page.locator(
      `[data-testid="case-override"][data-case-id="${application.application_id}"]`,
    );
    await expect(override).toBeVisible();
    await override.click();

    const dialog = page.getByRole('dialog', { name: 'Override DECLINE' });
    await expect(dialog).toBeVisible();
    await page.getByTestId('override-reason').selectOption('MO-UW-901');
    await page.getByTestId('override-comment').fill('Risk accepted after portfolio review.');
    await page.getByTestId('override-submit').click();

    await expect(page.getByTestId('override-notice')).toContainText(ACTOR_IDS.ADMIN);
    await expect(override).toHaveCount(0);

    const audit = (await apiAs('ADMIN').get(
      `/api/underwriting/applications/${application.application_id}/audit`,
    )) as { audit_records: readonly AuditRow[] };
    const actions = audit.audit_records.map((row) => `${row.action}:${row.actor_id}`);
    expect(actions).toContain(`UW_DECLINE:${ACTOR_IDS.UNDERWRITER}`);
    expect(actions).toContain(`UW_OVERRIDE_DECLINE:${ACTOR_IDS.ADMIN}`);

    const detail = (await apiAs('ADMIN').get(
      `/api/applications/${application.application_id}`,
    )) as { status: string };
    expect(detail.status).toBe('AUTO_BIND');
  });
});
