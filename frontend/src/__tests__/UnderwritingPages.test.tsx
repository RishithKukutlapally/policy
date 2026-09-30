/**
 * Story E4-S5 (AC-09, AC-14, AC-24) — Underwriter Workbench and Admin Underwriting Review.
 *
 * The underwriting endpoints belong to the backend half of the story, so `src/api/underwriting` and
 * `src/api/applications` are mocked and the screens are verified against api-contracts.md §2.11–2.15.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { ROLE_STORAGE_KEY, RoleProvider } from '../app/RoleContext';
import { UnderwritingReviewPage } from '../pages/UnderwritingReviewPage';
import { WorkbenchPage } from '../pages/WorkbenchPage';
import { setViewportMatches } from '../test/setup';
import type {
  ApplicationDetail,
  AuditResponse,
  QueueItem,
} from '../types/applications';
import type { ActorRole } from '../types/roles';

vi.mock('../api/underwriting', () => ({
  getQueue: vi.fn(),
  submitDecision: vi.fn(),
  submitOverride: vi.fn(),
  getAudit: vi.fn(),
  fetchReasonCodes: vi.fn(),
}));
vi.mock('../api/applications', () => ({
  createApplication: vi.fn(),
  getApplication: vi.fn(),
}));

import { getApplication } from '../api/applications';
import { fetchReasonCodes, getAudit, getQueue, submitDecision, submitOverride } from '../api/underwriting';

const MANUAL_ID = 'a52d6c1e-3b7f-4e2a-9c58-1f0e7d4b2a63';
const DECLINED_ID = 'd45e0b8c-7a13-4f2d-a9e6-3c8b1d0f5e74';

const REASONS: Readonly<Record<string, string>> = {
  'MO-UW-001': 'Vehicle older than 15 years',
  'MO-UW-002': 'Vehicle older than 10 years',
  'MO-UW-900': 'Underwriter approved',
  'MO-UW-901': 'Admin override: risk accepted',
  'MO-UW-902': 'Underwriter declined',
};

const MANUAL_CASE: QueueItem = {
  application_id: MANUAL_ID,
  product: 'MOTOR',
  status: 'MANUAL_REVIEW',
  rule_version: 1,
  reason_codes: ['MO-UW-002'],
  sum_insured: '500000.00',
  premium: '19334.70',
  submitted_at: '2026-09-21T10:42:00Z',
  decisions: [],
};

const DECLINED_CASE: QueueItem = {
  ...MANUAL_CASE,
  application_id: DECLINED_ID,
  status: 'DECLINED',
  reason_codes: ['MO-UW-001', 'MO-UW-002'],
  submitted_at: '2026-09-18T11:30:00Z',
};

const DETAIL: ApplicationDetail = {
  application_id: MANUAL_ID,
  quote_id: '3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04',
  product: 'MOTOR',
  rule_version: 1,
  status: 'MANUAL_REVIEW',
  decision: 'MANUAL_REVIEW',
  reason_codes: ['MO-UW-002'],
  reasons: [{ code: 'MO-UW-002', description: 'Vehicle older than 10 years' }],
  kyc: {
    full_name: 'Test Customer 01',
    date_of_birth: '1996-04-01',
    aadhaar_masked: 'XXXX-XXXX-0001',
    pan_masked: 'XXXXX0001X',
    address: '1 Sample Street, Testville',
  },
  status_history: [{ status: 'MANUAL_REVIEW', at: '2026-09-21T10:42:00Z' }],
  created_at: '2026-09-21T10:42:00Z',
  decisions: [],
  overrides: [],
  policy_number: null,
};

const AUDIT: AuditResponse = {
  application_id: MANUAL_ID,
  decisions: [],
  overrides: [],
  audit_records: [
    {
      action: 'UW_APPROVE',
      actor_id: 'uw-001',
      actor_role: 'UNDERWRITER',
      entity_type: 'APPLICATION',
      entity_id: MANUAL_ID,
      detail: null,
      correlation_id: 'corr-0001',
      created_at: '2026-09-29T11:05:00Z',
    },
  ],
};

/** Narrows the first element / first call away from `undefined` (noUncheckedIndexedAccess). */
function first<T>(items: readonly T[]): T {
  const item = items[0];
  if (item === undefined) throw new Error('expected at least one item');
  return item;
}

const getQueueMock = vi.mocked(getQueue);
const submitDecisionMock = vi.mocked(submitDecision);
const submitOverrideMock = vi.mocked(submitOverride);
const getAuditMock = vi.mocked(getAudit);
const fetchReasonCodesMock = vi.mocked(fetchReasonCodes);
const getApplicationMock = vi.mocked(getApplication);

function renderAs(role: ActorRole, element: JSX.Element): void {
  globalThis.localStorage.setItem(ROLE_STORAGE_KEY, role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/underwriter/queue']}>{element}</MemoryRouter>
    </RoleProvider>,
  );
}

beforeEach(() => {
  for (const mock of [
    getQueueMock,
    submitDecisionMock,
    submitOverrideMock,
    getAuditMock,
    fetchReasonCodesMock,
    getApplicationMock,
  ]) {
    mock.mockReset();
  }
  getQueueMock.mockResolvedValue([MANUAL_CASE]);
  getApplicationMock.mockResolvedValue(DETAIL);
  getAuditMock.mockResolvedValue(AUDIT);
  fetchReasonCodesMock.mockResolvedValue(REASONS);
});

describe('WorkbenchPage', () => {
  it('AC-14 renders the manual review queue and opens a case detail', async () => {
    const user = userEvent.setup();
    renderAs('UNDERWRITER', <WorkbenchPage />);

    const table = await screen.findByTestId('queue-table');
    expect(within(table).getByText('MOTOR')).toBeInTheDocument();
    expect(within(table).getByText(/MO-UW-002/)).toBeInTheDocument();

    await user.click(first(within(table).getAllByTestId('case-open')));

    const detail = await screen.findByTestId('case-detail');
    expect(within(detail).getByTestId('case-aadhaar')).toHaveTextContent('XXXX-XXXX-0001');
    expect(await screen.findByTestId('audit-trail')).toHaveTextContent('UW_APPROVE');
    expect(screen.getByTestId('audit-trail')).toHaveTextContent('uw-001');
  });

  it('AC-14 approves a case with the chosen reason codes and a comment', async () => {
    const user = userEvent.setup();
    submitDecisionMock.mockResolvedValue({
      application_id: MANUAL_ID,
      status: 'AUTO_BIND',
      decision: {
        decision_id: 52,
        decision: 'AUTO_BIND',
        reason_codes: ['MO-UW-900'],
        reasons: [{ code: 'MO-UW-900', description: 'Underwriter approved' }],
        rule_version: 1,
        decided_by: 'uw-001',
        comment: 'Vehicle inspected',
        created_at: '2026-09-29T11:05:00Z',
      },
    });
    renderAs('UNDERWRITER', <WorkbenchPage />);
    await user.click(first(await screen.findAllByTestId('case-open')));
    await screen.findByTestId('case-detail');

    await user.click(await screen.findByTestId('reason-MO-UW-900'));
    await user.type(screen.getByTestId('decision-comment'), 'Vehicle inspected');
    await user.click(screen.getByTestId('decision-approve'));

    await waitFor(() => expect(submitDecisionMock).toHaveBeenCalledTimes(1));
    const [, applicationId, body] = first(submitDecisionMock.mock.calls);
    expect(applicationId).toBe(MANUAL_ID);
    expect(body).toMatchObject({
      decision: 'APPROVE',
      reason_codes: ['MO-UW-900'],
      comment: 'Vehicle inspected',
    });
  });

  it('surfaces the 422 when no reason code is chosen', async () => {
    const user = userEvent.setup();
    submitDecisionMock.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Body validation failed',
        details: [{ field: 'reason_codes', code: 'REQUIRED' }],
        status: 422,
      }),
    );
    renderAs('UNDERWRITER', <WorkbenchPage />);
    await user.click(first(await screen.findAllByTestId('case-open')));
    await screen.findByTestId('case-detail');
    await user.click(screen.getByTestId('decision-decline'));

    const alert = await screen.findByTestId('decision-error');
    expect(alert).toHaveTextContent('VALIDATION_ERROR');
    expect(alert).toHaveTextContent('reason_codes');
  });

  it('AC-24 renders the queue as cards on a narrow viewport', async () => {
    setViewportMatches(true);
    renderAs('UNDERWRITER', <WorkbenchPage />);

    expect(await screen.findByTestId('queue-cards')).toBeInTheDocument();
    expect(screen.queryByTestId('queue-table')).not.toBeInTheDocument();
  });
});

describe('UnderwritingReviewPage', () => {
  it('refuses a non-admin role', async () => {
    renderAs('UNDERWRITER', <UnderwritingReviewPage />);
    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
  });

  it('AC-09 keeps override submit disabled until a reason and a 10-character comment are given', async () => {
    const user = userEvent.setup();
    getQueueMock.mockResolvedValue([DECLINED_CASE]);
    renderAs('ADMIN', <UnderwritingReviewPage />);

    await user.click(first(await screen.findAllByTestId('case-override')));
    const dialog = await screen.findByTestId('override-dialog');
    expect(dialog).toHaveAttribute('role', 'dialog');

    const submit = screen.getByTestId('override-submit');
    expect(submit).toBeDisabled();

    await user.selectOptions(screen.getByTestId('override-reason'), 'MO-UW-901');
    await user.type(screen.getByTestId('override-comment'), 'ok');
    expect(submit).toBeDisabled();

    await user.type(screen.getByTestId('override-comment'), ' condition verified');
    expect(submit).toBeEnabled();
  });

  it('AC-09 submits the override and renders a 422 UNKNOWN_REASON_CODE', async () => {
    const user = userEvent.setup();
    getQueueMock.mockResolvedValue([DECLINED_CASE]);
    submitOverrideMock.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Body validation failed',
        details: [{ field: 'reason_code', code: 'UNKNOWN_REASON_CODE' }],
        status: 422,
      }),
    );
    renderAs('ADMIN', <UnderwritingReviewPage />);

    await user.click(first(await screen.findAllByTestId('case-override')));
    await user.selectOptions(await screen.findByTestId('override-reason'), 'MO-UW-901');
    await user.type(screen.getByTestId('override-comment'), 'Vehicle restored, fitness seen');
    await user.click(screen.getByTestId('override-submit'));

    await waitFor(() => expect(submitOverrideMock).toHaveBeenCalledTimes(1));
    const [, applicationId, body] = first(submitOverrideMock.mock.calls);
    expect(applicationId).toBe(DECLINED_ID);
    expect(body).toEqual({
      reason_code: 'MO-UW-901',
      comment: 'Vehicle restored, fitness seen',
    });
    expect(await screen.findByTestId('override-error')).toHaveTextContent('UNKNOWN_REASON_CODE');
  });

  it('AC-09 closes the override dialog on Escape', async () => {
    const user = userEvent.setup();
    getQueueMock.mockResolvedValue([DECLINED_CASE]);
    renderAs('ADMIN', <UnderwritingReviewPage />);

    await user.click(first(await screen.findAllByTestId('case-override')));
    expect(await screen.findByTestId('override-dialog')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByTestId('override-dialog')).not.toBeInTheDocument());
  });
});
