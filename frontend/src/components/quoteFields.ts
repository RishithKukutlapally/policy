/**
 * Canonical per-product quote field sets (docs/conventions.md → "Quote input fields").
 *
 * One descriptor list per product drives both the rendered form and the request body, so the visible
 * inputs and the wire contract can never drift apart. Defaults reproduce the approved mockup E3-S3.
 */
import type {
  ProductCode,
  QuoteFieldSpec,
  QuoteFormValues,
  QuoteRequest,
} from '../types/quotes';

export const PRODUCT_LABELS: Readonly<Record<ProductCode, string>> = {
  TERM_LIFE: 'Term Life',
  MOTOR: 'Motor',
  HOUSEHOLD: 'Household',
};

export const PRODUCT_ORDER: readonly ProductCode[] = ['TERM_LIFE', 'MOTOR', 'HOUSEHOLD'];

export const DEFAULT_PRODUCT: ProductCode = 'MOTOR';

const SUM_INSURED: QuoteFieldSpec = {
  name: 'sum_insured',
  label: 'Sum insured',
  kind: 'money',
  hint: 'Rupees, two decimals — for example 500000.00.',
};

/** Eligibility ranges shown as hints; the active rule version remains authoritative (AC-01). */
const FIELD_SETS: Readonly<Record<ProductCode, readonly QuoteFieldSpec[]>> = {
  TERM_LIFE: [
    { ...SUM_INSURED, hint: `${SUM_INSURED.hint ?? ''} Term Life v1: 5,00,000.00 – 5,00,00,000.00.` },
    { name: 'age', label: 'Age', kind: 'integer', min: 18, max: 60 },
    { name: 'term_years', label: 'Term (years)', kind: 'integer', min: 5, max: 30 },
    { name: 'smoker', label: 'Smoker', kind: 'checkbox' },
  ],
  MOTOR: [
    { ...SUM_INSURED, hint: `${SUM_INSURED.hint ?? ''} Motor v1: 1,00,000.00 – 50,00,000.00.` },
    { name: 'owner_age', label: 'Owner age', kind: 'integer', min: 18, max: 75 },
    { name: 'vehicle_age_years', label: 'Vehicle age (years)', kind: 'integer', min: 0 },
    { name: 'engine_cc', label: 'Engine cc', kind: 'integer', min: 1 },
    {
      name: 'zone',
      label: 'Zone',
      kind: 'select',
      options: [
        { value: 'A', label: 'A' },
        { value: 'B', label: 'B' },
      ],
    },
    {
      name: 'ncb_percent',
      label: 'NCB %',
      kind: 'select',
      options: ['0', '20', '25', '35', '45', '50'].map((value) => ({ value, label: value })),
    },
  ],
  HOUSEHOLD: [
    { ...SUM_INSURED, hint: `${SUM_INSURED.hint ?? ''} Household v1: 5,00,000.00 – 2,00,00,000.00.` },
    { name: 'proposer_age', label: 'Proposer age', kind: 'integer', min: 18, max: 80 },
    {
      name: 'construction_type',
      label: 'Construction type',
      kind: 'select',
      options: [
        { value: 'CONCRETE', label: 'Concrete' },
        { value: 'BRICK', label: 'Brick' },
        { value: 'TIMBER', label: 'Timber' },
        { value: 'THATCH', label: 'Thatch' },
      ],
    },
    { name: 'in_flood_zone', label: 'In flood zone', kind: 'checkbox' },
    { name: 'has_security_system', label: 'Has security system', kind: 'checkbox' },
  ],
};

const DEFAULTS: Readonly<Record<ProductCode, QuoteFormValues>> = {
  TERM_LIFE: { sum_insured: '5000000.00', age: '35', term_years: '20', smoker: 'false' },
  MOTOR: {
    sum_insured: '500000.00',
    owner_age: '30',
    vehicle_age_years: '3',
    engine_cc: '1200',
    zone: 'A',
    ncb_percent: '20',
  },
  HOUSEHOLD: {
    sum_insured: '3000000.00',
    proposer_age: '40',
    construction_type: 'BRICK',
    in_flood_zone: 'true',
    has_security_system: 'true',
  },
};

export function fieldsFor(product: ProductCode): readonly QuoteFieldSpec[] {
  return FIELD_SETS[product];
}

/** Fresh form state for a product — used on first render and on every product switch. */
export function defaultsFor(product: ProductCode): QuoteFormValues {
  return { ...DEFAULTS[product] };
}

/**
 * Builds the `{product, inputs}` body. Integers are sent as JSON numbers, money and closed code
 * lists as strings; no arithmetic happens here (NFR-01). The server re-validates every field.
 */
export function buildQuoteRequest(product: ProductCode, values: QuoteFormValues): QuoteRequest {
  const inputs: Record<string, string | number | boolean> = {};
  for (const spec of fieldsFor(product)) {
    const raw = values[spec.name] ?? '';
    if (spec.kind === 'integer') {
      const parsed = Number.parseInt(raw, 10);
      // A blank or malformed box is forwarded verbatim so the server answers REQUIRED/INVALID_FORMAT.
      inputs[spec.name] = Number.isNaN(parsed) ? raw.trim() : parsed;
    } else if (spec.kind === 'checkbox') inputs[spec.name] = raw === 'true';
    else inputs[spec.name] = raw.trim();
  }
  return { product, inputs };
}
