/**
 * Rule-file JSON editor for creating a DRAFT (POST §2.4) or replacing the open one (PUT §2.5).
 *
 * 422 `details` entries are rendered inline, one per field path (e.g. `premium.base_rate`).
 * The editor never logs its contents.
 */
import type { DraftEditorMode, FieldIssue, ProductCode } from '../types/catalog';

export interface RuleFileEditorProps {
  readonly product: ProductCode;
  readonly mode: DraftEditorMode;
  readonly value: string;
  readonly busy: boolean;
  readonly issues: readonly FieldIssue[];
  readonly onChange: (next: string) => void;
  readonly onSubmit: () => void;
  readonly onCancelEdit: () => void;
}

const HINT_ID = 'rule-json-hint';
const ERRORS_ID = 'rule-json-errors';

export function RuleFileEditor({
  product,
  mode,
  value,
  busy,
  issues,
  onChange,
  onSubmit,
  onCancelEdit,
}: RuleFileEditorProps): JSX.Element {
  const replacing = mode.kind === 'replace';
  const invalid = issues.length > 0;
  const describedBy = invalid ? `${HINT_ID} ${ERRORS_ID}` : HINT_ID;

  return (
    <section className="panel" aria-labelledby="draft-h">
      <h2 id="draft-h">
        {replacing ? `Replace draft v${mode.version}` : 'New draft'} — {product}
      </h2>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="field">
          <label htmlFor="rule-json">Rule-set JSON</label>
          <span className="hint" id={HINT_ID}>
            Paste the full rule file. Money and rates are JSON strings (e.g. <code>&quot;base_rate&quot;: &quot;0.0320&quot;</code>).
          </span>
          <textarea
            id="rule-json"
            className="code"
            spellCheck={false}
            rows={14}
            value={value}
            aria-describedby={describedBy}
            aria-invalid={invalid ? 'true' : undefined}
            data-testid="rule-json"
            onChange={(event) => onChange(event.target.value)}
          />
        </div>
        {invalid ? (
          <div className="alert alert-error" role="alert" id={ERRORS_ID} data-testid="validation-errors">
            <p>
              <strong className="code">422 VALIDATION_ERROR</strong> — the rule file failed validation.
            </p>
            <ul>
              {issues.map((issue) => (
                <li key={`${issue.field}:${issue.code}`} data-testid={`field-error-${issue.field}`}>
                  <code>{issue.field}</code> — <code>{issue.code}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="actions">
          <button type="submit" className="btn btn-primary" disabled={busy} data-testid="create-draft">
            {replacing ? 'Save draft' : 'Create draft'}
          </button>
          {replacing ? (
            <button type="button" className="btn" onClick={onCancelEdit} data-testid="cancel-edit">
              Cancel editing
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
