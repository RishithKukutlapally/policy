/**
 * Story E2-S4 (AC-02, AC-11, AC-24) — Product Catalog Manager screen.
 *
 * The backend endpoints do not exist yet: `src/api/catalog` is mocked so the screen is tested
 * purely against the contract in specs/design/api-contracts.md §2.2–2.6.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { navTestId } from '../app/navigation';
import { RoleProvider, ROLE_STORAGE_KEY } from '../app/RoleContext';
import { CatalogPage } from '../pages/CatalogPage';
import { setViewportMatches } from '../test/setup';
import type { CatalogVersion } from '../types/catalog';
import type { ActorRole } from '../types/roles';
import type { ProductSummary, RuleFile } from '../types/api';

vi.mock('../api/catalog', () => ({
  listProducts: vi.fn(),
  listVersions: vi.fn(),
  createDraft: vi.fn(),
  replaceDraft: vi.fn(),
  publishVersion: vi.fn(),
}));

import { createDraft, listProducts, listVersions, publishVersion } from '../api/catalog';

const PRODUCTS: readonly ProductSummary[] = [
  { product: 'TERM_LIFE', name: 'Term Life', active_version: 1, currency: 'INR' },
  { product: 'MOTOR', name: 'Motor', active_version: 1, currency: 'INR' },
  { product: 'HOUSEHOLD', name: 'Household', active_version: null, currency: 'INR' },
];

const MOTOR_RULES: RuleFile = {
  product: 'MOTOR',
  version: 1,
  status: 'PUBLISHED',
  effective_from: '2026-01-01',
  currency: 'INR',
  premium: { base_rate: '0.0310', minimum_premium: '2500.00', factors: { zone_rates: { A: '1.05' } } },
  eligibility: {
    min_age: 18,
    max_age: 75,
    min_sum_insured: '100000.00',
    max_sum_insured: '5000000.00',
  },
  underwriting: {
    rules: [{ when: 'vehicle_age_years > 15', decision: 'DECLINE', reason_code: 'MO-UW-001' }],
    reason_codes: { 'MO-UW-001': 'Vehicle older than 15 years' },
  },
  endorsement: { allowed_types: ['CHANGE_ADDRESS'] },
  renewal: { term_months: 12, grace_period_days: 30 },
  cancellation: { method: 'PRO_RATA', free_look_days: 15, admin_fee: '250.00' },
};

const MOTOR_VERSIONS: readonly CatalogVersion[] = [
  {
    product: 'MOTOR',
    version: 1,
    status: 'PUBLISHED',
    effective_from: '2026-01-01',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    rules: MOTOR_RULES,
  },
  {
    product: 'MOTOR',
    version: 2,
    status: 'DRAFT',
    effective_from: '2026-11-01',
    is_active: false,
    created_at: '2026-10-20T10:00:00Z',
    rules: { ...MOTOR_RULES, version: 2, status: 'DRAFT', effective_from: '2026-11-01' },
  },
];

const mockListProducts = vi.mocked(listProducts);
const mockListVersions = vi.mocked(listVersions);
const mockCreateDraft = vi.mocked(createDraft);
const mockPublishVersion = vi.mocked(publishVersion);

function renderCatalog(role: ActorRole = 'ADMIN'): void {
  globalThis.localStorage.setItem(ROLE_STORAGE_KEY, role);
  render(
    <RoleProvider>
      <MemoryRouter initialEntries={['/admin/catalog']}>
        <CatalogPage />
      </MemoryRouter>
    </RoleProvider>,
  );
}

async function expandMotor(): Promise<void> {
  await userEvent.click(await screen.findByTestId('expand-MOTOR'));
  await screen.findByTestId('versions-table');
}

beforeEach(() => {
  vi.clearAllMocks();
  mockListProducts.mockResolvedValue(PRODUCTS);
  mockListVersions.mockResolvedValue(MOTOR_VERSIONS);
});

describe('CatalogPage — product list (AC-02)', () => {
  it('renders one row per product with name, active version and currency', async () => {
    renderCatalog();

    const termLife = await screen.findByTestId('product-row-TERM_LIFE');
    expect(within(termLife).getByText('Term Life')).toBeInTheDocument();
    expect(within(termLife).getByText('v1')).toBeInTheDocument();
    expect(screen.getByTestId('product-row-MOTOR')).toBeInTheDocument();

    const household = screen.getByTestId('product-row-HOUSEHOLD');
    expect(within(household).getByText('None')).toBeInTheDocument();
    expect(screen.getAllByTestId(/^product-row-/)).toHaveLength(3);
  });

  it('renders a load-failure banner with a working Retry button', async () => {
    mockListProducts.mockRejectedValueOnce(
      new ApiError({ code: 'INTERNAL_ERROR', message: 'boom', details: null, status: 500 }),
    );
    renderCatalog();

    const banner = await screen.findByTestId('load-error');
    expect(banner).toHaveTextContent('INTERNAL_ERROR');

    await userEvent.click(screen.getByTestId('retry-products'));
    expect(await screen.findByTestId('product-row-MOTOR')).toBeInTheDocument();
  });
});

describe('CatalogPage — versions (AC-11)', () => {
  it('expands a product to show its versions with text status badges', async () => {
    renderCatalog();
    await expandMotor();

    expect(mockListVersions).toHaveBeenCalledWith(expect.anything(), 'MOTOR');
    const v1 = screen.getByTestId('version-row-1');
    expect(within(v1).getByText('PUBLISHED')).toBeInTheDocument();
    expect(within(v1).getByText('Active')).toBeInTheDocument();
    expect(within(v1).queryByTestId('publish-v1')).not.toBeInTheDocument();

    const v2 = screen.getByTestId('version-row-2');
    expect(within(v2).getByText('DRAFT')).toBeInTheDocument();
    expect(within(v2).getByTestId('publish-v2')).toBeInTheDocument();
  });

  it('formats the minimum premium from the decimal string with Intl.NumberFormat', async () => {
    renderCatalog();
    await expandMotor();

    expect(within(screen.getByTestId('version-row-1')).getByTestId('min-premium-1')).toHaveTextContent(
      /2,500\.00/,
    );
  });

  it('publishes a draft only after the confirm dialog is accepted', async () => {
    mockPublishVersion.mockResolvedValue({
      product: 'MOTOR',
      version: 2,
      status: 'PUBLISHED',
      is_active: true,
    });
    renderCatalog();
    await expandMotor();

    await userEvent.click(screen.getByTestId('publish-v2'));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('MOTOR v2');
    expect(mockPublishVersion).not.toHaveBeenCalled();

    await userEvent.click(screen.getByTestId('publish-confirm'));
    await waitFor(() => expect(mockPublishVersion).toHaveBeenCalledWith(expect.anything(), 'MOTOR', 2));
  });

  it('closes the confirm dialog on Escape without publishing', async () => {
    renderCatalog();
    await expandMotor();

    await userEvent.click(screen.getByTestId('publish-v2'));
    await screen.findByRole('dialog');
    await userEvent.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(mockPublishVersion).not.toHaveBeenCalled();
  });

  it('renders a VERSION_IMMUTABLE banner when publishing a published version', async () => {
    mockPublishVersion.mockRejectedValue(
      new ApiError({
        code: 'VERSION_IMMUTABLE',
        message: 'MOTOR v2 is already PUBLISHED',
        details: null,
        status: 409,
      }),
    );
    renderCatalog();
    await expandMotor();

    await userEvent.click(screen.getByTestId('publish-v2'));
    await userEvent.click(screen.getByTestId('publish-confirm'));

    const banner = await screen.findByTestId('banner-VERSION_IMMUTABLE');
    expect(banner).toHaveTextContent('already PUBLISHED');
  });
});

describe('CatalogPage — draft editor errors', () => {
  it('shows a 422 field error next to the offending field path', async () => {
    mockCreateDraft.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: 'Rule file failed schema validation',
        details: [{ field: 'premium.base_rate', code: 'MONEY_MUST_BE_STRING' }],
        status: 422,
      }),
    );
    renderCatalog();
    await expandMotor();

    await userEvent.click(screen.getByTestId('create-draft'));

    const fieldError = await screen.findByTestId('field-error-premium.base_rate');
    expect(fieldError).toHaveTextContent('premium.base_rate');
    expect(fieldError).toHaveTextContent('MONEY_MUST_BE_STRING');
    expect(screen.getByTestId('rule-json')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows a DRAFT_ALREADY_OPEN banner', async () => {
    mockCreateDraft.mockRejectedValue(
      new ApiError({
        code: 'DRAFT_ALREADY_OPEN',
        message: 'MOTOR already has an open draft',
        details: null,
        status: 409,
      }),
    );
    renderCatalog();
    await expandMotor();

    await userEvent.click(screen.getByTestId('create-draft'));

    expect(await screen.findByTestId('banner-DRAFT_ALREADY_OPEN')).toHaveTextContent('open draft');
  });
});

describe('CatalogPage — guards and responsiveness', () => {
  it('shows "Not authorised" for a non-ADMIN role and loads nothing', async () => {
    renderCatalog('CUSTOMER');

    expect(await screen.findByTestId('not-authorised')).toHaveTextContent('Not authorised');
    expect(screen.queryByTestId('product-table')).not.toBeInTheDocument();
    expect(mockListProducts).not.toHaveBeenCalled();
  });

  it('collapses the product table to cards below the breakpoint (AC-24)', async () => {
    setViewportMatches(true);
    renderCatalog();

    expect(await screen.findByTestId('product-cards')).toBeInTheDocument();
    expect(screen.queryByTestId('product-table')).not.toBeInTheDocument();
    expect(screen.getByTestId('product-row-MOTOR')).toBeInTheDocument();
  });
});

describe('navigation hook (E1-S5 regression)', () => {
  it('keeps the admin nav item addressable as nav-catalog', () => {
    expect(navTestId({ label: 'Product Catalog', to: '/admin/catalog', testId: 'nav-catalog' })).toBe(
      'nav-catalog',
    );
    expect(navTestId({ label: 'Portfolio', to: '/admin/portfolio' })).toBe('nav-admin-portfolio');
  });
});
