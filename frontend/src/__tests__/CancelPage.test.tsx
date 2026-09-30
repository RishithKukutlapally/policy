/**
 * Story E8-S3 (AC-08, AC-19, AC-10, AC-24) — the Cancel screen with its refund preview.
 *
 * `src/api/cancellations` is mocked and the screen is verified against api-contracts.md §2.23–2.24.
 * Both refund sentences asserted here are assembled purely from server-sent decimal strings: the gross
 * pro-rata figure, the admin fee and the net amount all arrive in the breakdown (NFR-01).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { CancelPage } from '../pages/CancelPage';
import type { CancelResult, RefundBreakdown } from '../types/cancellation';
import type { ActorRole } from '../types/roles';
import { TERM_LIFE_DETAIL } from './fixtures';

vi.mock('../api/policies', () => ({
  getPolicy: vi.fn(),
  policyPath: (n: string) => `/api/policies/${n}`,
}));
vi.mock('../api/cancellations', () => ({
  getCancellationPreview: vi.fn(),
  cancelPolicy: vi.fn(),
}));

import { cancelPolicy, getCancellationPreview } from '../api/cancellations';
import { getPolicy } from '../api/policies';

/** §2.23 AC-19: 2026-01-10 is inside the 15-day free look — full refund, no admin fee. */
const FREE_LOOK: RefundBreakdown = {
  policy_number: 'TL-2026-000001',
  cancellation_date: '2026-01-10',
  refund_type: 'FREE_LOOK',
  premium_paid: '12000.00',
  term_days: 365,
  days_elapsed: 9,
  unused_days: 356,
  admin_fee: '0.00',
  amount: '12000.00',
  rule_version: 1,
};

/** §2.24 AC-08: 2026-04-01 → 9041.10 gross − 250.00 fee = 8791.10 net over 275 unused days. */
const PRO_RATA: RefundBreakdown = {
  policy_number: 'TL-2026-000001',
  cancellation_date: '2026-04-01',
  refund_type: 'PRO_RATA',
  premium_paid: '12000.00',
  term_days: 365,
  days_elapsed: 90,
  unused_days: 275,
  admin_fee: '250.00',
  amount: '8791.10',
  pro_rata_amount: '9041.10',
  rule_version: 1,
};

const CANCELLED: CancelResult = {
  policy_number: 'TL-2026-000001',
  status: 'CANCELLED',
  refund: {
    refund_id: 9,
    policy_number: 'TL-2026-000001',
    cancellation_date: '2026-04-01',
    refund_type: 'PRO_RATA',
    premium_paid: '12000.00',
    term_days: 365,
    days_elapsed: 90,
    unused_days: 275,
    admin_fee: '250.00',
    amount: '8791.10',
    rule_version: 1,
    reason: 'Vehicle sold',
    actor_id: 'cust-001',
    created_at: '2026-04-01T10:00:00Z',
  },
};

function renderCancel(role: ActorRole = 'CUSTOMER'): void {
  globalThis.localStorage.setItem('policyforge.demoRole', role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/policies/TL-2026-000001/cancel']}>
        <Routes>
          <Route path="/policies/:policyNumber/cancel" element={<CancelPage />} />
        </Routes>
      </MemoryRouter>
    </RoleProvider>,
  );
}

async function setDate(value: string): Promise<HTMLElement> {
  const input = await screen.findByTestId('cancellation-date');
  fireEvent.change(input, { target: { value } });
  return input;
}

beforeEach(() => {
  vi.mocked(getPolicy).mockReset().mockResolvedValue(TERM_LIFE_DETAIL);
  vi.mocked(getCancellationPreview).mockReset();
  vi.mocked(cancelPolicy).mockReset();
});

describe('Cancel — refund preview (AC-19)', () => {
  it('shows the free-look breakdown for a date inside the free-look window', async () => {
    vi.mocked(getCancellationPreview).mockResolvedValue(FREE_LOOK);
    renderCancel();

    const input = await setDate('2026-01-10');
    expect(input).toHaveAccessibleName(/cancellation date/i);

    const preview = await screen.findByTestId('refund-preview');
    expect(within(preview).getByTestId('refund-sentence')).toHaveTextContent(
      'Full refund ₹12,000.00 (free-look)',
    );
    expect(preview).toHaveTextContent('FREE_LOOK');
    expect(preview).toHaveTextContent('₹0.00');
    expect(getCancellationPreview).toHaveBeenCalledWith(
      expect.anything(),
      'TL-2026-000001',
      '2026-01-10',
    );
    // A preview persists nothing (§2.23).
    expect(cancelPolicy).not.toHaveBeenCalled();
  });

  it('shows the pro-rata breakdown — gross, unused days, admin fee and net', async () => {
    vi.mocked(getCancellationPreview).mockResolvedValue(PRO_RATA);
    renderCancel();
    await setDate('2026-04-01');

    const sentence = await screen.findByTestId('refund-sentence');
    expect(sentence).toHaveTextContent(
      'Refund ₹8,791.10 = ₹9,041.10 pro-rata for 275 unused days − ₹250.00 admin fee',
    );
    const preview = screen.getByTestId('refund-preview');
    expect(preview).toHaveTextContent('PRO_RATA');
    expect(preview).toHaveTextContent('₹12,000.00');
  });

  it('refetches and re-renders when the date changes', async () => {
    vi.mocked(getCancellationPreview)
      .mockResolvedValueOnce(FREE_LOOK)
      .mockResolvedValueOnce(PRO_RATA);
    renderCancel();

    await setDate('2026-01-10');
    expect(await screen.findByTestId('refund-sentence')).toHaveTextContent('₹12,000.00');

    await setDate('2026-04-01');
    await waitFor(() => {
      expect(screen.getByTestId('refund-sentence')).toHaveTextContent('₹8,791.10');
    });
    expect(getCancellationPreview).toHaveBeenCalledTimes(2);
  });

  it('renders a 422 OUTSIDE_TERM inline on the date field (AC-10)', async () => {
    vi.mocked(getCancellationPreview).mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: [{ field: 'date', code: 'OUTSIDE_TERM' }],
        status: 422,
      }),
    );
    renderCancel();
    const input = await setDate('2027-01-01');

    const error = await screen.findByTestId('field-error-cancellation_date');
    expect(error).toHaveTextContent('OUTSIDE_TERM');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByTestId('refund-sentence')).not.toBeInTheDocument();
  });

  it('shows an INVALID_POLICY_STATE banner for an already-cancelled policy (409, AC-10)', async () => {
    vi.mocked(getCancellationPreview).mockRejectedValue(
      new ApiError({
        code: 'INVALID_POLICY_STATE',
        message: 'Policy is already CANCELLED',
        details: { current: 'CANCELLED', target: 'CANCELLED' },
        status: 409,
      }),
    );
    renderCancel();
    await setDate('2026-04-01');

    expect(await screen.findByTestId('cancel-error')).toHaveTextContent('INVALID_POLICY_STATE');
  });
});

describe('Cancel — confirmation (AC-08, AC-24)', () => {
  it('requires an explicit dialog, then shows CANCELLED with the refund row', async () => {
    vi.mocked(getCancellationPreview).mockResolvedValue(PRO_RATA);
    vi.mocked(cancelPolicy).mockResolvedValue(CANCELLED);
    renderCancel();

    await setDate('2026-04-01');
    await screen.findByTestId('refund-sentence');
    await userEvent.type(screen.getByTestId('cancellation-reason'), 'Vehicle sold');
    await userEvent.click(screen.getByTestId('confirm-cancellation'));

    // The dialog gates the request: nothing was sent yet (AC-19).
    const dialog = await screen.findByTestId('confirm-dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveTextContent('₹8,791.10');
    expect(cancelPolicy).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByTestId('dialog-confirm'));

    await waitFor(() => {
      expect(cancelPolicy).toHaveBeenCalledWith(expect.anything(), 'TL-2026-000001', {
        cancellation_date: '2026-04-01',
        reason: 'Vehicle sold',
      });
    });
    expect(await screen.findByTestId('cancel-confirmation')).toHaveTextContent('₹8,791.10');
    expect(screen.getByTestId('status-badge')).toHaveTextContent('CANCELLED');
    const refunds = screen.getByTestId('refunds');
    expect(within(refunds).getByTestId('refund-amount')).toHaveTextContent('₹8,791.10');
    expect(refunds).toHaveTextContent('PRO_RATA');
    expect(refunds).toHaveTextContent('₹250.00');
  });

  it('keeping the policy in the dialog sends nothing', async () => {
    vi.mocked(getCancellationPreview).mockResolvedValue(PRO_RATA);
    renderCancel();

    await setDate('2026-04-01');
    await screen.findByTestId('refund-sentence');
    await userEvent.click(screen.getByTestId('confirm-cancellation'));
    await userEvent.click(within(await screen.findByTestId('confirm-dialog')).getByTestId('dialog-keep'));

    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
    expect(cancelPolicy).not.toHaveBeenCalled();
  });

  it('shows "Not authorised" to an UNDERWRITER', async () => {
    renderCancel('UNDERWRITER');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(screen.queryByTestId('cancellation-date')).not.toBeInTheDocument();
  });
});
