/**
 * Typed calls for the cancellation endpoints (api-contracts.md §2.23–2.24).
 *
 * The preview writes nothing, so the screen may call it on every date change; the refund figures it
 * returns are the same ones `cancelPolicy` persists (AC-19).
 */
import type { ApiClient } from './client';
import type { IsoDate } from '../types/api';
import type { CancelRequest, CancelResult, RefundBreakdown } from '../types/cancellation';
import { policyPath } from './policies';

export function cancellationPreviewPath(policyNumber: string): string {
  return `${policyPath(policyNumber)}/cancellation-preview`;
}

export function cancelPath(policyNumber: string): string {
  return `${policyPath(policyNumber)}/cancel`;
}

/** §2.23 — refund breakdown for a candidate date; 422 `OUTSIDE_TERM` outside the policy term. */
export function getCancellationPreview(
  api: ApiClient,
  policyNumber: string,
  date: IsoDate,
): Promise<RefundBreakdown> {
  return api.get<RefundBreakdown>(cancellationPreviewPath(policyNumber), { query: { date } });
}

/** §2.24 — cancel and record the refund; 409 `INVALID_POLICY_STATE` when already terminal. */
export function cancelPolicy(
  api: ApiClient,
  policyNumber: string,
  body: CancelRequest,
): Promise<CancelResult> {
  return api.post<CancelResult>(cancelPath(policyNumber), body);
}
