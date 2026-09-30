/**
 * Typed calls for the underwriting endpoints (api-contracts.md §2.12–2.15).
 *
 * Reason-code descriptions are never hardcoded in the UI: they come from the case's own rule version
 * through the catalog endpoint (AC-04), so a v2 rule set changes the wording without a code change.
 */
import { listVersions } from './catalog';
import type { ApiClient } from './client';
import type {
  AuditResponse,
  DecisionRequest,
  DecisionResult,
  OverrideRequest,
  OverrideResult,
  ProductCode,
  QueueItem,
  QueueStatus,
} from '../types/applications';

export function queuePath(): string {
  return '/api/underwriting/queue';
}

export function decisionPath(applicationId: string): string {
  return `/api/underwriting/applications/${encodeURIComponent(applicationId)}/decision`;
}

export function overridePath(applicationId: string): string {
  return `/api/underwriting/applications/${encodeURIComponent(applicationId)}/override`;
}

export function auditPath(applicationId: string): string {
  return `/api/underwriting/applications/${encodeURIComponent(applicationId)}/audit`;
}

/**
 * §2.12 — the review queue, oldest first. UNDERWRITER may only ask for `MANUAL_REVIEW`; ADMIN sees
 * both statuses when `status` is omitted.
 */
export function getQueue(api: ApiClient, status?: QueueStatus): Promise<readonly QueueItem[]> {
  return api.get<readonly QueueItem[]>(queuePath(), status === undefined ? {} : { query: { status } });
}

/** §2.13 — record an underwriter decision (`APPROVE` → AUTO_BIND, `DECLINE` → DECLINED). */
export function submitDecision(
  api: ApiClient,
  applicationId: string,
  body: DecisionRequest,
): Promise<DecisionResult> {
  return api.post<DecisionResult>(decisionPath(applicationId), body);
}

/** §2.14 — admin override of a DECLINED application; comment 10–500 characters. */
export function submitOverride(
  api: ApiClient,
  applicationId: string,
  body: OverrideRequest,
): Promise<OverrideResult> {
  return api.post<OverrideResult>(overridePath(applicationId), body);
}

/** §2.15 — decisions, overrides and audit records for one application, oldest first. */
export function getAudit(api: ApiClient, applicationId: string): Promise<AuditResponse> {
  return api.get<AuditResponse>(auditPath(applicationId));
}

/**
 * `underwriting.reason_codes` of one rule version, read through `GET /api/products/{product}/versions`
 * (§2.3). Returns an empty map when the version is unknown or its rule file was trimmed.
 */
export async function fetchReasonCodes(
  api: ApiClient,
  product: ProductCode,
  ruleVersion: number,
): Promise<Readonly<Record<string, string>>> {
  const versions = await listVersions(api, product);
  const match = versions.find((version) => version.version === ruleVersion);
  return match?.rules?.underwriting.reason_codes ?? {};
}
