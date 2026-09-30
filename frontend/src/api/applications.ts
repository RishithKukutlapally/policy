/**
 * Typed calls for the application endpoints (api-contracts.md §2.10–2.11).
 *
 * The request body carries raw Aadhaar, PAN and (for TERM_LIFE) health answers: it is never logged
 * here or in the shared client (NFR-03).
 */
import type { ApiClient } from './client';
import type {
  ApplicationDetail,
  ApplicationRequest,
  ApplicationResponse,
} from '../types/applications';

export function applicationsPath(): string {
  return '/api/applications';
}

export function applicationPath(applicationId: string): string {
  return `${applicationsPath()}/${encodeURIComponent(applicationId)}`;
}

/** §2.10 — submit an application; the response is the synchronous underwriting outcome. CUSTOMER. */
export function createApplication(
  api: ApiClient,
  body: ApplicationRequest,
): Promise<ApplicationResponse> {
  return api.post<ApplicationResponse>(applicationsPath(), body);
}

/** §2.11 — the application with its decisions, overrides and (once issued) policy number. */
export function getApplication(api: ApiClient, applicationId: string): Promise<ApplicationDetail> {
  return api.get<ApplicationDetail>(applicationPath(applicationId));
}
