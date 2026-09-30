/**
 * The post-submission view of the Endorse screen (story E6-S3, AC-06, AC-24).
 *
 * The history shown is the policy re-read after the 201, so the row is the persisted append-only record
 * rather than an optimistic echo of the request (NFR-02). `premium_delta` keeps the server's sign.
 */
import { Link } from 'react-router-dom';
import { formatSignedMoney } from '../policies/format';
import { EndorsementHistory } from '../policies/PolicyHistory';
import { StatusBadge } from '../StatusBadge';
import type { EndorsementType, PolicyDetail } from '../../types/policies';

export interface EndorsementDoneProps {
  readonly policyNumber: string;
  readonly type: EndorsementType;
  readonly premiumDelta: string;
  readonly currency: string;
  /** The re-read policy, or `null` when that follow-up request failed. */
  readonly endorsed: PolicyDetail | null;
}

export function EndorsementDone({
  policyNumber,
  type,
  premiumDelta,
  currency,
  endorsed,
}: EndorsementDoneProps): JSX.Element {
  return (
    <div className="endorse-done">
      <div className="alert alert-ok" role="status" data-testid="endorsement-confirmation">
        <p>
          Endorsement <code>{type}</code> recorded for {policyNumber} · premium delta{' '}
          {formatSignedMoney(premiumDelta, currency)}.
        </p>
      </div>
      <div className="page-head">
        <div>
          <h1>
            {policyNumber} <StatusBadge status={endorsed?.status ?? 'ENDORSED'} />
          </h1>
        </div>
        <Link className="btn" to={`/policies/${policyNumber}`}>
          Open full Policy Detail
        </Link>
      </div>
      <section className="panel" aria-labelledby="eh-h">
        <h2 id="eh-h">Endorsement history</h2>
        <EndorsementHistory endorsements={endorsed?.endorsements ?? []} currency={currency} />
      </section>
    </div>
  );
}
