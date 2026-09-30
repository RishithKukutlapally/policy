/**
 * Story E5-S3 (AC-05, AC-15, AC-24) — My Policies and Policy Detail.
 *
 * The policy endpoints belong to the backend half of the story, so `src/api/policies` is mocked and
 * the screens are verified against api-contracts.md §2.16–2.18. Fixtures carry masked KYC only; the
 * raw values below exist purely so a test can assert they never reach the DOM (NFR-03).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { PoliciesPage } from '../pages/PoliciesPage';
import { PolicyDetailPage } from '../pages/PolicyDetailPage';
import { setViewportMatches } from '../test/setup';
import type { PolicyDetail, PolicySummary } from '../types/policies';

vi.mock('../api/policies', () => ({
  listPolicies: vi.fn(),
  getPolicy: vi.fn(),
  issuePolicy: vi.fn(),
}));

import { getPolicy, issuePolicy, listPolicies } from '../api/policies';

/** Synthetic values that must never be rendered — only their masks may appear. */
const RAW_AADHAAR = '999900000001';
const RAW_PAN = 'AAAAA0001A';

const MOTOR: PolicySummary = {
  policy_number: 'MO-2026-000001',
  product: 'MOTOR',
  status: 'ACTIVE',
  rule_version: 1,
  sum_insured: '500000.00',
  premium: '15500.00',
  currency: 'INR',
  effective_date: '2026-03-01',
  expiry_date: '2027-02-28',
  premium_due_date: '2026-03-01',
  next_premium_due_date: '2027-03-01',
  previous_policy_number: null,
};

const HOUSEHOLD: PolicySummary = {
  ...MOTOR,
  policy_number: 'HH-2026-000001',
  product: 'HOUSEHOLD',
  status: 'CANCELLED',
  sum_insured: '3000000.00',
  premium: '2700.00',
  effective_date: '2026-01-21',
  expiry_date: '2027-01-20',
  premium_due_date: '2026-01-21',
  next_premium_due_date: null,
};

const MOTOR_DETAIL: PolicyDetail = {
  ...MOTOR,
  status: 'ENDORSED',
  successor_policy_number: null,
  application_id: '7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21',
  insured: {
    full_name: 'Test Customer 01',
    address: '2 Sample Road, Testville',
    aadhaar_masked: 'XXXX-XXXX-0001',
    pan_masked: 'XXXXX0001X',
    nominees: [{ nominee_name: 'Test Nominee 01', relationship: 'SPOUSE', share_percent: '100.00' }],
  },
  transitions: [
    {
      from_status: null,
      to_status: 'ACTIVE',
      reason: 'ISSUED',
      actor_id: 'cust-001',
      occurred_at: '2026-03-01T10:05:00Z',
    },
    {
      from_status: 'ACTIVE',
      to_status: 'ENDORSED',
      reason: 'ENDORSEMENT:CHANGE_ADDRESS',
      actor_id: 'cust-001',
      occurred_at: '2026-06-10T09:30:00Z',
    },
  ],
  endorsements: [
    {
      endorsement_id: 17,
      type: 'CHANGE_ADDRESS',
      before: { address: '1 Sample Street, Testville' },
      after: { address: '2 Sample Road, Testville' },
      premium_delta: '0.00',
      rule_version: 1,
      endorsement_date: '2026-06-10',
      actor_id: 'cust-001',
      created_at: '2026-06-10T09:30:00Z',
    },
    {
      endorsement_id: 18,
      type: 'CHANGE_SUM_INSURED',
      before: { sum_insured: '400000.00' },
      after: { sum_insured: '500000.00' },
      premium_delta: '1200.00',
      rule_version: 1,
      endorsement_date: '2026-07-02',
      actor_id: 'cust-001',
      created_at: '2026-07-02T16:45:00Z',
    },
  ],
  payments: [
    {
      payment_id: 1,
      due_date: '2026-03-01',
      amount: '15500.00',
      rule_version: 1,
      actor_id: 'cust-001',
      paid_at: '2026-03-01T10:05:00Z',
    },
  ],
  refunds: [],
};

const CANCELLED_DETAIL: PolicyDetail = {
  ...MOTOR_DETAIL,
  ...HOUSEHOLD,
  endorsements: [],
  transitions: [
    {
      from_status: 'ACTIVE',
      to_status: 'CANCELLED',
      reason: 'CUSTOMER_REQUEST',
      actor_id: 'cust-001',
      occurred_at: '2026-07-21T14:30:00Z',
    },
  ],
  refunds: [
    {
      refund_id: 9,
      policy_number: 'HH-2026-000001',
      cancellation_date: '2026-07-21',
      refund_type: 'PRO_RATA',
      premium_paid: '2700.00',
      term_days: 365,
      days_elapsed: 181,
      unused_days: 184,
      admin_fee: '250.00',
      amount: '1111.10',
      rule_version: 1,
      reason: 'Vehicle sold',
      actor_id: 'cust-001',
      created_at: '2026-07-21T14:30:00Z',
    },
  ],
};

function notFound(): ApiError {
  return new ApiError({
    code: 'NOT_FOUND',
    message: 'Policy not found',
    details: null,
    status: 404,
  });
}

function renderList(route = '/policies'): void {
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={[route]}>
        <PoliciesPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

function renderDetail(policyNumber: string): void {
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={[`/policies/${policyNumber}`]}>
        <PolicyDetailPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(listPolicies).mockReset();
  vi.mocked(getPolicy).mockReset();
  vi.mocked(issuePolicy).mockReset();
});

describe('My Policies (AC-15)', () => {
  it('lists each policy with its number, money, dates and a text status badge', async () => {
    vi.mocked(listPolicies).mockResolvedValue([MOTOR, HOUSEHOLD]);
    renderList();

    const list = await screen.findByTestId('policy-list');
    const motorRow = within(list).getByTestId('policy-row-MO-2026-000001');
    expect(motorRow).toHaveTextContent('MO-2026-000001');
    expect(motorRow).toHaveTextContent('Motor');
    expect(motorRow).toHaveTextContent('₹15,500.00');
    expect(motorRow).toHaveTextContent('₹5,00,000.00');
    expect(motorRow).toHaveTextContent('2026-03-01');
    expect(motorRow).toHaveTextContent('2027-02-28');
    expect(motorRow).toHaveTextContent('2027-03-01');
    expect(within(motorRow).getByTestId('status-badge')).toHaveTextContent('ACTIVE');
    expect(
      within(within(list).getByTestId('policy-row-HH-2026-000001')).getByTestId('status-badge'),
    ).toHaveTextContent('CANCELLED');
  });

  it('shows an empty state when the customer has no policies', async () => {
    vi.mocked(listPolicies).mockResolvedValue([]);
    renderList();

    expect(await screen.findByTestId('policies-empty')).toHaveTextContent(/no policies yet/i);
    expect(screen.queryByTestId('policy-list')).not.toBeInTheDocument();
  });

  it('renders stacked cards instead of a table at a narrow width (AC-24)', async () => {
    setViewportMatches(true);
    vi.mocked(listPolicies).mockResolvedValue([MOTOR]);
    renderList();

    const list = await screen.findByTestId('policy-list');
    expect(list.tagName).toBe('UL');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(within(list).getByTestId('policy-card-MO-2026-000001')).toHaveTextContent('₹15,500.00');
  });

  it('shows a retry banner when the list fails with 500', async () => {
    vi.mocked(listPolicies)
      .mockRejectedValueOnce(
        new ApiError({ code: 'INTERNAL_ERROR', message: 'boom', details: null, status: 500 }),
      )
      .mockResolvedValueOnce([MOTOR]);
    renderList();

    const banner = await screen.findByTestId('policies-error');
    expect(banner).toHaveTextContent('INTERNAL_ERROR');
    await userEvent.click(within(banner).getByRole('button', { name: /retry/i }));
    expect(await screen.findByTestId('policy-list')).toBeInTheDocument();
  });

  it('issues a policy for an AUTO_BIND application reached with ?application=', async () => {
    vi.mocked(listPolicies).mockResolvedValue([]);
    vi.mocked(issuePolicy).mockResolvedValue(MOTOR);
    renderList(`/policies?application=${MOTOR_DETAIL.application_id}`);

    await userEvent.click(await screen.findByTestId('issue-policy'));
    await waitFor(() => {
      expect(issuePolicy).toHaveBeenCalledWith(expect.anything(), MOTOR_DETAIL.application_id);
    });
  });

  it('shows a banner when issuing an application that is not AUTO_BIND (409)', async () => {
    vi.mocked(listPolicies).mockResolvedValue([]);
    vi.mocked(issuePolicy).mockRejectedValue(
      new ApiError({
        code: 'INVALID_APPLICATION_STATE',
        message: 'Application is not AUTO_BIND',
        details: null,
        status: 409,
      }),
    );
    renderList(`/policies?application=${MOTOR_DETAIL.application_id}`);

    await userEvent.click(await screen.findByTestId('issue-policy'));
    expect(await screen.findByTestId('issue-error')).toHaveTextContent('INVALID_APPLICATION_STATE');
  });
});

describe('Policy Detail (AC-15, AC-05)', () => {
  it('opening a policy from the list shows its detail with history and lifecycle', async () => {
    vi.mocked(listPolicies).mockResolvedValue([MOTOR]);
    renderList();
    const open = await screen.findByTestId('policy-open');
    expect(open).toHaveAccessibleName(/MO-2026-000001/);
    expect(open).toHaveAttribute('href', '/policies/MO-2026-000001');

    vi.mocked(getPolicy).mockResolvedValue(MOTOR_DETAIL);
    renderDetail('MO-2026-000001');

    const detail = await screen.findByTestId('policy-detail');
    expect(within(detail).getByRole('heading', { level: 1 })).toHaveTextContent('MO-2026-000001');
    expect(within(detail).getByTestId('detail-status')).toHaveTextContent('ENDORSED');

    const history = within(detail).getByTestId('endorsement-history');
    expect(history).toHaveTextContent('CHANGE_ADDRESS');
    expect(history).toHaveTextContent('2026-06-10');
    expect(history).toHaveTextContent('+₹1,200.00');

    const lifecycle = within(detail).getByTestId('lifecycle');
    expect(within(lifecycle).getAllByRole('listitem')).toHaveLength(2);
    expect(lifecycle).toHaveTextContent('ACTIVE');
    expect(lifecycle).toHaveTextContent('ENDORSED');
    expect(lifecycle).toHaveTextContent('2026-06-10');

    expect(within(detail).getByTestId('payments')).toHaveTextContent('₹15,500.00');
  });

  it('never paints a raw Aadhaar or PAN (NFR-03)', async () => {
    vi.mocked(getPolicy).mockResolvedValue(MOTOR_DETAIL);
    renderDetail('MO-2026-000001');

    await screen.findByTestId('policy-detail');
    expect(document.body.textContent).toContain('XXXX-XXXX-0001');
    expect(document.body.textContent).toContain('XXXXX0001X');
    expect(document.body.textContent).not.toContain(RAW_AADHAAR);
    expect(document.body.textContent).not.toContain(RAW_PAN);
  });

  it('renders "Policy not found" for a 404 and reveals nothing else', async () => {
    vi.mocked(getPolicy).mockRejectedValue(notFound());
    renderDetail('MO-2026-999999');

    expect(await screen.findByTestId('policy-not-found')).toHaveTextContent('Policy not found');
    expect(screen.queryByTestId('policy-detail')).not.toBeInTheDocument();
  });

  it('disables the lifecycle actions for a CANCELLED policy (AC-10) and lists its refund', async () => {
    vi.mocked(getPolicy).mockResolvedValue(CANCELLED_DETAIL);
    renderDetail('HH-2026-000001');

    await screen.findByTestId('policy-detail');
    for (const testId of ['action-endorse', 'action-renew', 'action-cancel']) {
      expect(screen.getByTestId(testId)).toHaveAttribute('aria-disabled', 'true');
    }
    expect(screen.getByTestId('refunds')).toHaveTextContent('₹1,111.10');
    expect(screen.getByTestId('refunds')).toHaveTextContent('PRO_RATA');
    expect(screen.getByTestId('endorsements-empty')).toBeInTheDocument();
  });
});
