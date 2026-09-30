/**
 * Story E9-S2 (AC-20, AC-24) — the admin Portfolio Dashboard.
 *
 * `src/api/portfolio` is mocked and the screen is verified against api-contracts.md §2.26. Every money
 * figure is the server's decimal string formatted `en-IN`; the dashboard aggregates nothing (NFR-01).
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { PortfolioPage } from '../pages/PortfolioPage';
import { setViewportMatches } from '../test/setup';
import type { PortfolioSnapshot } from '../types/portfolio';
import type { ActorRole } from '../types/roles';

vi.mock('../api/portfolio', () => ({ getPortfolio: vi.fn() }));

import { getPortfolio } from '../api/portfolio';

const SNAPSHOT: PortfolioSnapshot = {
  as_of: '2027-01-01',
  active_by_product: { TERM_LIFE: 0, MOTOR: 3, HOUSEHOLD: 2 },
  premium_collected: '43000.00',
  refunds_paid: '8791.10',
  renewal_pipeline: [
    {
      policy_number: 'MO-2026-000005',
      product: 'MOTOR',
      due_date: '2027-01-15',
      renewal_premium: '14322.00',
      paid: true,
    },
    {
      policy_number: 'HH-2026-000003',
      product: 'HOUSEHOLD',
      due_date: '2027-01-20',
      renewal_premium: '2700.00',
      paid: false,
    },
  ],
  lapse_forecast: {
    count: 1,
    premium_at_risk: '3100.00',
    policies: [
      {
        policy_number: 'MO-2025-000009',
        product: 'MOTOR',
        due_date: '2026-12-20',
        grace_end_date: '2027-01-19',
        premium: '3100.00',
      },
    ],
  },
};

const EMPTY_FORECAST: PortfolioSnapshot = {
  ...SNAPSHOT,
  as_of: '2026-10-15',
  renewal_pipeline: [],
  lapse_forecast: { count: 0, premium_at_risk: '0.00', policies: [] },
};

function renderPortfolio(role: ActorRole = 'ADMIN'): void {
  globalThis.localStorage.setItem('policyforge.demoRole', role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/admin/portfolio']}>
        <PortfolioPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getPortfolio).mockReset().mockResolvedValue(SNAPSHOT);
});

describe('Portfolio — figures (AC-20)', () => {
  it('renders active policies by product, premium collected, the pipeline and the lapse forecast', async () => {
    renderPortfolio();

    const byProduct = await screen.findByTestId('portfolio-by-product');
    expect(within(byProduct).getByTestId('card-TERM_LIFE')).toHaveTextContent('Term Life');
    expect(within(byProduct).getByTestId('card-TERM_LIFE')).toHaveTextContent('0');
    expect(within(byProduct).getByTestId('card-MOTOR')).toHaveTextContent('3');
    expect(within(byProduct).getByTestId('card-HOUSEHOLD')).toHaveTextContent('2');

    const cards = screen.getByTestId('portfolio-cards');
    expect(within(cards).getByTestId('card-premium-collected')).toHaveTextContent('₹43,000.00');
    expect(within(cards).getByTestId('card-refunds-paid')).toHaveTextContent('₹8,791.10');

    const pipeline = screen.getByTestId('renewal-pipeline');
    expect(pipeline).toHaveTextContent('MO-2026-000005');
    expect(pipeline).toHaveTextContent('2027-01-15');
    expect(pipeline).toHaveTextContent('₹14,322.00');
    expect(pipeline).toHaveTextContent('PAID');
    expect(pipeline).toHaveTextContent('UNPAID');

    const forecast = screen.getByTestId('lapse-forecast');
    expect(forecast).toHaveTextContent('MO-2025-000009');
    expect(forecast).toHaveTextContent('2027-01-19');
    expect(forecast).toHaveTextContent('₹3,100.00');
  });

  it('shows "No policies at risk" when the forecast is empty', async () => {
    vi.mocked(getPortfolio).mockResolvedValue(EMPTY_FORECAST);
    renderPortfolio();

    expect(await screen.findByTestId('lapse-empty')).toHaveTextContent('No policies at risk');
    expect(screen.queryByTestId('lapse-forecast')).not.toBeInTheDocument();
  });
});

describe('Portfolio — as_of, loading and errors (AC-20)', () => {
  it('shows a loading indicator until the snapshot arrives', async () => {
    let release: (value: PortfolioSnapshot) => void = () => undefined;
    vi.mocked(getPortfolio).mockReturnValue(
      new Promise<PortfolioSnapshot>((resolve) => {
        release = resolve;
      }),
    );
    renderPortfolio();

    expect(screen.getByTestId('loading')).toBeInTheDocument();
    release(SNAPSHOT);
    expect(await screen.findByTestId('portfolio-cards')).toBeInTheDocument();
    expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
  });

  it('refetches with the chosen as_of date', async () => {
    renderPortfolio();
    await screen.findByTestId('portfolio-cards');

    const asOf = screen.getByTestId('as-of');
    expect(asOf).toHaveAccessibleName(/as of/i);
    await userEvent.clear(asOf);
    await userEvent.type(asOf, '2027-01-01');

    await waitFor(() => {
      expect(getPortfolio).toHaveBeenLastCalledWith(expect.anything(), '2027-01-01');
    });
  });

  it('shows an inline alert with a Retry button on 500 and recovers', async () => {
    vi.mocked(getPortfolio)
      .mockRejectedValueOnce(
        new ApiError({ code: 'INTERNAL_ERROR', message: 'boom', details: null, status: 500 }),
      )
      .mockResolvedValueOnce(SNAPSHOT);
    renderPortfolio();

    const alert = await screen.findByTestId('portfolio-error');
    expect(alert).toHaveTextContent('INTERNAL_ERROR');
    expect(screen.queryByTestId('portfolio-cards')).not.toBeInTheDocument();

    await userEvent.click(within(alert).getByTestId('retry'));
    expect(await screen.findByTestId('portfolio-cards')).toBeInTheDocument();
  });
});

describe('Portfolio — responsive and access (AC-24)', () => {
  it('stacks the tables into cards at 390 px with no table element', async () => {
    setViewportMatches(true);
    renderPortfolio();

    const pipeline = await screen.findByTestId('renewal-pipeline');
    expect(pipeline.tagName).toBe('UL');
    expect(screen.getByTestId('lapse-forecast').tagName).toBe('UL');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    // Status is still text, never colour alone.
    expect(pipeline).toHaveTextContent('PAID');
    expect(screen.getByTestId('portfolio-cards')).toBeInTheDocument();
  });

  it('shows "Not authorised" to a CUSTOMER and never calls the endpoint', async () => {
    renderPortfolio('CUSTOMER');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(screen.queryByTestId('portfolio-cards')).not.toBeInTheDocument();
    expect(getPortfolio).not.toHaveBeenCalled();
  });

  it('shows "Not authorised" to an UNDERWRITER', async () => {
    renderPortfolio('UNDERWRITER');

    expect(await screen.findByTestId('not-authorised')).toBeInTheDocument();
  });
});
