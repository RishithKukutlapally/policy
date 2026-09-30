/**
 * KYC stub inputs for the Apply screen (AC-03, NFR-03).
 *
 * Aadhaar and PAN are typed into `type="password"` inputs and, as soon as focus leaves, the visible
 * value becomes the mask (`XXXX-XXXX-0001` / `XXXXX0001X`): the raw digits live only in the parent's
 * state until the request is sent, and nothing is ever logged.
 */
import { useState } from 'react';
import { maskAadhaar, maskPan } from '../../lib/maskPii';
import type { KycFormValues } from '../../types/applications';
import './uw.css';

export interface KycFormProps {
  readonly values: KycFormValues;
  /** 422 `details` keyed by wire field, e.g. `kyc.pan`. */
  readonly issues: Readonly<Record<string, string>>;
  readonly disabled: boolean;
  readonly onChange: (field: keyof KycFormValues, value: string) => void;
}

const MESSAGES: Readonly<Record<string, string>> = {
  REQUIRED: 'This field is required.',
  INVALID_FORMAT: 'Check the format and try again.',
  OUT_OF_RANGE: 'Value is outside the range allowed by the active rule version.',
};

function FieldError({ field, code }: { field: string; code: string | undefined }): JSX.Element | null {
  if (code === undefined) return null;
  return (
    <p className="field-error" id={`kyc-${field}-error`} data-testid={`field-error-kyc.${field}`}>
      {code} — {MESSAGES[code] ?? 'Correct this field and try again.'}
    </p>
  );
}

interface SecretFieldProps {
  readonly name: 'aadhaar' | 'pan';
  readonly label: string;
  readonly hint: string;
  readonly value: string;
  readonly mask: (raw: string) => string;
  readonly issue: string | undefined;
  readonly disabled: boolean;
  readonly onChange: (field: keyof KycFormValues, value: string) => void;
}

function SecretField({
  name,
  label,
  hint,
  value,
  mask,
  issue,
  disabled,
  onChange,
}: SecretFieldProps): JSX.Element {
  const [focused, setFocused] = useState(false);
  const describedBy = [`kyc-${name}-hint`, issue === undefined ? null : `kyc-${name}-error`]
    .filter((id): id is string => id !== null)
    .join(' ');
  return (
    <div className="field">
      <label htmlFor={`kyc-${name}`}>{label}</label>
      <span className="hint" id={`kyc-${name}-hint`}>
        {hint}
      </span>
      <input
        id={`kyc-${name}`}
        data-testid={`kyc-${name}`}
        type={focused ? 'password' : 'text'}
        autoComplete="off"
        inputMode={name === 'aadhaar' ? 'numeric' : 'text'}
        disabled={disabled}
        aria-invalid={issue === undefined ? undefined : true}
        aria-describedby={describedBy}
        value={focused ? value : mask(value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(event) => onChange(name, event.target.value)}
      />
      <FieldError field={name} code={issue} />
    </div>
  );
}

export function KycForm({ values, issues, disabled, onChange }: KycFormProps): JSX.Element {
  return (
    <div className="form-grid">
      <div className="field full">
        <label htmlFor="kyc-full_name">Full name</label>
        <input
          id="kyc-full_name"
          data-testid="kyc-full_name"
          type="text"
          autoComplete="off"
          disabled={disabled}
          aria-invalid={issues['kyc.full_name'] === undefined ? undefined : true}
          value={values.full_name}
          onChange={(event) => onChange('full_name', event.target.value)}
        />
        <FieldError field="full_name" code={issues['kyc.full_name']} />
      </div>
      <div className="field">
        <label htmlFor="kyc-date_of_birth">Date of birth</label>
        <input
          id="kyc-date_of_birth"
          data-testid="kyc-date_of_birth"
          type="date"
          disabled={disabled}
          aria-invalid={issues['kyc.date_of_birth'] === undefined ? undefined : true}
          value={values.date_of_birth}
          onChange={(event) => onChange('date_of_birth', event.target.value)}
        />
        <FieldError field="date_of_birth" code={issues['kyc.date_of_birth']} />
      </div>
      <SecretField
        name="aadhaar"
        label="Aadhaar"
        hint="12 digits · hidden while typing, shown masked afterwards"
        value={values.aadhaar}
        mask={maskAadhaar}
        issue={issues['kyc.aadhaar']}
        disabled={disabled}
        onChange={onChange}
      />
      <SecretField
        name="pan"
        label="PAN"
        hint="Format AAAAA9999A · hidden while typing"
        value={values.pan}
        mask={maskPan}
        issue={issues['kyc.pan']}
        disabled={disabled}
        onChange={onChange}
      />
      <div className="field full">
        <label htmlFor="kyc-address">Address</label>
        <textarea
          id="kyc-address"
          data-testid="kyc-address"
          rows={2}
          disabled={disabled}
          aria-invalid={issues['kyc.address'] === undefined ? undefined : true}
          value={values.address}
          onChange={(event) => onChange('address', event.target.value)}
        />
        <FieldError field="address" code={issues['kyc.address']} />
      </div>
    </div>
  );
}
