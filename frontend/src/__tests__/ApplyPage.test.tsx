/**
 * Story E4-S5 (AC-03, AC-04, NFR-03) — the customer Apply screen.
 *
 * The application endpoints belong to the backend half of the story, so `src/api/applications` and
 * `src/api/quotes` are mocked and the screen is verified against api-contracts.md §2.10.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { ApplyPage } from '../pages/ApplyPage';
import type { ApplicationResponse } from '../types/applications';
import type { StoredQuote } from '../types/quotes';

vi.mock('../api/applications', () => ({
  createApplication: vi.fn(),
  getApplication: vi.fn(),
}));
vi.mock('../api/quotes', () => ({
  getQuote: vi.fn(),
}));

import { createApplication } from '../api/applications';
import { getQuote } from '../api/quotes';

const QUOTE_ID = '3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04';
const RAW_AADHAAR = '999900000001';
const RAW_PAN = 'AAAAA0001A';

const QUOTE: StoredQuote = {
  quote_id: QUOTE_ID,
  product: 'MOTOR',
  rule_version: 1,
  sum_insured: '500000.00',
  premium: '14322.00',
  currency: 'INR',
  created_at: '2026-10-01T09:30:00Z',
  actor_id: 'cust-001',
  inputs: {
    sum_insured: '500000.00',
    owner_age: 30,
    vehicle_age_years: 12,
    engine_cc: 1200,
    zone: 'A',
    ncb_percent: '20',
  },
};

function application(overrides: Partial<ApplicationResponse> = {}): ApplicationResponse {
  return {
    application_id: '7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21',
    quote_id: QUOTE_ID,
    product: 'MOTOR',
    rule_version: 1,
    status: 'AUTO_BIND',
    decision: 'AUTO_BIND',
    reason_codes: [],
    reasons: [],
    kyc: {
      full_name: 'Test Customer 01',
      date_of_birth: '1996-04-01',
      aadhaar_masked: 'XXXX-XXXX-0001',
      pan_masked: 'XXXXX0001X',
      address: '1 Sample Street, Testville',
    },
    status_history: [{ status: 'SUBMITTED', at: '2026-10-01T09:31:00Z' }],
    created_at: '2026-10-01T09:31:00Z',
    ...overrides,
  };
}

const createApplicationMock = vi.mocked(createApplication);
const getQuoteMock = vi.mocked(getQuote);

function renderApplyPage(): void {
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={[`/apply?quote=${QUOTE_ID}`]}>
        <ApplyPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

async function fillKyc(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByTestId('kyc-full_name'), 'Test Customer 01');
  await user.type(screen.getByTestId('kyc-date_of_birth'), '1996-04-01');
  await user.type(screen.getByTestId('kyc-aadhaar'), RAW_AADHAAR);
  await user.type(screen.getByTestId('kyc-pan'), RAW_PAN);
  await user.type(screen.getByTestId('kyc-address'), '1 Sample Street, Testville');
}

beforeEach(() => {
  createApplicationMock.mockReset();
  getQuoteMock.mockReset();
  getQuoteMock.mockResolvedValue(QUOTE);
});

describe('ApplyPage', () => {
  it('AC-03 shows the quoted premium read-only and the AUTO_BIND decision after submitting', async () => {
    const user = userEvent.setup();
    createApplicationMock.mockResolvedValue(application());
    renderApplyPage();

    expect(await screen.findByTestId('apply-premium')).toHaveTextContent('14,322.00');
    await fillKyc(user);
    await user.click(screen.getByTestId('submit-application'));

    expect(await screen.findByTestId('application-result')).toBeInTheDocument();
    expect(screen.getByTestId('status-badge')).toHaveTextContent('AUTO_BIND');
    expect(screen.getByTestId('issue-policy')).toBeInTheDocument();

    const call = createApplicationMock.mock.calls[0];
    if (call === undefined) throw new Error('createApplication was not called');
    const [, body] = call;
    expect(body.quote_id).toBe(QUOTE_ID);
    expect(body.kyc.pan).toBe(RAW_PAN);
  });

  it('AC-04 lists each reason code with its description and the rule version', async () => {
    const user = userEvent.setup();
    createApplicationMock.mockResolvedValue(
      application({
        status: 'MANUAL_REVIEW',
        decision: 'MANUAL_REVIEW',
        reason_codes: ['MO-UW-002'],
        reasons: [{ code: 'MO-UW-002', description: 'Vehicle older than 10 years' }],
      }),
    );
    renderApplyPage();
    await fillKyc(user);
    await user.click(screen.getByTestId('submit-application'));

    const reasons = await screen.findByTestId('reason-codes');
    expect(reasons).toHaveTextContent('MO-UW-002');
    expect(reasons).toHaveTextContent('Vehicle older than 10 years');
    expect(screen.getByTestId('application-result')).toHaveTextContent('Rule version v1');
    expect(screen.queryByTestId('issue-policy')).not.toBeInTheDocument();
  });

  it('AC-03 renders a 422 field error inline for kyc.pan and no decision', async () => {
    const user = userEvent.setup();
    createApplicationMock.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Body validation failed',
        details: [{ field: 'kyc.pan', code: 'INVALID_FORMAT' }],
        status: 422,
      }),
    );
    renderApplyPage();
    await fillKyc(user);
    await user.click(screen.getByTestId('submit-application'));

    const error = await screen.findByTestId('field-error-kyc.pan');
    expect(error).toHaveTextContent('INVALID_FORMAT');
    expect(screen.queryByTestId('application-result')).not.toBeInTheDocument();
  });

  it('NFR-03 never renders the raw Aadhaar or PAN, only the masked forms', async () => {
    const user = userEvent.setup();
    createApplicationMock.mockResolvedValue(application());
    renderApplyPage();
    await fillKyc(user);
    await user.click(screen.getByTestId('submit-application'));
    await screen.findByTestId('application-result');

    const text = document.body.textContent ?? '';
    expect(text).not.toContain(RAW_AADHAAR);
    expect(text).not.toContain(RAW_PAN);
    expect(screen.getByTestId('aadhaar-masked')).toHaveTextContent('XXXX-XXXX-0001');
    expect(screen.getByTestId('pan-masked')).toHaveTextContent('XXXXX0001X');
    // The inputs themselves hold no raw value once focus has left them.
    expect(screen.getByTestId('kyc-aadhaar')).toHaveValue('');
    expect(screen.getByTestId('kyc-pan')).toHaveValue('');
  });

  it('shows a QUOTE_STALE banner when the quote is no longer on the active version', async () => {
    const user = userEvent.setup();
    createApplicationMock.mockRejectedValue(
      new ApiError({
        code: 'QUOTE_STALE',
        message: 'MOTOR has a newer active rule version than this quote.',
        details: null,
        status: 409,
      }),
    );
    renderApplyPage();
    await fillKyc(user);
    await user.click(screen.getByTestId('submit-application'));

    const banner = await screen.findByTestId('apply-banner');
    expect(banner).toHaveTextContent('QUOTE_STALE');
    await waitFor(() => expect(screen.queryByTestId('application-result')).not.toBeInTheDocument());
  });
});
