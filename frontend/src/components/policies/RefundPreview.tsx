/**
 * The refund breakdown of the Cancel screen (story E8-S3, contract §2.23, AC-19).
 *
 * Every figure in the sentence is a decimal string the server computed: the net `amount`, the gross
 * `pro_rata_amount` and the `admin_fee`. The UI joins them into prose and never performs the
 * subtraction itself (NFR-01) — when the server omits the gross figure the clause is dropped rather
 * than derived.
 */
import { formatMoney } from '../../lib/money';
import type { RefundBreakdown } from '../../types/cancellation';

/** AC-19: `Full refund ₹12,000.00 (free-look)` or `Refund ₹8,791.10 = ₹9,041.10 pro-rata for 275 unused days − ₹250.00 admin fee`. */
export function refundSentence(refund: RefundBreakdown, currency: string): string {
  const net = formatMoney(refund.amount, currency);
  if (refund.refund_type === 'FREE_LOOK') return `Full refund ${net} (free-look)`;
  if (refund.pro_rata_amount === undefined) {
    return `Refund ${net} pro-rata for ${refund.unused_days} unused days, after a ${formatMoney(refund.admin_fee, currency)} admin fee`;
  }
  const gross = formatMoney(refund.pro_rata_amount, currency);
  const fee = formatMoney(refund.admin_fee, currency);
  return `Refund ${net} = ${gross} pro-rata for ${refund.unused_days} unused days − ${fee} admin fee`;
}

export interface RefundPreviewProps {
  readonly refund: RefundBreakdown;
  readonly currency: string;
}

export function RefundPreview({ refund, currency }: RefundPreviewProps): JSX.Element {
  return (
    <>
      <p className="refund-line" data-testid="refund-sentence">
        {refundSentence(refund, currency)}
      </p>
      <dl className="kv small">
        <dt>Refund type</dt>
        <dd>
          <code>{refund.refund_type}</code>
        </dd>
        <dt>Premium paid</dt>
        <dd className="num">{formatMoney(refund.premium_paid, currency)}</dd>
        <dt>Days elapsed</dt>
        <dd>
          {refund.days_elapsed} of {refund.term_days}
        </dd>
        <dt>Unused days</dt>
        <dd>{refund.unused_days}</dd>
        <dt>Admin fee</dt>
        <dd className="num">{formatMoney(refund.admin_fee, currency)}</dd>
        <dt>Refund payable</dt>
        <dd className="num">{formatMoney(refund.amount, currency)}</dd>
      </dl>
    </>
  );
}
