/**
 * Admin portfolio DTOs mirroring specs/design/api-contracts.md §2.26.
 *
 * Counts are integers the server aggregated; money is a 2-decimal string. The dashboard sums nothing
 * (NFR-01) — `premium_collected`, `refunds_paid` and `premium_at_risk` are displayed as sent.
 */
import type { IsoDate, MoneyString, ProductCode } from './api';

/** A row of the "Renewal pipeline" table. */
export interface RenewalPipelineRow {
  readonly policy_number: string;
  readonly product: ProductCode;
  readonly due_date: IsoDate;
  /** `null` for a policy that is no longer renewable. */
  readonly renewal_premium: MoneyString | null;
  readonly paid: boolean;
}

/** A row of the "Lapse forecast" table. */
export interface LapseForecastRow {
  readonly policy_number: string;
  readonly product: ProductCode;
  readonly due_date: IsoDate;
  readonly grace_end_date: IsoDate;
  readonly premium: MoneyString;
}

export interface LapseForecast {
  readonly count: number;
  readonly premium_at_risk: MoneyString;
  readonly policies: readonly LapseForecastRow[];
}

/** 200 body of `GET /api/admin/portfolio` (§2.26). */
export interface PortfolioSnapshot {
  readonly as_of: IsoDate;
  readonly active_by_product: Readonly<Record<ProductCode, number>>;
  readonly premium_collected: MoneyString;
  readonly refunds_paid: MoneyString;
  readonly renewal_pipeline: readonly RenewalPipelineRow[];
  readonly lapse_forecast: LapseForecast;
}

/** Card order of the three product tiles (contract §2.2 order). */
export const PRODUCT_ORDER: readonly ProductCode[] = ['TERM_LIFE', 'MOTOR', 'HOUSEHOLD'];
