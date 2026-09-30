/**
 * Typed calls for the product catalog endpoints (api-contracts.md §2.2–2.6).
 *
 * Bodies are never logged: rule files are not PII but the shared client rule applies (NFR-03).
 */
import type { ApiClient } from './client';
import type {
  CatalogVersion,
  ProductCode,
  ProductSummary,
  PublishResult,
  RuleFileDraftBody,
  RuleVersionMutationResult,
} from '../types/catalog';

export function productsPath(): string {
  return '/api/products';
}

export function versionsPath(product: ProductCode): string {
  return `/api/products/${product}/versions`;
}

export function versionPath(product: ProductCode, version: number): string {
  return `${versionsPath(product)}/${version}`;
}

export function publishPath(product: ProductCode, version: number): string {
  return `${versionPath(product, version)}/publish`;
}

/** §2.2 — ordered TERM_LIFE, MOTOR, HOUSEHOLD. Open to every role. */
export function listProducts(api: ApiClient): Promise<readonly ProductSummary[]> {
  return api.get<readonly ProductSummary[]>(productsPath());
}

/** §2.3 — every version of one product, ascending. Open to every role. */
export function listVersions(
  api: ApiClient,
  product: ProductCode,
): Promise<readonly CatalogVersion[]> {
  return api.get<readonly CatalogVersion[]>(versionsPath(product));
}

/** §2.4 — create a DRAFT from a full rule-file body. ADMIN only (409 `DRAFT_ALREADY_OPEN`). */
export function createDraft(
  api: ApiClient,
  product: ProductCode,
  body: RuleFileDraftBody,
): Promise<RuleVersionMutationResult> {
  return api.post<RuleVersionMutationResult>(versionsPath(product), body);
}

/** §2.5 — replace an open DRAFT. ADMIN only (409 `VERSION_IMMUTABLE` when PUBLISHED). */
export function replaceDraft(
  api: ApiClient,
  product: ProductCode,
  version: number,
  body: RuleFileDraftBody,
): Promise<RuleVersionMutationResult> {
  return api.put<RuleVersionMutationResult>(versionPath(product, version), body);
}

/** §2.6 — publish a DRAFT; the version becomes active. ADMIN only. */
export function publishVersion(
  api: ApiClient,
  product: ProductCode,
  version: number,
): Promise<PublishResult> {
  return api.post<PublishResult>(publishPath(product, version), undefined);
}
