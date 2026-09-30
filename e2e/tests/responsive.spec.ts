/**
 * Responsive layout — AC-24 (story E1-S5 / E9-S4).
 *
 * The same tests run in both projects and branch on the project's viewport, because the point of AC-24 is
 * that one layout serves both: at 1280 px the side navigation is part of the page, at 390 px it collapses
 * behind the "Open navigation" button and every table re-renders as stacked cards with no horizontal
 * overflow. The ARIA snapshot pins the navigation's accessible structure (roles and names), which is what
 * a screen-reader user actually navigates — something a screenshot cannot prove.
 */
import { test, expect } from '../fixtures/app';

/** The stylesheet's breakpoint (`useIsNarrow`: collapse below 768 px). */
const NARROW_BREAKPOINT = 768;

test.describe('Responsive layout (AC-24)', () => {
  test('AC-24 the side navigation matches the viewport and nothing overflows horizontally', async ({
    page,
    asRole,
  }, testInfo) => {
    const width = page.viewportSize()?.width ?? 0;
    const narrow = width < NARROW_BREAKPOINT;
    expect([390, 1280]).toContain(width);

    await asRole('CUSTOMER');
    await page.goto('/');

    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    const toggle = page.getByRole('button', { name: 'Open navigation' });

    if (narrow) {
      // Mobile: the nav is behind a labelled menu button and opens on click.
      await expect(toggle).toBeVisible();
      await expect(nav).toBeHidden();
      await toggle.click();
      await expect(nav).toBeVisible();
      await expect(nav.getByRole('link', { name: 'Get a Quote' })).toBeVisible();
      await expect(toggle).toHaveAttribute('aria-expanded', 'true');
      await page.keyboard.press('Escape');
      await expect(nav).toBeHidden();
    } else {
      // Desktop: the nav is always on the page and there is no menu button.
      await expect(toggle).toHaveCount(0);
      await expect(nav).toBeVisible();
      await expect(nav.getByRole('link', { name: 'My Policies' })).toBeVisible();
    }

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `${testInfo.project.name} must not scroll horizontally`).toBeLessThanOrEqual(0);
  });

  test('AC-24 the customer navigation keeps its accessible structure at both viewports', async ({
    page,
    asRole,
  }) => {
    await asRole('CUSTOMER');
    await page.goto('/');
    if ((page.viewportSize()?.width ?? 0) < NARROW_BREAKPOINT) {
      await page.getByRole('button', { name: 'Open navigation' }).click();
    }
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toMatchAriaSnapshot({
      name: 'customer-nav.aria.yml',
    });
  });

  test('AC-24 AC-15 the policy table renders as stacked cards at 390 px and as a table at 1280 px', async ({
    page,
    asRole,
  }) => {
    await asRole('CUSTOMER');
    await page.goto('/policies');

    const list = page.getByTestId('policy-list');
    await expect(list).toBeVisible();
    const narrow = (page.viewportSize()?.width ?? 0) < NARROW_BREAKPOINT;

    // Same test id, two shapes: `<ul class="policy-cards">` on mobile, `<table>` on the desktop (AC-24).
    await expect(list).toHaveJSProperty('tagName', narrow ? 'UL' : 'TABLE');
    if (narrow) {
      await expect(page.locator('.policy-card').first()).toBeVisible();
      const overflow = await list.evaluate((node) => node.scrollWidth - node.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    } else {
      await expect(list.getByRole('columnheader', { name: 'Policy number' })).toBeVisible();
    }
  });

  test('AC-24 AC-20 the portfolio dashboard stacks its tables at 390 px', async ({ page, asRole }) => {
    await asRole('ADMIN');
    await page.goto('/admin/portfolio');

    await expect(page.getByTestId('portfolio-cards')).toBeVisible();
    const narrow = (page.viewportSize()?.width ?? 0) < NARROW_BREAKPOINT;
    const pipeline = page.getByTestId('renewal-pipeline');
    // This spec runs after the end-of-day sweep, so the pipeline may legitimately be empty by now —
    // either shape is asserted, never skipped.
    if ((await pipeline.count()) > 0) {
      await expect(pipeline).toHaveJSProperty('tagName', narrow ? 'UL' : 'TABLE');
    } else {
      await expect(page.getByTestId('pipeline-empty')).toBeVisible();
    }

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
