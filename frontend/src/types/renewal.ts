/**
 * Renewal, payment and end-of-day DTOs mirroring specs/design/api-contracts.md §2.20–2.22, §2.25.
 *
 * Every amount is a 2-decimal string from the active rule version; the UI never re-derives a premium,
 * a due date or a grace end date (NFR-01, AC-07).
 */
import type { IsoDate, IsoDateTime, MoneyString } from './api';

/** 200 body of `GET /api/policies/{policy_number}/renewal` (§2.20). */
export interface RenewalQuote {
  readonly policy_number: string;
  readonly renewable: boolean;
  /** `null` when the policy can no longer renew. */
  readonly renewal_premium: MoneyString | null;
  readonly rule_version: number;
  readonly currency: string;
  readonly due_date: IsoDate;
  /** `due_date` + the rule version's grace period (30 days in v1). */
  readonly grace_end_date: IsoDate;
  readonly renewal_window_opens: IsoDate;
  readonly paid: boolean;
}

/** 201 body of `POST /api/policies/{policy_number}/payments` (§2.22). */
export interface PaymentReceipt {
  readonly payment_id: number;
  readonly policy_number: string;
  readonly amount: MoneyString;
  readonly due_date: IsoDate;
  readonly rule_version: number;
  readonly actor_id: string;
  readonly paid_at: IsoDateTime;
}

/** `renewed_policies[]` of the end-of-day result: old number → successor number. */
export interface RenewedPair {
  readonly from: string;
  readonly to: string;
}

/**
 * `failed_policies[]` item. ASSUMED (mockup E7-S4): each entry names the policy and carries a short
 * operator-facing message; the contract only shows the empty list.
 */
export interface EndOfDayFailure {
  readonly policy_number: string;
  readonly error: string;
}

/** 200 body of `POST /api/admin/end-of-day` (§2.25). Re-running an `as_of` returns zero counts. */
export interface EndOfDayResult {
  readonly as_of: IsoDate;
  readonly renewed: number;
  readonly lapsed: number;
  readonly in_grace: number;
  readonly not_renewable: number;
  readonly failed: number;
  readonly renewed_policies: readonly RenewedPair[];
  /** ASSUMED (mockup E7-S4): plain policy numbers. */
  readonly lapsed_policies: readonly string[];
  readonly failed_policies: readonly EndOfDayFailure[];
}

export interface EndOfDayCount {
  readonly label: string;
  readonly testId: string;
  readonly value: number;
}

/** The counts shown on the admin control, in the order the mockup lists them. */
export function endOfDayCounts(result: EndOfDayResult): readonly EndOfDayCount[] {
  return [
    { label: 'Renewed', testId: 'count-renewed', value: result.renewed },
    { label: 'Lapsed', testId: 'count-lapsed', value: result.lapsed },
    { label: 'In grace', testId: 'count-in-grace', value: result.in_grace },
    { label: 'Not renewable', testId: 'count-not-renewable', value: result.not_renewable },
    { label: 'Failed', testId: 'count-failed', value: result.failed },
  ];
}
