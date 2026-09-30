/**
 * Application and underwriting DTOs (story E4-S5 · api-contracts.md §2.10–2.15).
 *
 * Money stays a decimal string the UI only formats (NFR-01) and KYC only ever crosses this boundary
 * masked on the way back: the response carries `aadhaar_masked` / `pan_masked`, never raw values
 * (NFR-03).
 */
import type { IsoDate, IsoDateTime, MoneyString, ProductCode } from './api';
import type { ActorRole } from './roles';

export type { ProductCode };

/** `ApplicationStatus` (docs/conventions.md → Lifecycle). */
export type ApplicationStatus =
  | 'SUBMITTED'
  | 'UNDERWRITING'
  | 'AUTO_BIND'
  | 'MANUAL_REVIEW'
  | 'DECLINED'
  | 'ISSUED';

/** Automatic/stored underwriting outcome. */
export type Decision = 'AUTO_BIND' | 'MANUAL_REVIEW' | 'DECLINE';

/** Request value on the decision endpoint (§2.13). */
export type UnderwriterDecision = 'APPROVE' | 'DECLINE';

/** Statuses the queue can be filtered by (§2.12). */
export type QueueStatus = 'MANUAL_REVIEW' | 'DECLINED';

/** Raw KYC leaving the browser once, inside the `POST /api/applications` body. Never logged. */
export interface KycInput {
  readonly full_name: string;
  readonly date_of_birth: IsoDate;
  readonly aadhaar: string;
  readonly pan: string;
  readonly address: string;
}

/** KYC as the API returns it — identifiers already masked server-side. */
export interface KycMasked {
  readonly full_name: string;
  readonly date_of_birth: IsoDate;
  readonly aadhaar_masked: string;
  readonly pan_masked: string;
  readonly address: string;
}

export interface HealthDeclarationInput {
  readonly has_pre_existing_condition: boolean;
  readonly details: string;
}

/** `POST /api/applications` body (§2.10). */
export interface ApplicationRequest {
  readonly quote_id: string;
  readonly kyc: KycInput;
  readonly health_declaration?: HealthDeclarationInput;
}

/** One reason code with the description from the case's rule version. */
export interface ReasonDetail {
  readonly code: string;
  readonly description: string;
}

export interface StatusHistoryEntry {
  readonly status: ApplicationStatus;
  readonly at: IsoDateTime;
}

/** `POST /api/applications` 201 body (§2.10). */
export interface ApplicationResponse {
  readonly application_id: string;
  readonly quote_id: string;
  readonly product: ProductCode;
  readonly rule_version: number;
  readonly status: ApplicationStatus;
  readonly decision: Decision;
  readonly reason_codes: readonly string[];
  readonly reasons: readonly ReasonDetail[];
  readonly kyc: KycMasked;
  readonly status_history: readonly StatusHistoryEntry[];
  readonly created_at: IsoDateTime;
}

/** One `underwriting_decisions` row (§2.12–2.15). */
export interface DecisionRow {
  readonly decision_id: number;
  readonly decision: Decision;
  readonly reason_codes: readonly string[];
  readonly reasons: readonly ReasonDetail[];
  readonly rule_version: number;
  /** `"SYSTEM"` for the automatic decision, otherwise the underwriter's actor id. */
  readonly decided_by: string;
  readonly comment: string | null;
  readonly created_at: IsoDateTime;
}

/** One `underwriting_overrides` row (§2.14–2.15). */
export interface OverrideRow {
  readonly override_id: number;
  readonly overridden_decision_id: number;
  readonly from_status: ApplicationStatus;
  readonly to_status: ApplicationStatus;
  readonly reason_code: string;
  readonly comment: string;
  readonly actor_id: string;
  readonly created_at: IsoDateTime;
}

/** `GET /api/applications/{application_id}` 200 body (§2.11). */
export interface ApplicationDetail extends ApplicationResponse {
  readonly decisions: readonly DecisionRow[];
  readonly overrides: readonly OverrideRow[];
  readonly policy_number: string | null;
}

/** `GET /api/underwriting/queue` item (§2.12) — no KYC is included. */
export interface QueueItem {
  readonly application_id: string;
  readonly product: ProductCode;
  readonly status: ApplicationStatus;
  readonly rule_version: number;
  readonly reason_codes: readonly string[];
  readonly sum_insured: MoneyString;
  readonly premium: MoneyString;
  readonly submitted_at: IsoDateTime;
  readonly decisions: readonly DecisionRow[];
}

/** `POST …/decision` body (§2.13). */
export interface DecisionRequest {
  readonly decision: UnderwriterDecision;
  readonly reason_codes: readonly string[];
  readonly comment: string;
}

/** `POST …/decision` 200 body (§2.13). */
export interface DecisionResult {
  readonly application_id: string;
  readonly status: ApplicationStatus;
  readonly decision: DecisionRow;
}

/** `POST …/override` body (§2.14) — exactly one code, comment 10–500 characters. */
export interface OverrideRequest {
  readonly reason_code: string;
  readonly comment: string;
}

/** `POST …/override` 200 body (§2.14). */
export interface OverrideResult {
  readonly application_id: string;
  readonly status: ApplicationStatus;
  readonly override: OverrideRow;
}

/** One `audit_records` row (§2.15) — `detail` never carries PII. */
export interface AuditRecord {
  readonly action: string;
  readonly actor_id: string;
  readonly actor_role: ActorRole | 'SYSTEM';
  readonly entity_type: string;
  readonly entity_id: string;
  readonly detail: Readonly<Record<string, unknown>> | null;
  readonly correlation_id: string;
  readonly created_at: IsoDateTime;
}

/** `GET …/audit` 200 body (§2.15), all lists oldest first. */
export interface AuditResponse {
  readonly application_id: string;
  readonly decisions: readonly DecisionRow[];
  readonly overrides: readonly OverrideRow[];
  readonly audit_records: readonly AuditRecord[];
}

/** Raw KYC form state; held in memory only and cleared once the application is submitted. */
export type KycFormValues = Readonly<Record<keyof KycInput, string>>;
