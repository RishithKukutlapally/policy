/**
 * Synthetic test data and API arrangement helpers (story E9-S4, docs/conventions.md → "Synthetic data").
 *
 * The specs prove journeys through the UI, but a journey that needs an *existing* quote, application or
 * policy arranges it through the same public API the UI calls — never by touching the database. All
 * identifiers are obviously fake: Aadhaar starts `9999`, PAN is `AAAAA0001A`, names are `Test Customer NN`.
 */
import type { ApiClient } from './app';

export const MOTOR_AUTO_BIND = {
  product: 'MOTOR',
  inputs: {
    sum_insured: '500000.00',
    owner_age: 30,
    vehicle_age_years: 3,
    engine_cc: 1200,
    zone: 'A',
    ncb_percent: '20',
  },
} as const;

/** `vehicle_age_years > 10` → MANUAL_REVIEW `MO-UW-002` (backend/policy_rules/motor/v1.json). */
export const MOTOR_MANUAL_REVIEW = {
  product: 'MOTOR',
  inputs: { ...MOTOR_AUTO_BIND.inputs, vehicle_age_years: 12 },
} as const;

/** `vehicle_age_years > 15` → DECLINE `MO-UW-001`. */
export const MOTOR_DECLINE = {
  product: 'MOTOR',
  inputs: { ...MOTOR_AUTO_BIND.inputs, vehicle_age_years: 18 },
} as const;

export const HOUSEHOLD_AUTO_BIND = {
  product: 'HOUSEHOLD',
  inputs: {
    sum_insured: '3000000.00',
    proposer_age: 40,
    construction_type: 'BRICK',
    in_flood_zone: false,
    has_security_system: true,
  },
} as const;

export interface KycValues {
  readonly full_name: string;
  readonly date_of_birth: string;
  readonly aadhaar: string;
  readonly pan: string;
  readonly address: string;
}

/** Synthetic KYC; `seq` keeps Aadhaar/PAN unique per applicant while staying in the dummy ranges. */
export function kycFor(seq: number): KycValues {
  const padded = String(seq).padStart(4, '0');
  return {
    full_name: `Test Customer ${String(seq).padStart(2, '0')}`,
    date_of_birth: '1990-04-12',
    aadhaar: `9999${padded}0000`.slice(0, 12),
    pan: `AAAAA${padded}A`,
    address: `${seq} Sample Street, Testville`,
  };
}

export const MASKED_AADHAAR = /^XXXX-XXXX-\d{4}$/;
export const MASKED_PAN = /^XXXXX\d{4}X$/;

export interface QuoteResult {
  readonly quote_id: string;
  readonly premium: string;
  readonly rule_version: number;
  readonly currency: string;
}

export interface ApplicationResult {
  readonly application_id: string;
  readonly decision: string;
  readonly status: string;
}

export interface PolicyResult {
  readonly policy_number: string;
  readonly premium: string;
  readonly status: string;
  readonly effective_date: string;
  readonly expiry_date: string;
}

/** `POST /api/quotes` as the customer. */
export async function createQuote(
  api: ApiClient,
  request: { product: string; inputs: Record<string, unknown> },
): Promise<QuoteResult> {
  return (await api.post('/api/quotes', request)) as QuoteResult;
}

/** `POST /api/applications` with synthetic KYC (and a health declaration for TERM_LIFE). */
export async function createApplication(
  api: ApiClient,
  quoteId: string,
  seq: number,
  healthDeclaration?: { has_pre_existing_condition: boolean; details: string },
): Promise<ApplicationResult> {
  const body: Record<string, unknown> = { quote_id: quoteId, kyc: kycFor(seq) };
  if (healthDeclaration !== undefined) body.health_declaration = healthDeclaration;
  return (await api.post('/api/applications', body)) as ApplicationResult;
}

/** Quote → application in one step; the decision comes back synchronously (AC-04). */
export async function arrangeApplication(
  api: ApiClient,
  quote: { product: string; inputs: Record<string, unknown> },
  seq: number,
): Promise<{ quote: QuoteResult; application: ApplicationResult }> {
  const created = await createQuote(api, quote);
  const application = await createApplication(api, created.quote_id, seq);
  return { quote: created, application };
}

/** Quote → application → issued policy, for the journeys that start from a live policy. */
export async function arrangePolicy(
  api: ApiClient,
  quote: { product: string; inputs: Record<string, unknown> },
  seq: number,
): Promise<PolicyResult> {
  const { application } = await arrangeApplication(api, quote, seq);
  if (application.decision !== 'AUTO_BIND') {
    throw new Error(`expected AUTO_BIND to arrange a policy, got ${application.decision}`);
  }
  return (await api.post(`/api/applications/${application.application_id}/issue`)) as PolicyResult;
}

export const POLICY_NUMBER = /^(TL|MO|HH)-\d{4}-\d{6}$/;
export const MOTOR_POLICY_NUMBER = /^MO-\d{4}-\d{6}$/;
/** `₹5,00,000.00` — `Intl.NumberFormat('en-IN')` grouping of a two-decimal decimal string. */
export const RUPEES = /^₹\d{1,3}(,\d{2,3})*\.\d{2}$/;
