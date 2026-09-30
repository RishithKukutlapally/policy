/**
 * Append-only history of one policy (NFR-02): endorsements oldest first, the lifecycle timeline, the
 * premium payments and any refunds. Presentation only — every value comes straight from §2.18.
 */
import { StatusBadge } from '../StatusBadge';
import { formatMoney } from '../../lib/money';
import { describeSnapshot, formatInstant, formatSignedMoney } from './format';
import type {
  EndorsementRecord,
  PolicyTransition,
  PremiumPayment,
  RefundRecord,
} from '../../types/policies';
import './policies.css';

export interface EndorsementHistoryProps {
  readonly endorsements: readonly EndorsementRecord[];
  readonly currency: string;
}

export function EndorsementHistory({
  endorsements,
  currency,
}: EndorsementHistoryProps): JSX.Element {
  if (endorsements.length === 0) {
    return (
      <div className="empty" data-testid="endorsements-empty">
        No endorsements on this policy yet.
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="endorsement-history">
        <caption className="sr-only">Endorsements, oldest first</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Type</th>
            <th scope="col">Before</th>
            <th scope="col">After</th>
            <th scope="col">Premium delta</th>
          </tr>
        </thead>
        <tbody>
          {endorsements.map((endorsement) => (
            <tr key={endorsement.endorsement_id}>
              <td data-label="Date" className="num">
                {endorsement.endorsement_date}
              </td>
              <td data-label="Type">
                <code>{endorsement.type}</code>
              </td>
              <td data-label="Before" className="before-after">
                {describeSnapshot(endorsement.before, currency)}
              </td>
              <td data-label="After" className="before-after">
                {describeSnapshot(endorsement.after, currency)}
              </td>
              <td data-label="Premium delta" className="num">
                {formatSignedMoney(endorsement.premium_delta, currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LifecycleTimeline({
  transitions,
}: {
  readonly transitions: readonly PolicyTransition[];
}): JSX.Element {
  if (transitions.length === 0) {
    return (
      <div className="empty" data-testid="lifecycle-empty">
        No transitions recorded.
      </div>
    );
  }
  return (
    <ol className="timeline" data-testid="lifecycle">
      {transitions.map((transition) => (
        <li key={`${transition.to_status}-${transition.occurred_at}`}>
          {transition.from_status === null ? (
            <span>Issued</span>
          ) : (
            <StatusBadge status={transition.from_status} />
          )}
          <span className="timeline-arrow" aria-hidden="true">
            →
          </span>
          <span className="sr-only">to</span>
          <StatusBadge status={transition.to_status} />
          <br />
          <span className="small muted">
            {formatInstant(transition.occurred_at)} · reason <code>{transition.reason}</code>
          </span>
        </li>
      ))}
    </ol>
  );
}

export function PaymentTable({
  payments,
  currency,
}: {
  readonly payments: readonly PremiumPayment[];
  readonly currency: string;
}): JSX.Element {
  if (payments.length === 0) {
    return <p className="small muted">No premium payments recorded.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="payments">
        <caption className="sr-only">Premium payments</caption>
        <thead>
          <tr>
            <th scope="col">Due date</th>
            <th scope="col">Amount</th>
            <th scope="col">Rule</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.payment_id}>
              <td data-label="Due date" className="num">
                {payment.due_date}
              </td>
              <td data-label="Amount" className="num">
                {formatMoney(payment.amount, currency)}
              </td>
              <td data-label="Rule">v{payment.rule_version}</td>
              <td data-label="Status">
                <StatusBadge status={payment.paid_at === null ? 'UNPAID' : 'PAID'} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RefundTable({
  refunds,
  currency,
}: {
  readonly refunds: readonly RefundRecord[];
  readonly currency: string;
}): JSX.Element {
  if (refunds.length === 0) {
    return <p className="small muted">No refunds.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="refunds">
        <caption className="sr-only">Refunds</caption>
        <thead>
          <tr>
            <th scope="col">Cancellation date</th>
            <th scope="col">Type</th>
            <th scope="col">Admin fee</th>
            <th scope="col">Amount</th>
          </tr>
        </thead>
        <tbody>
          {refunds.map((refund) => (
            <tr key={refund.refund_id}>
              <td data-label="Cancellation date" className="num">
                {refund.cancellation_date}
              </td>
              <td data-label="Type">
                <code>{refund.refund_type}</code>
              </td>
              <td data-label="Admin fee" className="num">
                {formatMoney(refund.admin_fee, currency)}
              </td>
              <td data-label="Amount" className="num" data-testid="refund-amount">
                {formatMoney(refund.amount, currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
