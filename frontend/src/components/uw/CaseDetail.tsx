/**
 * One underwriting case: masked applicant data, reason codes, audit trail and — while the case is
 * MANUAL_REVIEW — the decision form (AC-14).
 *
 * Reason codes are checkboxes drawn from the case's own rule version; `reason_codes` is required by
 * the API, so an empty selection comes back as a 422 shown next to the buttons.
 */
import { useState } from 'react';
import { AuditTrail } from './AuditTrail';
import { ReasonCodeList } from './ReasonCodeList';
import { StatusBadge } from '../StatusBadge';
import type {
  ApplicationDetail,
  AuditResponse,
  UnderwriterDecision,
} from '../../types/applications';
import './uw.css';

export interface CaseDetailProps {
  readonly detail: ApplicationDetail | null;
  readonly loading: boolean;
  readonly audit: AuditResponse | null;
  readonly auditLoading: boolean;
  readonly reasonCodes: Readonly<Record<string, string>>;
  readonly busy: boolean;
  readonly error: string | null;
  readonly onDecide: (decision: UnderwriterDecision, reasonCodes: readonly string[], comment: string) => void;
}

export function CaseDetail({
  detail,
  loading,
  audit,
  auditLoading,
  reasonCodes,
  busy,
  error,
  onDecide,
}: CaseDetailProps): JSX.Element {
  const [selected, setSelected] = useState<readonly string[]>([]);
  const [comment, setComment] = useState('');

  if (loading) {
    return (
      <p className="empty" data-testid="case-loading">
        Loading the case…
      </p>
    );
  }
  if (detail === null) {
    return (
      <p className="empty" data-testid="case-empty">
        Select a case from the queue.
      </p>
    );
  }

  const toggle = (code: string): void => {
    setSelected((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  };

  return (
    <div data-testid="case-detail">
      <div className="big-status">
        <StatusBadge status={detail.status} />
        <span className="small muted">Rule version v{detail.rule_version}</span>
      </div>
      <dl className="kv">
        <dt>Application id</dt>
        <dd>
          <code className="mono">{detail.application_id}</code>
        </dd>
        <dt>Applicant</dt>
        <dd>{detail.kyc.full_name}</dd>
        <dt>Aadhaar</dt>
        <dd className="mono" data-testid="case-aadhaar">
          {detail.kyc.aadhaar_masked}
        </dd>
        <dt>PAN</dt>
        <dd className="mono" data-testid="case-pan">
          {detail.kyc.pan_masked}
        </dd>
        <dt>Product</dt>
        <dd>{detail.product}</dd>
        <dt>Address</dt>
        <dd className="small">{detail.kyc.address}</dd>
      </dl>

      <h3>Reason codes</h3>
      <ReasonCodeList
        codes={detail.reason_codes}
        reasons={detail.reasons}
        descriptions={reasonCodes}
        testId="case-reason-codes"
      />

      <h3>Audit trail</h3>
      <AuditTrail audit={audit} loading={auditLoading} />

      {detail.status === 'MANUAL_REVIEW' ? (
        <form className="decision-box" noValidate onSubmit={(event) => event.preventDefault()}>
          <h3>Decision</h3>
          <fieldset className="field" aria-describedby="decision-codes-hint">
            <legend>Reason codes</legend>
            <span className="hint" id="decision-codes-hint">
              From the case’s rule version (v{detail.rule_version})
            </span>
            {Object.entries(reasonCodes).map(([code, description]) => (
              <label className="choice" key={code} htmlFor={`reason-${code}`}>
                <input
                  id={`reason-${code}`}
                  data-testid={`reason-${code}`}
                  type="checkbox"
                  disabled={busy}
                  checked={selected.includes(code)}
                  onChange={() => toggle(code)}
                />
                <span>
                  <code>{code}</code> {description}
                </span>
              </label>
            ))}
          </fieldset>
          <div className="field">
            <label htmlFor="decision-comment">Comment</label>
            <textarea
              id="decision-comment"
              data-testid="decision-comment"
              rows={3}
              disabled={busy}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
          {error === null ? null : (
            <div className="alert alert-error" role="alert" data-testid="decision-error">
              <p>{error}</p>
            </div>
          )}
          <div className="actions">
            <button
              type="button"
              className="btn btn-primary"
              data-testid="decision-approve"
              disabled={busy}
              onClick={() => onDecide('APPROVE', selected, comment.trim())}
            >
              Approve
            </button>
            <button
              type="button"
              className="btn btn-danger"
              data-testid="decision-decline"
              disabled={busy}
              onClick={() => onDecide('DECLINE', selected, comment.trim())}
            >
              Decline
            </button>
          </div>
        </form>
      ) : (
        <div className="alert alert-info" role="status" data-testid="case-closed">
          <p>Decision recorded — this case has left the manual review queue.</p>
        </div>
      )}
    </div>
  );
}
