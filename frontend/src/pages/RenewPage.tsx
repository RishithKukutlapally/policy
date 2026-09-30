/**
 * Renew — story E7-S4 (AC-07, AC-17), route `/policies/:policyNumber/renew`, CUSTOMER (owner) only.
 *
 * Renewal is owner-scoped: §2.21 returns 403 for ADMIN and UNDERWRITER, so the screen refuses those
 * roles before issuing a request. "Pay premium" posts the quote's `renewal_premium` back verbatim —
 * the UI never re-derives or re-rounds the amount (NFR-01, §2.22 `AMOUNT_MISMATCH`). "Renew" then
 * reveals the successor policy number and a link to its new term (AC-07).
 */
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { payPremium, renewPolicy } from '../api/renewal';
import { useRole } from '../app/RoleContext';
import { NotAuthorised } from '../components/NotAuthorised';
import { PolicyNotFound } from '../components/lifecycle/PolicyNotFound';
import { useRenewalLoad } from '../components/renew/useRenewalLoad';
import { StatusBadge } from '../components/StatusBadge';
import { classifyError, issueText } from '../lib/apiIssues';
import { formatMoney } from '../lib/money';
import { PRODUCT_NAMES } from '../types/policies';
import type { PolicySummary } from '../types/policies';
import '../components/lifecycle/lifecycle.css';
import './RenewPage.css';

export function RenewPage(): JSX.Element {
  const { policyNumber = '' } = useParams<{ policyNumber: string }>();
  const { api, role } = useRole();
  const mayRenew = role === 'CUSTOMER';

  const { policy, quote, loading, notFound, error: loadError } = useRenewalLoad(
    policyNumber,
    mayRenew,
  );

  const [paid, setPaid] = useState(false);
  const [successor, setSuccessor] = useState<PolicySummary | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fail = useCallback((caught: unknown, fallback: string): void => {
    setActionError(issueText(classifyError(caught, fallback)));
    setNotice(null);
  }, []);

  const onPay = useCallback(
    async (amount: string): Promise<void> => {
      setActionError(null);
      setNotice(null);
      setBusy(true);
      try {
        const receipt = await payPremium(api, policyNumber, amount);
        setPaid(true);
        setNotice(
          `Renewal premium ${formatMoney(receipt.amount, quote?.currency ?? 'INR')} received for the term starting ${receipt.due_date}.`,
        );
      } catch (caught) {
        fail(caught, 'The payment could not be recorded.');
      } finally {
        setBusy(false);
      }
    },
    [api, policyNumber, quote, fail],
  );

  const onRenew = useCallback(async (): Promise<void> => {
    setActionError(null);
    setNotice(null);
    setBusy(true);
    try {
      setSuccessor(await renewPolicy(api, policyNumber));
    } catch (caught) {
      fail(caught, 'The policy could not be renewed.');
    } finally {
      setBusy(false);
    }
  }, [api, policyNumber, fail]);

  if (!mayRenew) return <NotAuthorised allowed={['Customer']} />;
  if (loading) {
    return (
      <p className="muted" role="status">
        Loading renewal quote…
      </p>
    );
  }
  if (notFound) return <PolicyNotFound policyNumber={policyNumber} />;

  // A terminal policy (409 INVALID_POLICY_STATE) or a transport failure has no quote to show.
  if (quote === null) {
    return (
      <section className="panel">
        <h1>Renew {policyNumber}</h1>
        <div className="alert alert-error" role="alert" data-testid="renewal-error">
          <p>{loadError ?? 'The renewal quote could not be loaded.'}</p>
        </div>
        <p>
          <Link to="/policies">Back to My Policies</Link>
        </p>
      </section>
    );
  }

  const currency = quote.currency;
  const premium = quote.renewal_premium;
  const isPaid = paid || quote.paid;
  const renewed = successor !== null;

  return (
    <div className="renew-page">
      <p>
        <Link to={`/policies/${policyNumber}`}>← Back to Policy Detail</Link>
      </p>
      <div className="page-head">
        <div>
          <h1>
            Renew {policyNumber} <StatusBadge status={renewed ? 'RENEWED' : (policy?.status ?? 'ACTIVE')} />
          </h1>
          <p className="route">Renewal window opens {quote.renewal_window_opens}</p>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel" aria-labelledby="rq-h">
          <h2 id="rq-h">Renewal quote</h2>
          <p className="muted small" style={{ margin: 0 }}>
            Renewal premium (12 months)
          </p>
          <p className="lc-figure" data-testid="renewal-premium">
            {premium === null ? 'Not renewable' : formatMoney(premium, currency)}
          </p>
          <dl className="kv">
            <dt>Rule version</dt>
            <dd>v{quote.rule_version}</dd>
            <dt>Due date</dt>
            <dd className="num" data-testid="due-date">
              {quote.due_date}
            </dd>
            <dt>Grace period ends</dt>
            <dd className="num" data-testid="grace-end-date">
              {quote.grace_end_date}
            </dd>
            <dt>Renewal window</dt>
            <dd className="num">opens {quote.renewal_window_opens}</dd>
            <dt>Payment</dt>
            <dd>
              <StatusBadge status={isPaid ? 'PAID' : 'UNPAID'} testId="payment-status" />
            </dd>
          </dl>

          {notice === null ? null : (
            <div className="alert alert-ok" role="status">
              <p>{notice}</p>
            </div>
          )}
          {actionError === null ? null : (
            <div className="alert alert-error" role="alert" data-testid="renewal-error">
              <p>{actionError}</p>
            </div>
          )}

          <div className="actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || isPaid || premium === null || renewed}
              data-testid="pay-premium"
              onClick={() => void onPay(premium ?? '0.00')}
            >
              {isPaid ? 'Premium paid' : 'Pay premium'}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy || renewed}
              data-testid="renew-now"
              onClick={() => void onRenew()}
            >
              Renew now
            </button>
          </div>
        </section>

        <section className="panel" aria-labelledby="cur-h">
          <h2 id="cur-h">Current term</h2>
          {policy === null ? (
            <p className="small muted">The current term could not be loaded.</p>
          ) : (
            <dl className="kv">
              <dt>Product</dt>
              <dd>
                {PRODUCT_NAMES[policy.product]} · rule v{policy.rule_version}
              </dd>
              <dt>Sum insured</dt>
              <dd className="num">{formatMoney(policy.sum_insured, policy.currency)}</dd>
              <dt>Premium</dt>
              <dd className="num">{formatMoney(policy.premium, policy.currency)}</dd>
              <dt>Term</dt>
              <dd className="num">
                {policy.effective_date} – {policy.expiry_date}
              </dd>
            </dl>
          )}
          <p className="small muted">
            Pay before the due date and the policy renews automatically at end of day, or choose
            &ldquo;Renew now&rdquo; once paid. If it stays unpaid, cover continues until the grace period
            ends and the policy then lapses.
          </p>

          {successor === null ? null : (
            <div aria-live="polite" data-testid="successor">
              <h3>New term policy</h3>
              <dl className="kv">
                <dt>Policy number</dt>
                <dd>
                  <Link to={`/policies/${successor.policy_number}`} data-testid="successor-link">
                    {successor.policy_number}
                  </Link>
                </dd>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={successor.status} testId="successor-status" />
                </dd>
                <dt>Term</dt>
                <dd className="num">
                  {successor.effective_date} – {successor.expiry_date}
                </dd>
                <dt>Premium</dt>
                <dd className="num">{formatMoney(successor.premium, successor.currency)}</dd>
                <dt>Previous policy</dt>
                <dd>
                  <code>{successor.previous_policy_number ?? policyNumber}</code>
                </dd>
              </dl>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
