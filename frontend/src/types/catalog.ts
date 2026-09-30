/**
 * Product catalog DTOs (story E2-S4 · api-contracts.md §2.2–2.6).
 *
 * Extends the shared DTOs in `./api`; money and rates stay decimal strings (NFR-01).
 */
import type {
  IsoDate,
  ProductCode,
  ProductSummary,
  RuleFile,
  RuleSetStatus,
  RuleSetVersionSummary,
} from './api';

export type { ProductCode, ProductSummary, RuleFile, RuleSetStatus };

/**
 * A `GET /api/products/{product}/versions` item. `rules` is optional here: a server may trim the
 * embedded rule file, and the screen must still render the row.
 */
export interface CatalogVersion extends Omit<RuleSetVersionSummary, 'rules'> {
  readonly rules?: RuleFile;
}

/** 201 / 200 body of the DRAFT create and replace endpoints (§2.4, §2.5). */
export interface RuleVersionMutationResult {
  readonly product: ProductCode;
  readonly version: number;
  readonly status: RuleSetStatus;
}

/** 200 body of the publish endpoint (§2.6). */
export interface PublishResult extends RuleVersionMutationResult {
  readonly is_active: boolean;
}

/** Unparsed rule-file body typed by the editor before the server validates it. */
export type RuleFileDraftBody = Readonly<Record<string, unknown>>;

/** Editor mode: create a new DRAFT (POST) or replace the open one (PUT). */
export type DraftEditorMode = { readonly kind: 'create' } | { readonly kind: 'replace'; readonly version: number };

/** A 422 detail entry rendered inline next to its field path. */
export interface FieldIssue {
  readonly field: string;
  readonly code: string;
}

/** Effective-from is shown verbatim; never re-derived in the UI. */
export type EffectiveFrom = IsoDate;
