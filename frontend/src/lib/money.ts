/**
 * Display-only formatting of decimal strings from the API.
 *
 * The UI never does money arithmetic (NFR-01): `Number()` is used solely to hand the value to
 * `Intl.NumberFormat`, and the original string is returned when it is not a finite number.
 */
const FORMATTERS = new Map<string, Intl.NumberFormat>();

function formatterFor(currency: string): Intl.NumberFormat {
  const cached = FORMATTERS.get(currency);
  if (cached !== undefined) return cached;
  const created = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  FORMATTERS.set(currency, created);
  return created;
}

/** Formats a decimal string such as `"2500.00"` as `"₹2,500.00"`. */
export function formatMoney(amount: string, currency = 'INR'): string {
  const value = Number(amount);
  if (amount.trim() === '' || !Number.isFinite(value)) return amount;
  return formatterFor(currency).format(value);
}
