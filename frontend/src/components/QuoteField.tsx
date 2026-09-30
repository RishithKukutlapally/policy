/**
 * One risk input rendered from a `QuoteFieldSpec` (story E3-S3).
 *
 * Every control is labelled and keyboard reachable; a 422 `details[].field` for this input turns it
 * into `aria-invalid` and links the message through `aria-describedby` (AC-12).
 */
import type { QuoteFieldSpec } from '../types/quotes';

export interface QuoteFieldProps {
  readonly spec: QuoteFieldSpec;
  readonly value: string;
  /** 422 code for this field, or `null` when it is valid. */
  readonly errorCode: string | null;
  readonly disabled: boolean;
  readonly onChange: (name: string, value: string) => void;
}

const MESSAGES: Readonly<Record<string, string>> = {
  OUT_OF_RANGE: 'Value is outside the range allowed by the active rule version.',
  INVALID_FORMAT: 'Enter an amount such as 500000.00.',
  REQUIRED: 'This field is required.',
  UNKNOWN_CODE: 'Choose one of the listed values.',
  MONEY_MUST_BE_STRING: 'Enter an amount such as 500000.00.',
};

function describe(code: string): string {
  return `${code} — ${MESSAGES[code] ?? 'Correct this field and try again.'}`;
}

export function QuoteField({
  spec,
  value,
  errorCode,
  disabled,
  onChange,
}: QuoteFieldProps): JSX.Element {
  const inputId = `quote-${spec.name}`;
  const hintId = spec.hint === undefined ? null : `${inputId}-hint`;
  const errorId = errorCode === null ? null : `${inputId}-error`;
  const describedBy = [hintId, errorId].filter((id): id is string => id !== null).join(' ');
  const testId = spec.name === 'sum_insured' ? 'quote-sum-insured' : `input-${spec.name}`;

  const shared = {
    id: inputId,
    name: spec.name,
    disabled,
    'data-testid': testId,
    'aria-invalid': errorCode === null ? undefined : (true as const),
    'aria-describedby': describedBy === '' ? undefined : describedBy,
  };

  const error =
    errorCode === null ? null : (
      <p className="field-error" id={errorId ?? undefined} data-testid={`field-error-${spec.name}`}>
        {describe(errorCode)}
      </p>
    );

  if (spec.kind === 'checkbox') {
    return (
      <div className="field field--checkbox">
        <label className="choice" htmlFor={inputId}>
          <input
            {...shared}
            type="checkbox"
            checked={value === 'true'}
            onChange={(event) => onChange(spec.name, String(event.target.checked))}
          />
          <span>{spec.label}</span>
        </label>
        {error}
      </div>
    );
  }

  return (
    <div className={spec.name === 'sum_insured' ? 'field field--full' : 'field'}>
      <label htmlFor={inputId}>{spec.label}</label>
      {spec.hint !== undefined ? (
        <span className="hint" id={hintId ?? undefined}>
          {spec.hint}
        </span>
      ) : null}
      {spec.kind === 'select' ? (
        <select
          {...shared}
          className="quote-select"
          value={value}
          onChange={(event) => onChange(spec.name, event.target.value)}
        >
          {(spec.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          {...shared}
          className="quote-input"
          type={spec.kind === 'integer' ? 'number' : 'text'}
          inputMode={spec.kind === 'integer' ? 'numeric' : 'decimal'}
          min={spec.min}
          max={spec.max}
          value={value}
          onChange={(event) => onChange(spec.name, event.target.value)}
        />
      )}
      {error}
    </div>
  );
}
