/**
 * Shared synthetic fixtures for the sprint 3/4 lifecycle screens (E6-S3, E7-S4, E8-S3, E9-S2).
 *
 * Values mirror the worked examples in the stories and mockups so a test asserting `+₹1,537.26` or
 * `₹8,791.10` is asserting the same number the backend contract promises. Synthetic data only — the
 * KYC fields are masked exactly as the server sends them (NFR-03, project rule 4).
 */
import type { CatalogVersion } from '../types/catalog';
import type { PolicyDetail, PolicySummary } from '../types/policies';
import type { RuleFile } from '../types/api';

/** MO-2026-000001 from E6-S3: premium 15500.00, term 2026-03-01 – 2027-02-28. */
export const MOTOR_SUMMARY: PolicySummary = {
  policy_number: 'MO-2026-000001',
  product: 'MOTOR',
  status: 'ACTIVE',
  rule_version: 1,
  sum_insured: '500000.00',
  premium: '15500.00',
  currency: 'INR',
  effective_date: '2026-03-01',
  expiry_date: '2027-02-28',
  premium_due_date: '2026-03-01',
  next_premium_due_date: '2027-03-01',
  previous_policy_number: null,
};

export const MOTOR_DETAIL: PolicyDetail = {
  ...MOTOR_SUMMARY,
  successor_policy_number: null,
  application_id: '7b2e4d10-5c3a-4f8e-b1d2-9e0a6c4f3b21',
  insured: {
    full_name: 'Test Customer 01',
    address: '1 Sample Street, Testville',
    aadhaar_masked: 'XXXX-XXXX-0001',
    pan_masked: 'XXXXX0001X',
    nominees: [],
  },
  transitions: [
    {
      from_status: null,
      to_status: 'ACTIVE',
      reason: 'ISSUED',
      actor_id: 'cust-001',
      occurred_at: '2026-03-01T10:05:00Z',
    },
  ],
  endorsements: [],
  payments: [
    {
      payment_id: 1,
      due_date: '2026-03-01',
      amount: '15500.00',
      rule_version: 1,
      actor_id: 'cust-001',
      paid_at: '2026-03-01T10:05:00Z',
    },
  ],
  refunds: [],
};

/** The same policy after the CHANGE_SUM_INSURED endorsement of E6-S3 criterion 4. */
export const MOTOR_DETAIL_ENDORSED: PolicyDetail = {
  ...MOTOR_DETAIL,
  status: 'ENDORSED',
  sum_insured: '600000.00',
  transitions: [
    ...MOTOR_DETAIL.transitions,
    {
      from_status: 'ACTIVE',
      to_status: 'ENDORSED',
      reason: 'ENDORSEMENT:CHANGE_SUM_INSURED',
      actor_id: 'cust-001',
      occurred_at: '2026-09-01T11:20:00Z',
    },
  ],
  endorsements: [
    {
      endorsement_id: 18,
      type: 'CHANGE_SUM_INSURED',
      before: { sum_insured: '500000.00' },
      after: { sum_insured: '600000.00' },
      premium_delta: '1537.26',
      rule_version: 1,
      endorsement_date: '2026-09-01',
      actor_id: 'cust-001',
      created_at: '2026-09-01T11:20:00Z',
    },
  ],
};

/** TL-2026-000001 from E8-S3: premium paid 12000.00, term 2026-01-01 – 2026-12-31. */
export const TERM_LIFE_DETAIL: PolicyDetail = {
  ...MOTOR_DETAIL,
  policy_number: 'TL-2026-000001',
  product: 'TERM_LIFE',
  sum_insured: '5000000.00',
  premium: '12000.00',
  effective_date: '2026-01-01',
  expiry_date: '2026-12-31',
  premium_due_date: '2026-01-01',
  next_premium_due_date: '2027-01-01',
  payments: [
    {
      payment_id: 1,
      due_date: '2026-01-01',
      amount: '12000.00',
      rule_version: 1,
      actor_id: 'cust-001',
      paid_at: '2026-01-01T09:12:00Z',
    },
  ],
};

/** MOTOR v1 rule file, trimmed to the parts the Endorse screen reads. */
const MOTOR_RULES: RuleFile = {
  product: 'MOTOR',
  version: 1,
  status: 'PUBLISHED',
  effective_from: '2026-01-01',
  currency: 'INR',
  premium: { base_rate: '0.031', minimum_premium: '1500.00', factors: {} },
  eligibility: {
    min_age: 18,
    max_age: 70,
    min_sum_insured: '100000.00',
    max_sum_insured: '5000000.00',
  },
  underwriting: { rules: [], reason_codes: {} },
  endorsement: { allowed_types: ['CHANGE_ADDRESS', 'ADD_NOMINEE', 'CHANGE_SUM_INSURED'] },
  renewal: { term_months: 12, grace_period_days: 30 },
  cancellation: { method: 'PRO_RATA', free_look_days: 15, admin_fee: '250.00' },
};

export const MOTOR_VERSION_V1: CatalogVersion = {
  product: 'MOTOR',
  version: 1,
  status: 'PUBLISHED',
  effective_from: '2026-01-01',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  rules: MOTOR_RULES,
};

/** A v2 whose rule set no longer allows a sum-insured change — the selector must hide it. */
export const MOTOR_VERSION_V2: CatalogVersion = {
  ...MOTOR_VERSION_V1,
  version: 2,
  rules: { ...MOTOR_RULES, version: 2, endorsement: { allowed_types: ['CHANGE_ADDRESS'] } },
};
