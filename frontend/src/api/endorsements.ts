/**
 * Typed calls for the endorsement endpoint (api-contracts.md §2.19).
 *
 * `preview=true` and the real submission are the same endpoint, so both go through one path builder:
 * the only difference is the query flag and therefore the response shape. Bodies are never logged —
 * an `ADD_NOMINEE` request carries a person's name (NFR-03).
 */
import type { ApiClient } from './client';
import type { EndorsementPreview, EndorsementRequest, EndorsementResult } from '../types/endorsements';

export function endorsementsPath(policyNumber: string): string {
  return `/api/policies/${encodeURIComponent(policyNumber)}/endorsements`;
}

/** §2.19 `?preview=true` — 200 with the pro-rated delta; nothing is persisted. */
export function previewEndorsement(
  api: ApiClient,
  policyNumber: string,
  body: EndorsementRequest,
): Promise<EndorsementPreview> {
  return api.post<EndorsementPreview>(endorsementsPath(policyNumber), body, {
    query: { preview: true },
  });
}

/** §2.19 — 201 with the endorsement and the policy, now `ENDORSED`. */
export function createEndorsement(
  api: ApiClient,
  policyNumber: string,
  body: EndorsementRequest,
): Promise<EndorsementResult> {
  return api.post<EndorsementResult>(endorsementsPath(policyNumber), body);
}
