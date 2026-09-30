/**
 * Cancellation DTOs mirroring specs/design/api-contracts.md §2.23–2.24.
 *
 * The refund is computed entirely by the backend (docs/conventions.md → refund formulas): the screen
 * shows `amount`, `admin_fee` and the gross pro-rata figure verbatim and never subtracts them itself
 * (NFR-01).
 */
import type { IsoDate, MoneyString } from './api';
import type { PolicyStatus, RefundRecord, RefundType } from './policies';

/** 200 body of `GET …/cancellation-preview?date=` (§2.23). Nothing is persisted. */
export interface RefundBreakdown {
  readonly policy_number: string;
  readonly cancellation_date: IsoDate;
  readonly refund_type: RefundType;
  readonly premium_paid: MoneyString;
  readonly term_days: number;
  readonly days_elapsed: number;
  readonly unused_days: number;
  readonly admin_fee: MoneyString;
  /** Net refund actually paid — `max(gross − admin_fee, 0.00)` on the server. */
  readonly amount: MoneyString;
  readonly rule_version: number;
  /**
   * ASSUMED (mockup E8-S3): the gross pro-rata figure before the admin fee, so AC-19's sentence
   * "₹8,791.10 = ₹9,041.10 pro-rata … − ₹250.00 admin fee" needs no client-side arithmetic. When the
   * server omits it the screen drops the gross clause rather than computing it.
   */
  readonly pro_rata_amount?: MoneyString;
}

export interface CancelRequest {
  readonly cancellation_date: IsoDate;
  /** Non-blank free text, ≤ 200 chars (contract OI-5: no enum). */
  readonly reason: string;
}

/** 200 body of `POST …/cancel` (§2.24). */
export interface CancelResult {
  readonly policy_number: string;
  readonly status: PolicyStatus;
  readonly refund: RefundRecord;
}

/** Free-text reason limit from §2.24. */
export const REASON_MAX_LENGTH = 200;
