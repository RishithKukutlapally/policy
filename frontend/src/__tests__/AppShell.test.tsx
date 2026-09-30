import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderShell } from './renderShell';
import { ROLE_STORAGE_KEY } from '../app/RoleContext';
import { setViewportMatches } from '../test/setup';

function navLinkNames(): string[] {
  const nav = screen.getByRole('navigation', { name: 'Main navigation' });
  return within(nav)
    .getAllByRole('link')
    .map((link) => link.textContent ?? '');
}

describe('AppShell role-based navigation', () => {
  it('shows the customer navigation by default', () => {
    renderShell();
    expect(navLinkNames()).toEqual(['Get a Quote', 'My Policies']);
  });

  it('switches the visible nav items when the role changes', async () => {
    const user = userEvent.setup();
    renderShell();

    await user.selectOptions(screen.getByTestId('role-switcher'), 'UNDERWRITER');
    expect(navLinkNames()).toEqual(['Workbench']);

    await user.selectOptions(screen.getByTestId('role-switcher'), 'ADMIN');
    // "End of day" joins the admin nav with story E7-S4 (§2.25, ADMIN only).
    expect(navLinkNames()).toEqual([
      'Product Catalog',
      'Underwriting Review',
      'Portfolio',
      'End of day',
    ]);
  });

  it('offers exactly the three demo users', () => {
    renderShell();
    const options = within(screen.getByTestId('role-switcher')).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      'Customer (cust-001)',
      'Underwriter (uw-001)',
      'Admin (admin-001)',
    ]);
  });

  it('persists the selected role and restores it on the next mount', async () => {
    const user = userEvent.setup();
    const first = renderShell();
    await user.selectOptions(screen.getByTestId('role-switcher'), 'ADMIN');
    expect(globalThis.localStorage.getItem(ROLE_STORAGE_KEY)).toBe('ADMIN');

    first.unmount();
    renderShell();
    expect(screen.getByTestId('role-switcher')).toHaveValue('ADMIN');
  });

  it('renders the not-found view for an unknown route', () => {
    renderShell('/no-such-page');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('gives the role switcher and every nav link an accessible name', () => {
    renderShell();
    expect(screen.getByLabelText('Demo user')).toBe(screen.getByTestId('role-switcher'));
    for (const name of navLinkNames()) expect(name.length).toBeGreaterThan(0);
  });
});

describe('AppShell responsive navigation (AC-24)', () => {
  it('shows the nav and no toggle at desktop width', () => {
    setViewportMatches(false);
    renderShell();
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
    expect(screen.queryByTestId('nav-toggle')).toBeNull();
  });

  it('collapses the nav behind an "Open navigation" button below 768 px', async () => {
    setViewportMatches(true);
    const user = userEvent.setup();
    renderShell();

    const toggle = screen.getByRole('button', { name: 'Open navigation' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).toBeNull();

    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();

    await user.click(toggle);
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).toBeNull();
  });

  it('closes the open nav after following a link', async () => {
    setViewportMatches(true);
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByTestId('nav-toggle'));
    await user.click(screen.getByRole('link', { name: 'Get a Quote' }));

    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Get a Quote' })).toBeInTheDocument();
  });
});
