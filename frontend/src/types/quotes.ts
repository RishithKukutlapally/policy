/**
 * Quote DTOs and form descriptors (story E3-S3 · api-contracts.md §2.7–2.8).
 *
 * `sum_insured` and `premium` are decimal strings the UI only ever formats (NFR-01); the canonical
 * `inputs` field set per product comes from docs/conventions.md → "Quote input fields".
 */
import type { IsoDateTime, MoneyString, ProductCode } from './api';

export type { ProductCode };

export type Zone = 'A' | 'B';
export type NcbPercent = '0' | '20' | '25' | '35' | '45' | '50';
export type ConstructionType = 'CONCRETE' | 'BRICK' | 'TIMBER' | 'THATCH';

export interface TermLifeQuoteInputs {
  readonly sum_insured: MoneyString;
  readonly age: number;
  readonly term_years: number;
  readonly smoker: boolean;
}

export interface MotorQuoteInputs {
  readonly sum_insured: MoneyString;
  readonly owner_age: number;
  readonly vehicle_age_years: number;
  readonly engine_cc: number;
  readonly zone: Zone;
  readonly ncb_percent: NcbPercent;
}

export interface HouseholdQuoteInputs {
  readonly sum_insured: MoneyString;
  readonly proposer_age: number;
  readonly construction_type: ConstructionType;
  readonly in_flood_zone: boolean;
  readonly has_security_system: boolean;
}

export type QuoteInputs = TermLifeQuoteInputs | MotorQuoteInputs | HouseholdQuoteInputs;

/**
 * Wire shape of the `inputs` object. The per-product interfaces above describe what the server
 * expects; the form builds this open map from the product's field descriptors, and the server is the
 * authority on the exact field set (422 `UNKNOWN_FIELD` / `REQUIRED`).
 */
export type QuoteInputValues = Readonly<Record<string, string | number | boolean>>;

/** `POST /api/quotes` body — a product code plus that product's canonical inputs. */
export interface QuoteRequest {
  readonly product: ProductCode;
  readonly inputs: QuoteInputValues;
}

/** `POST /api/quotes` 201 body (§2.7). */
export interface QuoteResponse {
  readonly quote_id: string;
  readonly product: ProductCode;
  readonly rule_version: number;
  readonly sum_insured: MoneyString;
  readonly premium: MoneyString;
  readonly currency: string;
  readonly created_at: IsoDateTime;
}

/** `GET /api/quotes/{quote_id}` 200 body (§2.8) — the stored quote with its inputs. */
export interface StoredQuote extends QuoteResponse {
  readonly inputs: QuoteInputs;
  readonly actor_id: string;
}

/** Widget used for one risk input; `checkbox` carries booleans, `select` a closed code list. */
export type QuoteFieldKind = 'money' | 'integer' | 'checkbox' | 'select';

export interface QuoteFieldOption {
  readonly value: string;
  readonly label: string;
}

/** Declarative descriptor of a single risk input; the form renders these, never hardcoded JSX. */
export interface QuoteFieldSpec {
  /** Wire name sent inside `inputs` and echoed by 422 `details[].field`. */
  readonly name: string;
  readonly label: string;
  readonly kind: QuoteFieldKind;
  readonly hint?: string;
  readonly min?: number;
  readonly max?: number;
  readonly options?: readonly QuoteFieldOption[];
}

/** Raw form state: every value is held as a string ('true'/'false' for checkboxes). */
export type QuoteFormValues = Readonly<Record<string, string>>;

/** A 422 `details` entry rendered inline next to its input. */
export interface QuoteFieldIssue {
  readonly field: string;
  readonly code: string;
}
