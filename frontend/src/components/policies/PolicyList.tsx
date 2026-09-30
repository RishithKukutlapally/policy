/**
 * The policy list, rendered as a table on the desktop and as stacked cards below the 768 px
 * breakpoint (AC-24). Money is formatted from the decimal strings the API sends (NFR-01).
 */
import { Link } from 'react-router-dom';
import { StatusBadge } from '../StatusBadge';
import { formatMoney } from '../../lib/money';
import { PRODUCT_NAMES } from '../../types/policies';
import type { PolicySummary } from '../../types/policies';
import './policies.css';

export interface PolicyListProps {
  readonly policies: readonly PolicySummary[];
  readonly isNarrow: boolean;
  readonly caption: string;
}

function detailPath(policy: PolicySummary): string {
  return `/policies/${policy.policy_number}`;
}

function term(policy: PolicySummary): string {
  return `${policy.effective_date} – ${policy.expiry_date}`;
}

function nextDue(policy: PolicySummary): JSX.Element {
  if (policy.next_premium_due_date === null) {
    return <span className="muted">— (not renewable)</span>;
  }
  return <>{policy.next_premium_due_date}</>;
}

function OpenLink({ policy }: { readonly policy: PolicySummary }): JSX.Element {
  return (
    <Link
      className="policy-open"
      to={detailPath(policy)}
      data-testid="policy-open"
      data-policy-number={policy.policy_number}
      aria-label={`Open policy ${policy.policy_number}`}
    >
      {policy.policy_number}
    </Link>
  );
}

function money(policy: PolicySummary, amount: string): string {
  return formatMoney(amount, policy.currency);
}

export function PolicyList({ policies, isNarrow, caption }: PolicyListProps): JSX.Element {
  if (isNarrow) {
    return (
      <ul className="policy-cards" data-testid="policy-list" aria-label={caption}>
        {policies.map((policy) => (
          <li
            key={policy.policy_number}
            className="policy-card"
            data-testid={`policy-card-${policy.policy_number}`}
          >
            <div className="policy-card-head">
              <OpenLink policy={policy} />
              <StatusBadge status={policy.status} />
            </div>
            <dl className="kv">
              <dt>Product</dt>
              <dd>{PRODUCT_NAMES[policy.product]}</dd>
              <dt>Sum insured</dt>
              <dd className="num">{money(policy, policy.sum_insured)}</dd>
              <dt>Premium</dt>
              <dd className="num">{money(policy, policy.premium)}</dd>
              <dt>Term</dt>
              <dd className="num">{term(policy)}</dd>
              <dt>Next premium due</dt>
              <dd className="num">{nextDue(policy)}</dd>
            </dl>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="policy-list">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Policy number</th>
            <th scope="col">Product</th>
            <th scope="col">Status</th>
            <th scope="col">Sum insured</th>
            <th scope="col">Premium</th>
            <th scope="col">Term</th>
            <th scope="col">Next premium due</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((policy) => (
            <tr key={policy.policy_number} data-testid={`policy-row-${policy.policy_number}`}>
              <td data-label="Policy number">
                <OpenLink policy={policy} />
              </td>
              <td data-label="Product">{PRODUCT_NAMES[policy.product]}</td>
              <td data-label="Status">
                <StatusBadge status={policy.status} />
              </td>
              <td data-label="Sum insured" className="num">
                {money(policy, policy.sum_insured)}
              </td>
              <td data-label="Premium" className="num">
                {money(policy, policy.premium)}
              </td>
              <td data-label="Term" className="num">
                {term(policy)}
              </td>
              <td data-label="Next premium due" className="num">
                {nextDue(policy)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
