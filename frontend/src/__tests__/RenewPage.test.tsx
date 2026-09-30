/**
 * Story E7-S4 (AC-07, AC-17, AC-18, NFR-04) — the Renew screen and the admin end-of-day control.
 *
 * `src/api/renewal` and `src/api/policies` are mocked: the screens are verified against
 * api-contracts.md §2.20–2.22 and §2.25. The premium the "Pay premium" button sends must be the exact
 * decimal string from the quote — never a number the UI rounded (NFR-01, AC-17).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { EndOfDayPage } from '../pages/EndOfDayPage';
import { RenewPage } from '../pages/RenewPage';
import type { ActorRole } from '../types/roles';
import type { EndOfDayResult, PaymentReceipt, RenewalQuote } from '../types/renewal';
import { MOTOR_DETAIL, MOTOR_SUMMARY } from './fixtures';

vi.mock('../api/policies', () => ({
  getPolicy: vi.fn(),
  policyPath: (n: string) => `/api/policies/${n}`,
}));
vi.mock('../api/renewal', () => ({
  getRenewalQuote: vi.fn(),
  payPremium: vi.fn(),
  renewPolicy: vi.fn(),
  runEndOfDay: vi.fn(),
}));

import { getPolicy } from '../api/policies';
import { getRenewalQuote, payPremium, renewPolicy, runEndOfDay } from '../api/renewal';

/** §2.20 for MO-2026-000001 on business date 2027-02-15 (window opened 2027-01-29). */
const QUOTE: RenewalQuote = {
  policy_number: 'MO-2026-000001',
  renewable: true,
  renewal_premium: '15500.00',
  rule_version: 1,
  currency: 'INR',
  due_date: '2027-03-01',
  grace_end_date: '2027-03-31',
  renewal_window_opens: '2027-01-29',
  paid: false,
};

const RECEIPT: PaymentReceipt = {
  payment_id: 311,
  policy_number: 'MO-2026-000001',
  amount: '15500.00',
  due_date: '2027-03-01',
  rule_version: 1,
  actor_id: 'cust-001',
  paid_at: '2027-02-15T08:15:00Z',
};

const SUCCESSOR = {
  ...MOTOR_SUMMARY,
  policy_number: 'MO-2027-000001',
  effective_date: '2027-03-01',
  expiry_date: '2028-02-29',
  premium_due_date: '2027-03-01',
  next_premium_due_date: '2028-03-01',
  previous_policy_number: 'MO-2026-000001',
};

const EOD_RUN: EndOfDayResult = {
  as_of: '2027-01-15',
  renewed: 1,
  lapsed: 1,
  in_grace: 1,
  not_renewable: 0,
  failed: 0,
  renewed_policies: [{ from: 'TL-2026-000001', to: 'TL-2027-000001' }],
  lapsed_policies: ['MO-2026-000007'],
  failed_policies: [],
};

const EOD_ZERO: EndOfDayResult = {
  as_of: '2027-01-15',
  renewed: 0,
  lapsed: 0,
  in_grace: 0,
  not_renewable: 0,
  failed: 0,
  renewed_policies: [],
  lapsed_policies: [],
  failed_policies: [],
};

function conflict(code: 'INVALID_POLICY_STATE' | 'OUTSIDE_RENEWAL_WINDOW' | 'PREMIUM_ALREADY_PAID'): ApiError {
  return new ApiError({ code, message: `Rejected: ${code}`, details: null, status: 409 });
}

function renderRenew(role: ActorRole = 'CUSTOMER'): void {
  globalThis.localStorage.setItem('policyforge.demoRole', role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/policies/MO-2026-000001/renew']}>
        <Routes>
          <Route path="/policies/:policyNumber/renew" element={<RenewPage />} />
        </Routes>
      </MemoryRouter>
    </RoleProvider>,
  );
}

function renderEod(role: ActorRole = 'ADMIN'): void {
  globalThis.localStorage.setItem('policyforge.demoRole', role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/admin/end-of-day']}>
        <EndOfDayPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getPolicy).mockReset().mockResolvedValue(MOTOR_DETAIL);
  vi.mocked(getRenewalQuote).mockReset().mockResolvedValue(QUOTE);
  vi.mocked(payPremium).mockReset();
  vi.mocked(renewPolicy).mockReset();
  vi.mocked(runEndOfDay).mockReset();
});

describe('Renew — quote (AC-07)', () => {
  it('shows the refreshed premium, the new term dates and the grace end', async () => {
    renderRenew();

    expect(await screen.findByTestId('renewal-premium')).toHaveTextContent('₹15,500.00');
    expect(screen.getByTestId('due-date')).toHaveTextContent('2027-03-01');
    expect(screen.getByTestId('grace-end-date')).toHaveTextContent('2027-03-31');
    expect(screen.getByTestId('payment-status')).toHaveTextContent('UNPAID');
  });
});

describe('Renew — pay then renew (AC-17, AC-07)', () => {
  it('pays the quoted premium, shows PAID, then reveals the successor and a link to it', async () => {
    vi.mocked(payPremium).mockResolvedValue(RECEIPT);
    vi.mocked(renewPolicy).mockResolvedValue(SUCCESSOR);
    renderRenew();

    await userEvent.click(await screen.findByTestId('pay-premium'));

    // The exact decimal string from the quote, not a re-formatted number (NFR-01).
    await waitFor(() => {
      expect(payPremium).toHaveBeenCalledWith(expect.anything(), 'MO-2026-000001', '15500.00');
    });
    expect(await screen.findByTestId('payment-status')).toHaveTextContent('PAID');

    await userEvent.click(screen.getByTestId('renew-now'));

    const link = await screen.findByTestId('successor-link');
    expect(link).toHaveTextContent('MO-2027-000001');
    expect(link).toHaveAttribute('href', '/policies/MO-2027-000001');
    expect(screen.getByTestId('status-badge')).toHaveTextContent('RENEWED');
  });

  it('shows RENEWAL_PREMIUM_UNPAID inline when renewing before paying (422)', async () => {
    vi.mocked(renewPolicy).mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: [{ field: 'payment', code: 'RENEWAL_PREMIUM_UNPAID' }],
        status: 422,
      }),
    );
    renderRenew();

    await userEvent.click(await screen.findByTestId('renew-now'));

    const banner = await screen.findByTestId('renewal-error');
    expect(banner).toHaveTextContent('RENEWAL_PREMIUM_UNPAID');
    expect(screen.queryByTestId('successor-link')).not.toBeInTheDocument();
  });

  it('shows an OUTSIDE_RENEWAL_WINDOW banner on 409', async () => {
    vi.mocked(renewPolicy).mockRejectedValue(conflict('OUTSIDE_RENEWAL_WINDOW'));
    renderRenew();

    await userEvent.click(await screen.findByTestId('renew-now'));

    expect(await screen.findByTestId('renewal-error')).toHaveTextContent('OUTSIDE_RENEWAL_WINDOW');
  });

  it('shows a PREMIUM_ALREADY_PAID banner on 409 from the payment', async () => {
    vi.mocked(payPremium).mockRejectedValue(conflict('PREMIUM_ALREADY_PAID'));
    renderRenew();

    await userEvent.click(await screen.findByTestId('pay-premium'));

    expect(await screen.findByTestId('renewal-error')).toHaveTextContent('PREMIUM_ALREADY_PAID');
  });

  it('replaces the quote with an INVALID_POLICY_STATE banner when the policy is terminal (409)', async () => {
    vi.mocked(getRenewalQuote).mockRejectedValue(conflict('INVALID_POLICY_STATE'));
    renderRenew();

    expect(await screen.findByTestId('renewal-error')).toHaveTextContent('INVALID_POLICY_STATE');
    expect(screen.queryByTestId('pay-premium')).not.toBeInTheDocument();
  });

  it('shows "Not authorised" to an ADMIN (renew is owner-only, §2.21)', async () => {
    renderRenew('ADMIN');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(getRenewalQuote).not.toHaveBeenCalled();
  });
});

describe('Admin end-of-day (AC-18, NFR-04)', () => {
  it('runs the job and shows the counts and the renewed policies', async () => {
    vi.mocked(runEndOfDay).mockResolvedValue(EOD_RUN);
    renderEod();

    const asOf = screen.getByTestId('eod-as-of');
    expect(asOf).toHaveAccessibleName(/as of/i);
    await userEvent.clear(asOf);
    await userEvent.type(asOf, '2027-01-15');
    await userEvent.click(screen.getByTestId('run-eod'));

    const result = await screen.findByTestId('eod-result');
    expect(within(result).getByTestId('count-renewed')).toHaveTextContent('Renewed: 1');
    expect(within(result).getByTestId('count-lapsed')).toHaveTextContent('Lapsed: 1');
    expect(within(result).getByTestId('count-in-grace')).toHaveTextContent('In grace: 1');
    expect(within(result).getByTestId('count-failed')).toHaveTextContent('Failed: 0');
    expect(result).toHaveTextContent('TL-2026-000001');
    expect(result).toHaveTextContent('TL-2027-000001');
    expect(runEndOfDay).toHaveBeenCalledWith(expect.anything(), '2027-01-15');
  });

  it('a second run of the same date shows zeros (idempotent)', async () => {
    vi.mocked(runEndOfDay).mockResolvedValueOnce(EOD_RUN).mockResolvedValueOnce(EOD_ZERO);
    renderEod();

    const asOf = screen.getByTestId('eod-as-of');
    await userEvent.clear(asOf);
    await userEvent.type(asOf, '2027-01-15');

    await userEvent.click(screen.getByTestId('run-eod'));
    expect(await screen.findByTestId('count-renewed')).toHaveTextContent('Renewed: 1');

    await userEvent.click(screen.getByTestId('run-eod'));
    await waitFor(() => {
      expect(screen.getByTestId('count-renewed')).toHaveTextContent('Renewed: 0');
    });
    expect(screen.getByTestId('count-lapsed')).toHaveTextContent('Lapsed: 0');
    expect(screen.getByTestId('eod-result')).toHaveTextContent(/already processed/i);
  });

  it('lists each per-policy failure', async () => {
    vi.mocked(runEndOfDay).mockResolvedValue({
      ...EOD_ZERO,
      failed: 1,
      failed_policies: [
        { policy_number: 'HH-2026-000004', error: 'Rule version could not be loaded' },
      ],
    });
    renderEod();

    const asOf = screen.getByTestId('eod-as-of');
    await userEvent.clear(asOf);
    await userEvent.type(asOf, '2027-02-01');
    await userEvent.click(screen.getByTestId('run-eod'));

    const failures = await screen.findByTestId('eod-failures');
    expect(failures).toHaveTextContent('HH-2026-000004');
    expect(failures).toHaveTextContent('Rule version could not be loaded');
  });

  it('shows "Not authorised" to a CUSTOMER', async () => {
    renderEod('CUSTOMER');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(screen.queryByTestId('run-eod')).not.toBeInTheDocument();
  });
});
