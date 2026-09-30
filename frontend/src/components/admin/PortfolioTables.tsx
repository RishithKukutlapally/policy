/**
 * The renewal-pipeline and lapse-forecast views of the Portfolio dashboard (story E9-S2, AC-20, AC-24).
 *
 * Below the 768 px breakpoint each table becomes a list of stacked cards so there is no horizontal
 * scroll at 390 px; both shapes keep the same `data-testid` so one Playwright selector covers either.
 * Payment state is always the words `PAID` / `UNPAID` — never colour alone.
 */
import type { ReactNode } from 'react';
import { formatMoney } from '../../lib/money';
import { PRODUCT_NAMES } from '../../types/policies';
import type { LapseForecast, RenewalPipelineRow } from '../../types/portfolio';
import { StatusBadge } from '../StatusBadge';

/** One cell of the stacked-card shape: the column label plus its value. */
function CardRow({
  label,
  children,
}: {
  readonly label: string;
  readonly children: ReactNode;
}): JSX.Element {
  return (
    <div className="portfolio-card-row">
      <span className="lbl">{label}</span>
      <span>{children}</span>
    </div>
  );
}

export interface RenewalPipelineProps {
  readonly rows: readonly RenewalPipelineRow[];
  readonly isNarrow: boolean;
  readonly currency: string;
}

export function RenewalPipeline({
  rows,
  isNarrow,
  currency,
}: RenewalPipelineProps): JSX.Element {
  if (rows.length === 0) {
    return (
      <div className="empty" data-testid="pipeline-empty">
        No renewals due in the next 30 days
      </div>
    );
  }

  const premium = (row: RenewalPipelineRow): string =>
    row.renewal_premium === null ? 'Not renewable' : formatMoney(row.renewal_premium, currency);

  if (isNarrow) {
    return (
      <ul className="card-list" data-testid="renewal-pipeline">
        {rows.map((row) => (
          <li className="card" key={row.policy_number}>
            <p className="card-title">
              <code>{row.policy_number}</code>
              <StatusBadge status={row.paid ? 'PAID' : 'UNPAID'} testId="pipeline-status" />
            </p>
            <CardRow label="Product">{PRODUCT_NAMES[row.product]}</CardRow>
            <CardRow label="Due date">
              <span className="num">{row.due_date}</span>
            </CardRow>
            <CardRow label="Renewal premium">
              <span className="num">{premium(row)}</span>
            </CardRow>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="renewal-pipeline">
        <caption className="sr-only">Renewal pipeline</caption>
        <thead>
          <tr>
            <th scope="col">Policy number</th>
            <th scope="col">Product</th>
            <th scope="col">Due date</th>
            <th scope="col">Renewal premium</th>
            <th scope="col">Payment</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.policy_number}>
              <td data-label="Policy number">
                <code>{row.policy_number}</code>
              </td>
              <td data-label="Product">{PRODUCT_NAMES[row.product]}</td>
              <td data-label="Due date" className="num">
                {row.due_date}
              </td>
              <td data-label="Renewal premium" className="num">
                {premium(row)}
              </td>
              <td data-label="Payment">
                <StatusBadge status={row.paid ? 'PAID' : 'UNPAID'} testId="pipeline-status" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface LapseForecastViewProps {
  readonly forecast: LapseForecast;
  readonly isNarrow: boolean;
  readonly currency: string;
}

export function LapseForecastView({
  forecast,
  isNarrow,
  currency,
}: LapseForecastViewProps): JSX.Element {
  if (forecast.policies.length === 0) {
    return (
      <div className="empty" data-testid="lapse-empty">
        No policies at risk
      </div>
    );
  }

  if (isNarrow) {
    return (
      <ul className="card-list" data-testid="lapse-forecast">
        {forecast.policies.map((row) => (
          <li className="card" key={row.policy_number}>
            <p className="card-title">
              <code>{row.policy_number}</code>
            </p>
            <CardRow label="Product">{PRODUCT_NAMES[row.product]}</CardRow>
            <CardRow label="Due date">
              <span className="num">{row.due_date}</span>
            </CardRow>
            <CardRow label="Grace end date">
              <span className="num">{row.grace_end_date}</span>
            </CardRow>
            <CardRow label="Premium at risk">
              <span className="num">{formatMoney(row.premium, currency)}</span>
            </CardRow>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="lapse-forecast">
        <caption className="sr-only">Lapse forecast</caption>
        <thead>
          <tr>
            <th scope="col">Policy number</th>
            <th scope="col">Product</th>
            <th scope="col">Due date</th>
            <th scope="col">Grace end date</th>
            <th scope="col">Premium at risk</th>
          </tr>
        </thead>
        <tbody>
          {forecast.policies.map((row) => (
            <tr key={row.policy_number}>
              <td data-label="Policy number">
                <code>{row.policy_number}</code>
              </td>
              <td data-label="Product">{PRODUCT_NAMES[row.product]}</td>
              <td data-label="Due date" className="num">
                {row.due_date}
              </td>
              <td data-label="Grace end date" className="num">
                {row.grace_end_date}
              </td>
              <td data-label="Premium at risk" className="num">
                {formatMoney(row.premium, currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
