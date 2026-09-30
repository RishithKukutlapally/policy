/**
 * The per-type input group of the Endorse form (story E6-S3, contract §2.19).
 *
 * Only the fields the chosen `type` actually sends are mounted, so the request body can never carry a
 * stale value from another type. Every control is labelled, hinted and links its 422 code through
 * `aria-describedby` (AC-16, AC-24).
 */
import { FieldError, fieldErrorId } from '../FieldError';
import { formatMoney } from '../../lib/money';
import { NOMINEE_RELATIONSHIPS } from '../../types/endorsements';
import type { EndorsementType, PolicyDetail } from '../../types/policies';

/** Draft values of every field the three endorsement types can send. */
export interface EndorsementDraft {
  readonly address: string;
  readonly nominee_name: string;
  readonly relationship: string;
  readonly share_percent: string;
  readonly new_sum_insured: string;
}

export const EMPTY_DRAFT: EndorsementDraft = {
  address: '',
  nominee_name: '',
  relationship: 'SPOUSE',
  share_percent: '100',
  new_sum_insured: '',
};

export interface EndorsementFieldsProps {
  readonly type: EndorsementType;
  readonly draft: EndorsementDraft;
  readonly policy: PolicyDetail;
  /** 422 `details[].field` → code for the currently displayed fields. */
  readonly fieldErrors: Readonly<Record<string, string>>;
  readonly disabled: boolean;
  readonly onChange: (name: keyof EndorsementDraft, value: string) => void;
}

function describedBy(name: string, hint: boolean, error: boolean): string | undefined {
  const ids = [hint ? `${name}-hint` : null, error ? fieldErrorId(name) : null].filter(
    (id): id is string => id !== null,
  );
  return ids.length === 0 ? undefined : ids.join(' ');
}

export function EndorsementFields({
  type,
  draft,
  policy,
  fieldErrors,
  disabled,
  onChange,
}: EndorsementFieldsProps): JSX.Element {
  const errorOf = (name: string): string | null => fieldErrors[name] ?? null;

  if (type === 'CHANGE_ADDRESS') {
    const code = errorOf('address');
    return (
      <div className="field">
        <label htmlFor="address">New address</label>
        <span className="hint" id="address-hint">
          Current: {policy.insured.address} · max 300 characters
        </span>
        <textarea
          id="address"
          name="address"
          className="lc-textarea"
          rows={2}
          maxLength={300}
          value={draft.address}
          disabled={disabled}
          data-testid="input-address"
          aria-invalid={code === null ? undefined : true}
          aria-describedby={describedBy('address', true, code !== null)}
          onChange={(event) => onChange('address', event.target.value)}
        />
        <FieldError name="address" code={code} />
      </div>
    );
  }

  if (type === 'ADD_NOMINEE') {
    const nameCode = errorOf('nominee_name');
    const shareCode = errorOf('share_percent');
    return (
      <div className="form-grid">
        <div className="field field--full">
          <label htmlFor="nominee_name">Nominee name</label>
          <input
            type="text"
            id="nominee_name"
            name="nominee_name"
            className="lc-input"
            value={draft.nominee_name}
            disabled={disabled}
            data-testid="input-nominee_name"
            aria-invalid={nameCode === null ? undefined : true}
            aria-describedby={describedBy('nominee_name', false, nameCode !== null)}
            onChange={(event) => onChange('nominee_name', event.target.value)}
          />
          <FieldError name="nominee_name" code={nameCode} />
        </div>
        <div className="field">
          <label htmlFor="relationship">Relationship</label>
          <select
            id="relationship"
            name="relationship"
            className="lc-select"
            value={draft.relationship}
            disabled={disabled}
            data-testid="input-relationship"
            onChange={(event) => onChange('relationship', event.target.value)}
          >
            {NOMINEE_RELATIONSHIPS.map((value) => (
              <option key={value} value={value}>
                {value.charAt(0) + value.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
          <FieldError name="relationship" code={errorOf('relationship')} />
        </div>
        <div className="field">
          <label htmlFor="share_percent">Share %</label>
          <span className="hint" id="share_percent-hint">
            1–100 · existing nominees: {policy.insured.nominees.length}
          </span>
          <input
            type="text"
            inputMode="decimal"
            id="share_percent"
            name="share_percent"
            className="lc-input"
            value={draft.share_percent}
            disabled={disabled}
            data-testid="input-share_percent"
            aria-invalid={shareCode === null ? undefined : true}
            aria-describedby={describedBy('share_percent', true, shareCode !== null)}
            onChange={(event) => onChange('share_percent', event.target.value)}
          />
          <FieldError name="share_percent" code={shareCode} />
        </div>
      </div>
    );
  }

  const sumCode = errorOf('new_sum_insured');
  return (
    <div className="field">
      <label htmlFor="new_sum_insured">Sum insured</label>
      <span className="hint" id="new_sum_insured-hint">
        Current {formatMoney(policy.sum_insured, policy.currency)} · the range allowed by rule version v
        {policy.rule_version} is enforced by the server
      </span>
      <input
        type="text"
        inputMode="decimal"
        id="new_sum_insured"
        name="new_sum_insured"
        className="lc-input"
        value={draft.new_sum_insured}
        disabled={disabled}
        data-testid="input-new_sum_insured"
        aria-invalid={sumCode === null ? undefined : true}
        aria-describedby={describedBy('new_sum_insured', true, sumCode !== null)}
        onChange={(event) => onChange('new_sum_insured', event.target.value)}
      />
      <FieldError name="new_sum_insured" code={sumCode} />
    </div>
  );
}
