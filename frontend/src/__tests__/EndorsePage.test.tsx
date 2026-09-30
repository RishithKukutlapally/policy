/**
 * Story E6-S3 (AC-06, AC-16, AC-10, AC-24) — the Endorse screen.
 *
 * The endorsement endpoint belongs to the backend half of the story, so `src/api/endorsements`,
 * `src/api/policies` and `src/api/catalog` are mocked and the screen is verified against
 * api-contracts.md §2.19. Every money figure asserted here is a string the server sent: the test would
 * fail if the UI ever did the subtraction itself (NFR-01).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { EndorsePage } from '../pages/EndorsePage';
import type { ActorRole } from '../types/roles';
import type { EndorsementPreview, EndorsementResult } from '../types/endorsements';
import {
  MOTOR_DETAIL,
  MOTOR_DETAIL_ENDORSED,
  MOTOR_SUMMARY,
  MOTOR_VERSION_V1,
  MOTOR_VERSION_V2,
} from './fixtures';

vi.mock('../api/policies', () => ({
  getPolicy: vi.fn(),
  policyPath: (n: string) => `/api/policies/${n}`,
}));
vi.mock('../api/catalog', () => ({ listVersions: vi.fn() }));
vi.mock('../api/endorsements', () => ({
  previewEndorsement: vi.fn(),
  createEndorsement: vi.fn(),
}));

import { listVersions } from '../api/catalog';
import { createEndorsement, previewEndorsement } from '../api/endorsements';
import { getPolicy } from '../api/policies';

/** §2.19 `?preview=true` for 600000.00: (18600.00 − 15500.00) × 181 / 365 = 1537.26. */
const PREVIEW: EndorsementPreview = {
  policy_number: 'MO-2026-000001',
  type: 'CHANGE_SUM_INSURED',
  preview: true,
  before: { sum_insured: '500000.00', premium: '15500.00' },
  after: { sum_insured: '600000.00', premium: '18600.00' },
  new_premium: '18600.00',
  premium_delta: '1537.26',
  rule_version: 1,
  endorsement_date: '2026-09-01',
  unused_days: 181,
  term_days: 365,
};

const CREATED: EndorsementResult = {
  endorsement_id: 18,
  policy_number: 'MO-2026-000001',
  type: 'CHANGE_SUM_INSURED',
  before: { sum_insured: '500000.00', premium: '15500.00' },
  after: { sum_insured: '600000.00', premium: '18600.00' },
  new_premium: '18600.00',
  premium_delta: '1537.26',
  rule_version: 1,
  endorsement_date: '2026-09-01',
  created_at: '2026-09-01T11:20:00Z',
  policy: { ...MOTOR_SUMMARY, status: 'ENDORSED', sum_insured: '600000.00' },
};

function renderEndorse(role: ActorRole = 'CUSTOMER', policyNumber = 'MO-2026-000001'): void {
  globalThis.localStorage.setItem('policyforge.demoRole', role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={[`/policies/${policyNumber}/endorse`]}>
        <Routes>
          <Route path="/policies/:policyNumber/endorse" element={<EndorsePage />} />
        </Routes>
      </MemoryRouter>
    </RoleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getPolicy).mockReset().mockResolvedValue(MOTOR_DETAIL);
  vi.mocked(listVersions).mockReset().mockResolvedValue([MOTOR_VERSION_V1]);
  vi.mocked(previewEndorsement).mockReset();
  vi.mocked(createEndorsement).mockReset();
});

describe('Endorse — type selector (AC-16)', () => {
  it('offers only the rule version’s allowed_types', async () => {
    renderEndorse();

    const select = await screen.findByTestId('endorsement-type');
    expect(select).toHaveAccessibleName(/endorsement type/i);
    const values = within(select)
      .getAllByRole('option')
      .map((option) => (option as HTMLOptionElement).value);
    expect(values).toEqual(['CHANGE_ADDRESS', 'ADD_NOMINEE', 'CHANGE_SUM_INSURED']);
  });

  it('hides a type the policy’s own rule version does not allow', async () => {
    vi.mocked(getPolicy).mockResolvedValue({ ...MOTOR_DETAIL, rule_version: 2 });
    vi.mocked(listVersions).mockResolvedValue([MOTOR_VERSION_V1, MOTOR_VERSION_V2]);
    renderEndorse();

    const select = await screen.findByTestId('endorsement-type');
    const values = within(select)
      .getAllByRole('option')
      .map((option) => (option as HTMLOptionElement).value);
    expect(values).toEqual(['CHANGE_ADDRESS']);
  });

  it('swaps the fields when the type changes', async () => {
    renderEndorse();
    const select = await screen.findByTestId('endorsement-type');

    expect(screen.getByTestId('input-address')).toBeInTheDocument();
    expect(screen.queryByTestId('input-new_sum_insured')).not.toBeInTheDocument();

    await userEvent.selectOptions(select, 'ADD_NOMINEE');
    expect(screen.getByTestId('input-nominee_name')).toHaveAccessibleName(/nominee name/i);
    expect(screen.getByTestId('input-relationship')).toBeInTheDocument();
    expect(screen.getByTestId('input-share_percent')).toBeInTheDocument();

    await userEvent.selectOptions(select, 'CHANGE_SUM_INSURED');
    expect(screen.getByTestId('input-new_sum_insured')).toHaveAccessibleName(/sum insured/i);
    expect(screen.queryByTestId('input-address')).not.toBeInTheDocument();
  });
});

describe('Endorse — preview (AC-16)', () => {
  it('shows the signed pro-rated delta and persists nothing', async () => {
    vi.mocked(previewEndorsement).mockResolvedValue(PREVIEW);
    renderEndorse();

    await userEvent.selectOptions(await screen.findByTestId('endorsement-type'), 'CHANGE_SUM_INSURED');
    await userEvent.type(screen.getByTestId('input-new_sum_insured'), '600000.00');
    await userEvent.click(screen.getByTestId('preview'));

    expect(await screen.findByTestId('preview-delta')).toHaveTextContent('+₹1,537.26');
    const result = screen.getByTestId('preview-result');
    expect(result).toHaveTextContent('₹18,600.00');
    expect(result).toHaveTextContent('181');
    expect(result).toHaveTextContent(/nothing has been saved/i);

    expect(previewEndorsement).toHaveBeenCalledWith(expect.anything(), 'MO-2026-000001', {
      type: 'CHANGE_SUM_INSURED',
      new_sum_insured: '600000.00',
    });
    // Preview must not persist: the create endpoint was never called (AC-16).
    expect(createEndorsement).not.toHaveBeenCalled();
    expect(screen.queryByTestId('endorsement-confirmation')).not.toBeInTheDocument();
  });

  it('renders a negative delta with a minus sign', async () => {
    vi.mocked(previewEndorsement).mockResolvedValue({
      ...PREVIEW,
      after: { sum_insured: '400000.00', premium: '12400.00' },
      new_premium: '12400.00',
      premium_delta: '-1537.26',
    });
    renderEndorse();

    await userEvent.selectOptions(await screen.findByTestId('endorsement-type'), 'CHANGE_SUM_INSURED');
    await userEvent.type(screen.getByTestId('input-new_sum_insured'), '400000.00');
    await userEvent.click(screen.getByTestId('preview'));

    expect(await screen.findByTestId('preview-delta')).toHaveTextContent('−₹1,537.26');
  });

  it('attaches a 422 OUT_OF_RANGE to the sum insured field and shows no preview', async () => {
    vi.mocked(previewEndorsement).mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: [{ field: 'new_sum_insured', code: 'OUT_OF_RANGE' }],
        status: 422,
      }),
    );
    renderEndorse();

    await userEvent.selectOptions(await screen.findByTestId('endorsement-type'), 'CHANGE_SUM_INSURED');
    await userEvent.type(screen.getByTestId('input-new_sum_insured'), '99999');
    await userEvent.click(screen.getByTestId('preview'));

    const error = await screen.findByTestId('field-error-new_sum_insured');
    expect(error).toHaveTextContent('OUT_OF_RANGE');
    expect(screen.getByTestId('input-new_sum_insured')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByTestId('preview-result')).not.toBeInTheDocument();
  });
});

describe('Endorse — submission (AC-06, AC-16, AC-10, AC-24)', () => {
  it('submitting moves the policy to ENDORSED and shows the new history row', async () => {
    vi.mocked(createEndorsement).mockResolvedValue(CREATED);
    vi.mocked(getPolicy)
      .mockResolvedValueOnce(MOTOR_DETAIL)
      .mockResolvedValueOnce(MOTOR_DETAIL_ENDORSED);
    renderEndorse();

    await userEvent.selectOptions(await screen.findByTestId('endorsement-type'), 'CHANGE_SUM_INSURED');
    await userEvent.type(screen.getByTestId('input-new_sum_insured'), '600000.00');
    await userEvent.click(screen.getByTestId('submit-endorsement'));

    const confirmation = await screen.findByTestId('endorsement-confirmation');
    expect(confirmation).toHaveTextContent('CHANGE_SUM_INSURED');
    expect(confirmation).toHaveTextContent('+₹1,537.26');
    expect(screen.getByTestId('status-badge')).toHaveTextContent('ENDORSED');

    const history = screen.getByTestId('endorsement-history');
    expect(history).toHaveTextContent('2026-09-01');
    expect(history).toHaveTextContent('+₹1,537.26');
    expect(screen.getByRole('link', { name: /policy detail/i })).toHaveAttribute(
      'href',
      '/policies/MO-2026-000001',
    );
  });

  it('sends an ADD_NOMINEE body with the relationship and share', async () => {
    vi.mocked(createEndorsement).mockResolvedValue({
      ...CREATED,
      type: 'ADD_NOMINEE',
      premium_delta: '0.00',
    });
    renderEndorse();

    await userEvent.selectOptions(await screen.findByTestId('endorsement-type'), 'ADD_NOMINEE');
    await userEvent.type(screen.getByTestId('input-nominee_name'), 'Test Nominee 01');
    await userEvent.selectOptions(screen.getByTestId('input-relationship'), 'SPOUSE');
    await userEvent.clear(screen.getByTestId('input-share_percent'));
    await userEvent.type(screen.getByTestId('input-share_percent'), '100');
    await userEvent.click(screen.getByTestId('submit-endorsement'));

    await waitFor(() => {
      expect(createEndorsement).toHaveBeenCalledWith(expect.anything(), 'MO-2026-000001', {
        type: 'ADD_NOMINEE',
        nominee_name: 'Test Nominee 01',
        relationship: 'SPOUSE',
        share_percent: '100',
      });
    });
  });

  it('shows an INVALID_POLICY_STATE banner on 409 (AC-10)', async () => {
    vi.mocked(createEndorsement).mockRejectedValue(
      new ApiError({
        code: 'INVALID_POLICY_STATE',
        message: 'Policy is CANCELLED',
        details: { current: 'CANCELLED', target: 'ENDORSED' },
        status: 409,
      }),
    );
    renderEndorse();

    await screen.findByTestId('endorsement-type');
    await userEvent.click(screen.getByTestId('submit-endorsement'));

    const banner = await screen.findByTestId('endorse-error');
    expect(banner).toHaveTextContent('INVALID_POLICY_STATE');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(screen.queryByTestId('endorsement-confirmation')).not.toBeInTheDocument();
  });
});

describe('Endorse — access', () => {
  it('shows "Not authorised" to an UNDERWRITER', async () => {
    renderEndorse('UNDERWRITER');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(screen.queryByTestId('endorsement-type')).not.toBeInTheDocument();
    expect(getPolicy).not.toHaveBeenCalled();
  });

  it('renders the shared not-found panel for a 404', async () => {
    vi.mocked(getPolicy).mockRejectedValue(
      new ApiError({ code: 'NOT_FOUND', message: 'not found', details: null, status: 404 }),
    );
    renderEndorse();

    expect(await screen.findByTestId('policy-not-found')).toBeInTheDocument();
    expect(screen.queryByTestId('endorsement-type')).not.toBeInTheDocument();
  });
});
