/**
 * Typed call for the admin portfolio endpoint (api-contracts.md §2.26).
 *
 * `as_of` is optional: omitting it lets the server use its own business date (DEC-012) rather than the
 * browser clock.
 */
import type { ApiClient } from './client';
import type { IsoDate } from '../types/api';
import type { PortfolioSnapshot } from '../types/portfolio';

export function portfolioPath(): string {
  return '/api/admin/portfolio';
}

/** §2.26 — ADMIN only; 403 for CUSTOMER and UNDERWRITER. */
export function getPortfolio(api: ApiClient, asOf?: IsoDate): Promise<PortfolioSnapshot> {
  return api.get<PortfolioSnapshot>(portfolioPath(), {
    query: { as_of: asOf === '' ? undefined : asOf },
  });
}
