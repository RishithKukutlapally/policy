/**
 * Policy DTOs mirroring specs/design/api-contracts.md §2.16–2.18.
 *
 * Every money value is a 2-decimal string (NFR-01); the UI only formats it. KYC identifiers arrive
 * pre-masked from the server (`aadhaar_masked`, `pan_masked`) and no raw variant is ever modelled
 * here, so a raw Aadhaar or PAN cannot reach the DOM through these types (NFR-03).
 */
import type { IsoDate, IsoDateTime, MoneyString, ProductCode } from './api';

/** docs/conventions.md → `PolicyStatus`. */
export type PolicyStatus = 'ACTIVE' | 'ENDORSED' | 'LAPSED' | 'CANCELLED' | 'RENEWED';

export type EndorsementType = 'CHANGE_ADDRESS' | 'ADD_NOMINEE' | 'CHANGE_SUM_INSURED';

export type RefundType = 'FREE_LOOK' | 'PRO_RATA';

/** Statuses that still allow endorse / renew / cancel (AC-10 terminal statuses do not). */
const LIVE_STATUSES: ReadonlySet<PolicyStatus> = new Set<PolicyStatus>(['ACTIVE', 'ENDORSED']);

export function isLive(status: PolicyStatus): boolean {
  return LIVE_STATUSES.has(status);
}

/** `GET /api/policies` item and `POST …/issue` response (§2.16, §2.17). */
export interface PolicySummary {
  readonly policy_number: string;
  readonly product: ProductCode;
  readonly status: PolicyStatus;
  readonly rule_version: number;
  readonly sum_insured: MoneyString;
  readonly premium: MoneyString;
  readonly currency: string;
  readonly effective_date: IsoDate;
  readonly expiry_date: IsoDate;
  readonly premium_due_date: IsoDate;
  /** `null` for a policy that can no longer renew (CANCELLED / LAPSED / RENEWED). */
  readonly next_premium_due_date: IsoDate | null;
  readonly previous_policy_number: string | null;
}

export interface Nominee {
  readonly nominee_name: string;
  readonly relationship: string;
  /** Decimal string, e.g. `"100.00"`. */
  readonly share_percent: string;
}

/** Masked-only view of the insured (§2.18 `insured`). */
export interface InsuredView {
  readonly full_name: string;
  readonly address: string;
  readonly aadhaar_masked: string;
  readonly pan_masked: string;
  readonly nominees: readonly Nominee[];
}

export interface PolicyTransition {
  readonly from_status: PolicyStatus | null;
  readonly to_status: PolicyStatus;
  readonly reason: string;
  readonly actor_id: string;
  readonly occurred_at: IsoDateTime;
}

/** `before` / `after` are endorsement-type specific snapshots, so they stay `unknown`-valued. */
export type EndorsementSnapshot = Readonly<Record<string, unknown>>;

export interface EndorsementRecord {
  readonly endorsement_id: number;
  readonly type: EndorsementType;
  readonly before: EndorsementSnapshot;
  readonly after: EndorsementSnapshot;
  /** Signed decimal string, e.g. `"0.00"` or `"-1200.00"`. */
  readonly premium_delta: MoneyString;
  readonly rule_version: number;
  readonly endorsement_date: IsoDate;
  readonly actor_id: string;
  readonly created_at: IsoDateTime;
}

export interface PremiumPayment {
  readonly payment_id: number;
  readonly due_date: IsoDate;
  readonly amount: MoneyString;
  readonly rule_version: number;
  readonly actor_id: string;
  /** `null` while the instalment is unpaid. */
  readonly paid_at: IsoDateTime | null;
}

export interface RefundRecord {
  readonly refund_id: number;
  readonly policy_number: string;
  readonly cancellation_date: IsoDate;
  readonly refund_type: RefundType;
  readonly premium_paid: MoneyString;
  readonly term_days: number;
  readonly days_elapsed: number;
  readonly unused_days: number;
  readonly admin_fee: MoneyString;
  readonly amount: MoneyString;
  readonly rule_version: number;
  readonly reason: string;
  readonly actor_id: string;
  readonly created_at: IsoDateTime;
}

/** `GET /api/policies/{policy_number}` (§2.18). */
export interface PolicyDetail extends PolicySummary {
  readonly successor_policy_number: string | null;
  readonly application_id: string;
  readonly insured: InsuredView;
  /** Oldest first. */
  readonly transitions: readonly PolicyTransition[];
  /** Oldest first. */
  readonly endorsements: readonly EndorsementRecord[];
  readonly payments: readonly PremiumPayment[];
  readonly refunds: readonly RefundRecord[];
}

/** Optional server-side filters of `GET /api/policies`. */
export interface PolicyListFilter {
  readonly product?: ProductCode;
  readonly status?: PolicyStatus;
}

export const PRODUCT_NAMES: Readonly<Record<ProductCode, string>> = {
  TERM_LIFE: 'Term Life',
  MOTOR: 'Motor',
  HOUSEHOLD: 'Household',
};
