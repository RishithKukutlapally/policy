/**
 * The underwriting queue, rendered as a table on the desktop and as stacked cards below the 768 px
 * breakpoint (AC-24). Shared by the Workbench and the Admin Underwriting Review.
 */
import type { ReactNode } from 'react';
import { StatusBadge } from '../StatusBadge';
import { formatMoney } from '../../lib/money';
import { shortId } from '../../lib/maskPii';
import type { QueueItem } from '../../types/applications';
import './uw.css';

export interface QueueViewProps {
  readonly items: readonly QueueItem[];
  readonly caption: string;
  readonly emptyText: string;
  readonly isNarrow: boolean;
  /** Per-row action (open / override / a status note). */
  readonly renderAction: (item: QueueItem) => ReactNode;
}

function submittedDate(item: QueueItem): string {
  return item.submitted_at.slice(0, 10);
}

function codes(item: QueueItem): string {
  return item.reason_codes.length === 0 ? '—' : item.reason_codes.join(', ');
}

export function QueueView({
  items,
  caption,
  emptyText,
  isNarrow,
  renderAction,
}: QueueViewProps): JSX.Element {
  if (items.length === 0) {
    return (
      <div className="empty" data-testid="queue-empty">
        {emptyText}
      </div>
    );
  }

  if (isNarrow) {
    return (
      <ul className="queue-cards" data-testid="queue-cards" aria-label={caption}>
        {items.map((item) => (
          <li
            key={item.application_id}
            className="queue-card"
            data-testid={`queue-card-${shortId(item.application_id)}`}
          >
            <div className="queue-card-head">
              <code className="mono">{shortId(item.application_id)}…</code>
              <StatusBadge status={item.status} />
            </div>
            <dl className="kv">
              <dt>Product</dt>
              <dd>{item.product}</dd>
              <dt>Reason codes</dt>
              <dd>
                <code>{codes(item)}</code>
              </dd>
              <dt>Rule</dt>
              <dd>v{item.rule_version}</dd>
              <dt>Premium</dt>
              <dd className="num">{formatMoney(item.premium)}</dd>
              <dt>Submitted</dt>
              <dd>{submittedDate(item)}</dd>
            </dl>
            <div className="queue-card-actions">{renderAction(item)}</div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="queue-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Application</th>
            <th scope="col">Product</th>
            <th scope="col">Status</th>
            <th scope="col">Reason codes</th>
            <th scope="col">Rule</th>
            <th scope="col">Submitted</th>
            <th scope="col">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.application_id} data-testid={`queue-row-${shortId(item.application_id)}`}>
              <td data-label="Application">
                <code className="mono">{shortId(item.application_id)}…</code>
              </td>
              <td data-label="Product">{item.product}</td>
              <td data-label="Status">
                <StatusBadge status={item.status} />
              </td>
              <td data-label="Reason codes">
                <code>{codes(item)}</code>
              </td>
              <td data-label="Rule">v{item.rule_version}</td>
              <td data-label="Submitted" className="num">
                {submittedDate(item)}
              </td>
              <td data-label="Actions" className="cell-actions">
                {renderAction(item)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
