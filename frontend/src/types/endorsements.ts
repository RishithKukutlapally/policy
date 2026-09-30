/**
 * Endorsement DTOs mirroring specs/design/api-contracts.md §2.19.
 *
 * `premium_delta` and `new_premium` are signed / plain 2-decimal strings computed by the backend; the
 * UI only formats them (NFR-01). The request is discriminated by `type` exactly as the contract table
 * describes, so an impossible combination (an address on a sum-insured change) cannot be constructed.
 */
import type { IsoDate, IsoDateTime, MoneyString } from './api';
import type { EndorsementSnapshot, EndorsementType, PolicySummary } from './policies';

/** `relationship` enum of the `ADD_NOMINEE` body (§2.19). */
export type NomineeRelationship = 'SPOUSE' | 'CHILD' | 'PARENT' | 'SIBLING' | 'OTHER';

export const NOMINEE_RELATIONSHIPS: readonly NomineeRelationship[] = [
  'SPOUSE',
  'CHILD',
  'PARENT',
  'SIBLING',
  'OTHER',
];

export interface ChangeAddressRequest {
  readonly type: 'CHANGE_ADDRESS';
  readonly address: string;
}

export interface AddNomineeRequest {
  readonly type: 'ADD_NOMINEE';
  readonly nominee_name: string;
  readonly relationship: NomineeRelationship;
  /** Decimal string 1–100, e.g. `"100.00"`. */
  readonly share_percent: string;
}

export interface ChangeSumInsuredRequest {
  readonly type: 'CHANGE_SUM_INSURED';
  readonly new_sum_insured: MoneyString;
}

export type EndorsementRequest = ChangeAddressRequest | AddNomineeRequest | ChangeSumInsuredRequest;

/** Fields shared by the `?preview=true` 200 and the 201 bodies (§2.19). */
interface EndorsementOutcome {
  readonly policy_number: string;
  readonly type: EndorsementType;
  readonly before: EndorsementSnapshot;
  readonly after: EndorsementSnapshot;
  readonly new_premium: MoneyString;
  /** Signed decimal string, e.g. `"1537.26"` or `"-1537.26"`. */
  readonly premium_delta: MoneyString;
  readonly rule_version: number;
  readonly endorsement_date: IsoDate;
}

/** 200 body of `POST …/endorsements?preview=true` — nothing is persisted. */
export interface EndorsementPreview extends EndorsementOutcome {
  readonly preview: true;
  /**
   * ASSUMED (mockup E6-S3): the server also returns the pro-ration window so the screen can explain
   * the delta without doing arithmetic. Optional — the delta alone is enough to render the preview.
   */
  readonly unused_days?: number;
  readonly term_days?: number;
}

/** 201 body of `POST …/endorsements` — includes the policy, now `ENDORSED`. */
export interface EndorsementResult extends EndorsementOutcome {
  readonly endorsement_id: number;
  readonly created_at: IsoDateTime;
  readonly policy: PolicySummary;
}

/** Human labels for the type selector; keys are the rule file's `endorsement.allowed_types`. */
export const ENDORSEMENT_LABELS: Readonly<Record<EndorsementType, string>> = {
  CHANGE_ADDRESS: 'Change address',
  ADD_NOMINEE: 'Add nominee',
  CHANGE_SUM_INSURED: 'Change sum insured',
};

const ENDORSEMENT_TYPES: ReadonlySet<string> = new Set<EndorsementType>([
  'CHANGE_ADDRESS',
  'ADD_NOMINEE',
  'CHANGE_SUM_INSURED',
]);

/** Narrows the rule file's `readonly string[]` to the types this screen can render. */
export function toEndorsementTypes(allowed: readonly string[]): readonly EndorsementType[] {
  return allowed.filter((value): value is EndorsementType => ENDORSEMENT_TYPES.has(value));
}
