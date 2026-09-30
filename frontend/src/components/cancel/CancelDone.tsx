/**
 * The post-cancellation view of the Cancel screen (story E8-S3, AC-08, AC-24).
 *
 * The refund row rendered here is the persisted `RefundRecord` from the 200 body (§2.24), not the
 * preview — so what the customer sees confirmed is exactly what was written (NFR-02).
 */
import { Link } from 'react-router-dom';
import { formatMoney } from '../../lib/money';
import { RefundTable } from '../policies/PolicyHistory';
import { StatusBadge } from '../StatusBadge';
import type { CancelResult } from '../../types/cancellation';

export interface CancelDoneProps {
  readonly result: CancelResult;
  readonly currency: string;
}

export function CancelDone({ result, currency }: CancelDoneProps): JSX.Element {
  const isFreeLook = result.refund.refund_type === 'FREE_LOOK';
  return (
    <div className="cancel-done">
      <div className="alert alert-ok" role="status" data-testid="cancel-confirmation">
        <p>
          Policy cancelled. {isFreeLook ? 'Full refund ' : 'Refund '}
          {formatMoney(result.refund.amount, currency)} recorded.
        </p>
      </div>
      <div className="page-head">
        <div>
          <h1>
            {result.policy_number} <StatusBadge status={result.status} />
          </h1>
        </div>
        <Link className="btn" to={`/policies/${result.policy_number}`}>
          Open full Policy Detail
        </Link>
      </div>
      <section className="panel" aria-labelledby="refund-h">
        <h2 id="refund-h">Refund</h2>
        <RefundTable refunds={[result.refund]} currency={currency} />
      </section>
    </div>
  );
}
