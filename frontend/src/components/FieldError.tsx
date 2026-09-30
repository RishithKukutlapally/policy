/**
 * A 422 `details[].code` rendered next to the field it names.
 *
 * The code is always shown verbatim alongside its explanation so the message stays traceable to the
 * contract (docs/conventions.md → error codes) rather than being paraphrased away.
 */
const MESSAGES: Readonly<Record<string, string>> = {
  REQUIRED: 'This field is required.',
  INVALID_FORMAT: 'Check the format and try again.',
  MONEY_MUST_BE_STRING: 'Enter an amount such as 600000.00.',
  OUT_OF_RANGE: 'Value is outside the range allowed by the policy’s rule version.',
  UNCHANGED: 'This is already the current value.',
  NOT_ALLOWED: 'The policy’s rule version does not allow this endorsement type.',
  UNKNOWN_CODE: 'Choose one of the listed values.',
  SHARE_EXCEEDS_100: 'The nominee shares would add up to more than 100%.',
  OUTSIDE_TERM: 'Choose a date inside the policy term.',
  AMOUNT_MISMATCH: 'Pay exactly the quoted renewal premium.',
  NOT_RENEWABLE: 'This policy can no longer be renewed.',
  RENEWAL_PREMIUM_UNPAID: 'Pay the renewal premium first.',
};

export function fieldErrorText(code: string): string {
  return `${code} — ${MESSAGES[code] ?? 'Correct this field and try again.'}`;
}

export interface FieldErrorProps {
  /** Form field name, used for both the element id and the Playwright hook. */
  readonly name: string;
  /** The 422 code, or `null` when the field is valid. */
  readonly code: string | null;
}

export function fieldErrorId(name: string): string {
  return `${name}-error`;
}

export function FieldError({ name, code }: FieldErrorProps): JSX.Element | null {
  if (code === null) return null;
  return (
    <p className="field-error" id={fieldErrorId(name)} data-testid={`field-error-${name}`}>
      {fieldErrorText(code)}
    </p>
  );
}
