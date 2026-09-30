/**
 * Story E3-S3 (AC-01, AC-12, AC-24) — Get a Quote screen.
 *
 * The quote endpoints are owned by the backend half of the story, so `src/api/quotes` is mocked and
 * the screen is verified purely against specs/design/api-contracts.md §2.7.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { RoleProvider } from '../app/RoleContext';
import { QuotePage } from '../pages/QuotePage';
import { setViewportMatches } from '../test/setup';
import type { QuoteResponse } from '../types/quotes';

vi.mock('../api/quotes', () => ({
  createQuote: vi.fn(),
}));

import { createQuote } from '../api/quotes';

const MOTOR_QUOTE: QuoteResponse = {
  quote_id: '3f1c9a2e-8d4b-4c1e-9a7f-2b6d5e8c1a04',
  product: 'MOTOR',
  rule_version: 1,
  sum_insured: '500000.00',
  premium: '14322.00',
  currency: 'INR',
  created_at: '2026-10-01T09:30:00Z',
};

function renderQuotePage(): void {
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/quote']}>
        <QuotePage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

const createQuoteMock = vi.mocked(createQuote);

beforeEach(() => {
  createQuoteMock.mockReset();
});

describe('QuotePage', () => {
  it('swaps the risk-input field set when the product changes', async () => {
    const user = userEvent.setup();
    renderQuotePage();

    // MOTOR is the default product (mockup E3-S3).
    expect(screen.getByTestId('input-owner_age')).toBeInTheDocument();
    expect(screen.getByTestId('input-zone')).toBeInTheDocument();
    expect(screen.queryByTestId('input-term_years')).not.toBeInTheDocument();

    await user.selectOptions(screen.getByTestId('quote-product'), 'TERM_LIFE');

    expect(screen.getByTestId('input-age')).toBeInTheDocument();
    expect(screen.getByTestId('input-term_years')).toBeInTheDocument();
    expect(screen.getByTestId('input-smoker')).toBeInTheDocument();
    expect(screen.queryByTestId('input-owner_age')).not.toBeInTheDocument();
    expect(screen.queryByTestId('input-ncb_percent')).not.toBeInTheDocument();

    await user.selectOptions(screen.getByTestId('quote-product'), 'HOUSEHOLD');

    expect(screen.getByTestId('input-proposer_age')).toBeInTheDocument();
    expect(screen.getByTestId('input-construction_type')).toBeInTheDocument();
    expect(screen.getByTestId('input-in_flood_zone')).toBeInTheDocument();
    expect(screen.getByTestId('input-has_security_system')).toBeInTheDocument();
    expect(screen.queryByTestId('input-age')).not.toBeInTheDocument();

    // The shared field survives every switch.
    expect(screen.getByTestId('quote-sum-insured')).toBeInTheDocument();
  });

  it('posts the canonical MOTOR inputs and renders the formatted premium with the rule version', async () => {
    const user = userEvent.setup();
    createQuoteMock.mockResolvedValue(MOTOR_QUOTE);
    renderQuotePage();

    await user.click(screen.getByTestId('quote-submit'));

    await waitFor(() => expect(screen.getByTestId('quote-premium')).toBeInTheDocument());
    expect(createQuoteMock).toHaveBeenCalledTimes(1);
    const body = createQuoteMock.mock.calls[0]?.[1];
    expect(body).toEqual({
      product: 'MOTOR',
      inputs: {
        sum_insured: '500000.00',
        owner_age: 30,
        vehicle_age_years: 3,
        engine_cc: 1200,
        zone: 'A',
        ncb_percent: '20',
      },
    });

    // Formatted by Intl.NumberFormat('en-IN') from the decimal string — never computed here.
    expect(screen.getByTestId('quote-premium')).toHaveTextContent('14,322.00');
    expect(screen.getByTestId('quote-rule-version')).toHaveTextContent('Rule version v1');
    expect(screen.getByTestId('quote-result')).toHaveAttribute('role', 'status');
  });

  it('renders a 422 VALIDATION_ERROR inline next to the offending field', async () => {
    const user = userEvent.setup();
    createQuoteMock.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Quote inputs are invalid',
        details: [{ field: 'sum_insured', code: 'OUT_OF_RANGE' }],
        status: 422,
      }),
    );
    renderQuotePage();

    const sumInsured = screen.getByTestId('quote-sum-insured');
    await user.clear(sumInsured);
    await user.type(sumInsured, '50000.00');
    await user.click(screen.getByTestId('quote-submit'));

    const fieldError = await screen.findByTestId('field-error-sum_insured');
    expect(fieldError).toHaveTextContent('OUT_OF_RANGE');
    expect(sumInsured).toHaveAttribute('aria-invalid', 'true');
    expect(sumInsured.getAttribute('aria-describedby')).toContain(fieldError.id);
    expect(screen.queryByTestId('quote-premium')).not.toBeInTheDocument();
  });

  it('renders a banner when the product has no published rule version (409)', async () => {
    const user = userEvent.setup();
    createQuoteMock.mockRejectedValue(
      new ApiError({
        code: 'NO_PUBLISHED_VERSION',
        message: 'Household has no published rule version',
        details: null,
        status: 409,
      }),
    );
    renderQuotePage();

    await user.selectOptions(screen.getByTestId('quote-product'), 'HOUSEHOLD');
    await user.click(screen.getByTestId('quote-submit'));

    const banner = await screen.findByTestId('quote-banner');
    expect(banner).toHaveTextContent('NO_PUBLISHED_VERSION');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(screen.queryByTestId('quote-premium')).not.toBeInTheDocument();
  });

  it('shows a banner when the network is unreachable', async () => {
    const user = userEvent.setup();
    createQuoteMock.mockRejectedValue(
      new ApiError({
        code: 'NETWORK_ERROR',
        message: 'The server could not be reached.',
        details: null,
        status: 0,
      }),
    );
    renderQuotePage();

    await user.click(screen.getByTestId('quote-submit'));

    expect(await screen.findByTestId('quote-banner')).toHaveTextContent('NETWORK_ERROR');
  });

  it('disables the submit button while the request is in flight', async () => {
    const user = userEvent.setup();
    let release: (value: QuoteResponse) => void = () => undefined;
    createQuoteMock.mockImplementation(
      () =>
        new Promise<QuoteResponse>((resolve) => {
          release = resolve;
        }),
    );
    renderQuotePage();

    const submit = screen.getByTestId('quote-submit');
    await user.click(submit);

    expect(submit).toBeDisabled();
    expect(screen.getByTestId('quote-loading')).toBeInTheDocument();

    release(MOTOR_QUOTE);
    await waitFor(() => expect(submit).toBeEnabled());
    expect(screen.queryByTestId('quote-loading')).not.toBeInTheDocument();
    expect(createQuoteMock).toHaveBeenCalledTimes(1);
  });

  it('keeps every labelled input reachable at a narrow viewport', async () => {
    setViewportMatches(true);
    createQuoteMock.mockResolvedValue(MOTOR_QUOTE);
    renderQuotePage();

    expect(screen.getByTestId('quote-page')).toHaveAttribute('data-narrow', 'true');
    expect(screen.getByLabelText('Sum insured')).toBe(screen.getByTestId('quote-sum-insured'));
    expect(screen.getByLabelText('Owner age')).toBeInTheDocument();
    expect(screen.getByLabelText('Product')).toBe(screen.getByTestId('quote-product'));
    expect(screen.getByTestId('quote-submit')).toBeEnabled();
  });
});
