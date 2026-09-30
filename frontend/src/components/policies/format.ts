/**
 * Display-only helpers for the policy views. No money arithmetic happens here: the sign is read from
 * the decimal string the API sent and the digits are handed to `Intl.NumberFormat` untouched (NFR-01).
 */
import { formatMoney } from '../../lib/money';
import type { EndorsementSnapshot } from '../../types/policies';

/** `"1200.00"` → `"+₹1,200.00"`, `"-1200.00"` → `"−₹1,200.00"`. */
export function formatSignedMoney(amount: string, currency = 'INR'): string {
  const negative = amount.trim().startsWith('-');
  const magnitude = amount.trim().replace(/^[+-]/, '');
  return `${negative ? '−' : '+'}${formatMoney(magnitude, currency)}`;
}

/** `"2026-06-10T09:30:00Z"` → `"2026-06-10 09:30"`. */
export function formatInstant(value: string): string {
  return value.replace('T', ' ').slice(0, 16);
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/**
 * One-line summary of an endorsement `before` / `after` snapshot. Snapshots only ever carry the
 * changed policy attributes (address, nominee, sum insured) — never a KYC identifier.
 */
export function describeSnapshot(snapshot: EndorsementSnapshot, currency = 'INR'): string {
  const address = asString(snapshot.address);
  if (address !== null) return address;

  const sumInsured = asString(snapshot.sum_insured);
  if (sumInsured !== null) return `Sum insured ${formatMoney(sumInsured, currency)}`;

  const nomineeName = asString(snapshot.nominee_name);
  if (nomineeName !== null) {
    const relationship = asString(snapshot.relationship);
    return relationship === null ? nomineeName : `${nomineeName} (${relationship})`;
  }

  if (Array.isArray(snapshot.nominees)) {
    const count = snapshot.nominees.length;
    return count === 0 ? 'No nominees' : `${count} nominee(s)`;
  }
  return '—';
}
