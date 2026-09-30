/**
 * Cancel — story E8-S3 (AC-08, AC-19, AC-10, AC-24), route `/policies/:policyNumber/cancel`.
 *
 * Changing the date re-reads `GET …/cancellation-preview?date=` (§2.23), which persists nothing, so the
 * refund breakdown can be explored freely before committing. `POST …/cancel` is only ever reached
 * through the explicit confirmation dialog (AC-19). A 422 on `date` / `cancellation_date` — notably
 * `OUTSIDE_TERM` — is attached to the date field; a 409 `INVALID_POLICY_STATE` (already cancelled,
 * lapsed or renewed) becomes a banner (AC-10).
 */
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { cancelPolicy, getCancellationPreview } from '../api/cancellations';
import { useRole } from '../app/RoleContext';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { FieldError, fieldErrorId } from '../components/FieldError';
import { NotAuthorised } from '../components/NotAuthorised';
import { CancelDone } from '../components/cancel/CancelDone';
import { PolicyFactsPanel } from '../components/lifecycle/PolicyFactsPanel';
import { PolicyNotFound } from '../components/lifecycle/PolicyNotFound';
import { usePolicyLoad } from '../components/lifecycle/usePolicyLoad';
import { RefundPreview, refundSentence } from '../components/policies/RefundPreview';
import { StatusBadge } from '../components/StatusBadge';
import { classifyError, issueText } from '../lib/apiIssues';
import { REASON_MAX_LENGTH } from '../types/cancellation';
import type { CancelResult, RefundBreakdown } from '../types/cancellation';
import '../components/lifecycle/lifecycle.css';
import './CancelPage.css';

/** The 422 field names §2.23 and §2.24 use for the date, both shown on the one date input. */
const DATE_FIELDS: readonly string[] = ['date', 'cancellation_date'];

export function CancelPage(): JSX.Element {
  const { policyNumber = '' } = useParams<{ policyNumber: string }>();
  const { api, role } = useRole();
  const mayCancel = role === 'CUSTOMER' || role === 'ADMIN';

  const { policy, loading, notFound, error: loadError } = usePolicyLoad(policyNumber, mayCancel);

  const [date, setDate] = useState('');
  const [reason, setReason] = useState('');
  const [refund, setRefund] = useState<RefundBreakdown | null>(null);
  const [dateCode, setDateCode] = useState<string | null>(null);
  const [reasonCode, setReasonCode] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<CancelResult | null>(null);

  const currency = policy?.currency ?? 'INR';

  const fail = useCallback((caught: unknown, fallback: string): void => {
    const issues = classifyError(caught, fallback);
    const code = DATE_FIELDS.map((field) => issues.fields[field]).find(
      (value): value is string => value !== undefined,
    );
    setDateCode(code ?? null);
    setReasonCode(issues.fields.reason ?? null);
    const inline = code !== undefined || issues.fields.reason !== undefined;
    // A field-level 422 is already shown inline; anything else needs the banner (409, 500, network).
    setBanner(inline ? null : issueText(issues));
  }, []);

  const onDateChange = useCallback(
    async (next: string): Promise<void> => {
      setDate(next);
      setRefund(null);
      setDateCode(null);
      setReasonCode(null);
      setBanner(null);
      if (next === '') return;
      setPreviewing(true);
      try {
        setRefund(await getCancellationPreview(api, policyNumber, next));
      } catch (caught) {
        fail(caught, 'The refund preview could not be loaded.');
      } finally {
        setPreviewing(false);
      }
    },
    [api, policyNumber, fail],
  );

  const onConfirm = useCallback(async (): Promise<void> => {
    setBusy(true);
    try {
      setDone(await cancelPolicy(api, policyNumber, { cancellation_date: date, reason }));
      setDialogOpen(false);
    } catch (caught) {
      setDialogOpen(false);
      fail(caught, 'The policy could not be cancelled.');
    } finally {
      setBusy(false);
    }
  }, [api, policyNumber, date, reason, fail]);

  if (!mayCancel) return <NotAuthorised allowed={['Customer', 'Admin']} />;
  if (loading) {
    return (
      <p className="muted" role="status">
        Loading policy…
      </p>
    );
  }
  if (notFound) return <PolicyNotFound policyNumber={policyNumber} />;
  if (policy === null) {
    return (
      <section className="panel">
        <h1>Cancel policy</h1>
        <div className="alert alert-error" role="alert" data-testid="cancel-error">
          <p>{loadError ?? 'The policy could not be loaded.'}</p>
        </div>
      </section>
    );
  }

  if (done !== null) return <CancelDone result={done} currency={currency} />;

  // `reason` is validated by the server (§2.24 `REQUIRED`), so only an unusable date blocks the dialog.
  const canConfirm = date !== '' && dateCode === null;

  return (
    <div className="cancel-page">
      <p>
        <Link to={`/policies/${policy.policy_number}`}>← Back to Policy Detail</Link>
      </p>
      <div className="page-head">
        <div>
          <h1>
            Cancel {policy.policy_number} <StatusBadge status={policy.status} />
          </h1>
          <p className="route">
            Term {policy.effective_date} – {policy.expiry_date}
          </p>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel" aria-labelledby="c-h">
          <h2 id="c-h">Cancellation</h2>
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              setDialogOpen(true);
            }}
          >
            <div className="form-grid">
              <div className="field">
                <label htmlFor="cancellation_date">Cancellation date</label>
                <span className="hint" id="cancellation_date-hint">
                  Within the policy term {policy.effective_date} – {policy.expiry_date}
                </span>
                <input
                  type="date"
                  id="cancellation_date"
                  name="cancellation_date"
                  className="lc-input"
                  value={date}
                  min={policy.effective_date}
                  max={policy.expiry_date}
                  data-testid="cancellation-date"
                  aria-invalid={dateCode === null ? undefined : true}
                  aria-describedby={
                    dateCode === null
                      ? 'cancellation_date-hint'
                      : `cancellation_date-hint ${fieldErrorId('cancellation_date')}`
                  }
                  onChange={(event) => void onDateChange(event.target.value)}
                />
                <FieldError name="cancellation_date" code={dateCode} />
              </div>
              <div className="field">
                <label htmlFor="cancellation_reason">Reason</label>
                <span className="hint" id="cancellation_reason-hint">
                  Free text, up to {REASON_MAX_LENGTH} characters
                </span>
                <input
                  type="text"
                  id="cancellation_reason"
                  name="reason"
                  className="lc-input"
                  maxLength={REASON_MAX_LENGTH}
                  value={reason}
                  data-testid="cancellation-reason"
                  aria-invalid={reasonCode === null ? undefined : true}
                  aria-describedby={
                    reasonCode === null
                      ? 'cancellation_reason-hint'
                      : `cancellation_reason-hint ${fieldErrorId('reason')}`
                  }
                  onChange={(event) => setReason(event.target.value)}
                />
                <FieldError name="reason" code={reasonCode} />
              </div>
            </div>

            <section
              className="panel cancel-preview"
              aria-labelledby="pv-h"
              aria-live="polite"
              data-testid="refund-preview"
            >
              <h3 id="pv-h">Refund preview</h3>
              {previewing ? (
                <p className="lc-loading" role="status">
                  Updating preview…
                </p>
              ) : refund === null ? (
                <p className="small muted">
                  Choose a cancellation date to see the refund the server calculates.
                </p>
              ) : (
                <RefundPreview refund={refund} currency={currency} />
              )}
            </section>

            {banner === null ? null : (
              <div className="alert alert-error" role="alert" data-testid="cancel-error">
                <p>{banner}</p>
              </div>
            )}

            <div className="actions">
              <button
                type="submit"
                className="btn btn-danger"
                disabled={!canConfirm || busy}
                data-testid="confirm-cancellation"
              >
                Confirm cancellation
              </button>
              <Link className="btn" to={`/policies/${policy.policy_number}`}>
                Keep my policy
              </Link>
            </div>
          </form>
        </section>

        <PolicyFactsPanel
          policy={policy}
          footnote="The refund type, the pro-rata share and the admin fee all come from the policy's rule version — this screen only displays them."
        />
      </div>

      {dialogOpen ? (
        <ConfirmDialog
          title={`Cancel ${policy.policy_number}?`}
          confirmLabel="Yes, cancel policy"
          cancelLabel="Keep policy"
          confirmTestId="dialog-confirm"
          cancelTestId="dialog-keep"
          busy={busy}
          busyLabel="Cancelling…"
          onConfirm={() => void onConfirm()}
          onCancel={() => setDialogOpen(false)}
        >
          <p>
            Cancellation date <strong className="num">{date}</strong>.{' '}
            {refund === null
              ? 'The refund is calculated by the system on confirmation.'
              : `${refundSentence(refund, currency)}.`}
          </p>
          <p className="small">This cannot be undone. Cover ends on the cancellation date.</p>
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
