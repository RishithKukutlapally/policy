/**
 * DTO types mirroring specs/design/api-contracts.md.
 * Money and rates always arrive as decimal strings — never `number` (NFR-01).
 */

export type ProductCode = 'TERM_LIFE' | 'MOTOR' | 'HOUSEHOLD';

export type RuleSetStatus = 'DRAFT' | 'PUBLISHED';

/** A decimal string with two fraction digits, e.g. "14322.00". */
export type MoneyString = string;

/** ISO-8601 date, `YYYY-MM-DD`. */
export type IsoDate = string;

/** ISO-8601 instant, e.g. "2026-01-01T00:00:00Z". */
export type IsoDateTime = string;

/** `GET /api/products` item (contract §2.2). */
export interface ProductSummary {
  readonly product: ProductCode;
  readonly name: string;
  /** `null` when the product has no PUBLISHED version. */
  readonly active_version: number | null;
  readonly currency: string;
}

/** `GET /api/products/{product}/versions` item (contract §2.3). */
export interface RuleSetVersionSummary {
  readonly product: ProductCode;
  readonly version: number;
  readonly status: RuleSetStatus;
  readonly effective_from: IsoDate;
  readonly is_active: boolean;
  readonly created_at: IsoDateTime;
  readonly rules: RuleFile;
}

export interface RuleFile {
  readonly product: ProductCode;
  readonly version: number;
  readonly status: RuleSetStatus;
  readonly effective_from: IsoDate;
  readonly currency: string;
  readonly premium: {
    readonly base_rate: string;
    readonly minimum_premium: MoneyString;
    readonly factors: Readonly<Record<string, unknown>>;
  };
  readonly eligibility: {
    readonly min_age: number;
    readonly max_age: number;
    readonly min_sum_insured: MoneyString;
    readonly max_sum_insured: MoneyString;
  };
  readonly underwriting: {
    readonly rules: readonly UnderwritingRule[];
    readonly reason_codes: Readonly<Record<string, string>>;
  };
  readonly endorsement: { readonly allowed_types: readonly string[] };
  readonly renewal: { readonly term_months: number; readonly grace_period_days: number };
  readonly cancellation: {
    readonly method: 'PRO_RATA';
    readonly free_look_days: number;
    readonly admin_fee: MoneyString;
  };
}

export interface UnderwritingRule {
  readonly when: string;
  readonly decision: 'AUTO_BIND' | 'MANUAL_REVIEW' | 'DECLINE';
  readonly reason_code: string;
}

/** Canonical error codes (docs/conventions.md → Error codes). */
export type ApiErrorCode =
  | 'VALIDATION_ERROR'
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'NO_PUBLISHED_VERSION'
  | 'VERSION_IMMUTABLE'
  | 'DRAFT_ALREADY_OPEN'
  | 'INVALID_POLICY_STATE'
  | 'INVALID_APPLICATION_STATE'
  | 'QUOTE_STALE'
  | 'PREMIUM_ALREADY_PAID'
  | 'OUTSIDE_RENEWAL_WINDOW'
  | 'INTERNAL_ERROR'
  // Client-side sentinels for transport / non-envelope failures.
  | 'NETWORK_ERROR'
  | 'UNKNOWN_ERROR';

export interface FieldErrorDetail {
  readonly field: string;
  readonly code: string;
}

/** `details` is a 422 field list, a plain object, or null. */
export type ApiErrorDetails =
  | readonly FieldErrorDetail[]
  | Readonly<Record<string, string>>
  | null;

/** The canonical envelope: `{"error": {code, message, details}}`. */
export interface ApiErrorEnvelope {
  readonly error: {
    readonly code: string;
    readonly message: string;
    readonly details?: ApiErrorDetails;
  };
}

export function isFieldErrorDetails(
  details: ApiErrorDetails,
): details is readonly FieldErrorDetail[] {
  return Array.isArray(details);
}
