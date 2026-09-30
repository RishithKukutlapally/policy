/**
 * The read-only "Policy" side panel shared by the Endorse and Cancel screens.
 *
 * Only cover facts are shown. The insured's KYC identifiers are deliberately absent — those belong to
 * Policy Detail, and a lifecycle form has no reason to put them on screen (NFR-03).
 */
import { formatMoney } from '../../lib/money';
import { PRODUCT_NAMES } from '../../types/policies';
import type { PolicyDetail } from '../../types/policies';
import { StatusBadge } from '../StatusBadge';

export interface PolicyFactsPanelProps {
  readonly policy: PolicyDetail;
  /** Extra rows the owning screen needs (the address and nominees on Endorse, for example). */
  readonly extra?: JSX.Element;
  readonly footnote: string;
  /** Endorse shows the status here; Cancel already shows it in the page heading. */
  readonly showStatus?: boolean;
}

export function PolicyFactsPanel({
  policy,
  extra,
  footnote,
  showStatus = false,
}: PolicyFactsPanelProps): JSX.Element {
  const currency = policy.currency;
  return (
    <section className="panel" aria-labelledby="policy-facts-h">
      <h2 id="policy-facts-h">Policy</h2>
      <dl className="kv">
        {showStatus ? (
          <>
            <dt>Status</dt>
            <dd>
              <StatusBadge status={policy.status} testId="facts-status" />
            </dd>
          </>
        ) : null}
        <dt>Product</dt>
        <dd>
          {PRODUCT_NAMES[policy.product]} · rule v{policy.rule_version}
        </dd>
        <dt>Sum insured</dt>
        <dd className="num">{formatMoney(policy.sum_insured, currency)}</dd>
        <dt>Premium</dt>
        <dd className="num">{formatMoney(policy.premium, currency)}</dd>
        <dt>Term</dt>
        <dd className="num">
          {policy.effective_date} – {policy.expiry_date}
        </dd>
        {extra}
      </dl>
      <p className="small muted">{footnote}</p>
    </section>
  );
}
