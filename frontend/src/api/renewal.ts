/**
 * Typed calls for the renewal, payment and end-of-day endpoints (api-contracts.md §2.20–2.22, §2.25).
 *
 * The renewal premium always comes from the quote the server returned; `payPremium` echoes that exact
 * decimal string back so the amount can never drift from the active rule version (NFR-01, AC-17).
 */
import type { ApiClient } from './client';
import type { IsoDate, MoneyString } from '../types/api';
import type { PolicySummary } from '../types/policies';
import type { EndOfDayResult, PaymentReceipt, RenewalQuote } from '../types/renewal';
import { policyPath } from './policies';

export function renewalPath(policyNumber: string): string {
  return `${policyPath(policyNumber)}/renewal`;
}

export function renewPath(policyNumber: string): string {
  return `${policyPath(policyNumber)}/renew`;
}

export function paymentsPath(policyNumber: string): string {
  return `${policyPath(policyNumber)}/payments`;
}

export function endOfDayPath(): string {
  return '/api/admin/end-of-day';
}

/** §2.20 — the renewal quote on the product's active version. 409 for a terminal policy. */
export function getRenewalQuote(api: ApiClient, policyNumber: string): Promise<RenewalQuote> {
  return api.get<RenewalQuote>(renewalPath(policyNumber));
}

/** §2.22 — record the renewal premium. `amount` must equal the quote's `renewal_premium`. */
export function payPremium(
  api: ApiClient,
  policyNumber: string,
  amount: MoneyString,
): Promise<PaymentReceipt> {
  return api.post<PaymentReceipt>(paymentsPath(policyNumber), { amount });
}

/** §2.21 — early renewal inside the window; 201 with the successor policy. No request body. */
export function renewPolicy(api: ApiClient, policyNumber: string): Promise<PolicySummary> {
  return api.request<PolicySummary>(renewPath(policyNumber), { method: 'POST' });
}

/** §2.25 — ADMIN only; idempotent per `as_of` (a second run returns zero counts, AC-18). */
export function runEndOfDay(api: ApiClient, asOf: IsoDate): Promise<EndOfDayResult> {
  return api.post<EndOfDayResult>(endOfDayPath(), { as_of: asOf });
}
