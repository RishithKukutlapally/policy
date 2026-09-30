/**
 * Client-side masking of the two KYC identifiers (NFR-03).
 *
 * The server is the authority — its responses already carry `aadhaar_masked` / `pan_masked`. These
 * helpers exist only so the Apply form can show what the user typed without ever painting the raw
 * value on screen; the masks match docs/conventions.md (`XXXX-XXXX-0001`, `XXXXX0001X`).
 */

/** `999900000001` → `XXXX-XXXX-0001`; shorter input keeps the digits it has. */
export function maskAadhaar(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  if (digits === '') return '';
  return `XXXX-XXXX-${digits.slice(-4)}`;
}

/** `AAAAA0001A` → `XXXXX0001X`; shorter input is masked character by character. */
export function maskPan(raw: string): string {
  const value = raw.trim();
  if (value === '') return '';
  if (value.length < 10) return 'X'.repeat(value.length);
  return `XXXXX${value.slice(5, 9)}X`;
}

/** First 8 characters of a UUID — the queue's compact application reference (mockup E4-S5). */
export function shortId(applicationId: string): string {
  return applicationId.slice(0, 8);
}
