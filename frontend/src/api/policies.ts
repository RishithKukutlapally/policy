/**
 * Typed calls for the policy endpoints (api-contracts.md §2.16–2.18).
 *
 * The server scopes `GET /api/policies` by actor: a CUSTOMER receives only their own policies and a
 * CUSTOMER asking for someone else's policy number gets 404 `NOT_FOUND` — the UI never filters for
 * authorisation itself.
 */
import type { ApiClient } from './client';
import type { PolicyDetail, PolicyListFilter, PolicySummary } from '../types/policies';

export function policiesPath(): string {
  return '/api/policies';
}

export function policyPath(policyNumber: string): string {
  return `/api/policies/${encodeURIComponent(policyNumber)}`;
}

export function issuePath(applicationId: string): string {
  return `/api/applications/${encodeURIComponent(applicationId)}/issue`;
}

/** §2.17 — the caller's policies, ordered by effective date then policy number. */
export function listPolicies(
  api: ApiClient,
  filter: PolicyListFilter = {},
): Promise<readonly PolicySummary[]> {
  return api.get<readonly PolicySummary[]>(policiesPath(), {
    query: { product: filter.product, status: filter.status },
  });
}

/** §2.18 — one policy with its endorsements, transitions, payments and refunds. */
export function getPolicy(api: ApiClient, policyNumber: string): Promise<PolicyDetail> {
  return api.get<PolicyDetail>(policyPath(policyNumber));
}

/** §2.16 — issue an `AUTO_BIND` application; 409 `INVALID_APPLICATION_STATE` for any other status. */
export function issuePolicy(api: ApiClient, applicationId: string): Promise<PolicySummary> {
  // The contract defines no request body, so none is sent (no `Content-Type`, no payload).
  return api.request<PolicySummary>(issuePath(applicationId), { method: 'POST' });
}
