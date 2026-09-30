/**
 * Policy Detail — story E5-S3 (AC-15, AC-10, AC-24), route `/policies/:policyNumber`.
 *
 * `GET /api/policies/{policy_number}` (§2.18) answers 404 `NOT_FOUND` both for an unknown number and
 * for another customer's policy, so this screen renders the same "Policy not found" panel for either
 * case and never hints that the policy exists. KYC identifiers are shown exactly as the server masked
 * them (NFR-03) and the lifecycle actions later stories own are disabled on a terminal status (AC-10).
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { getPolicy } from '../api/policies';
import {
  EndorsementHistory,
  LifecycleTimeline,
  PaymentTable,
  RefundTable,
} from '../components/policies/PolicyHistory';
import { StatusBadge } from '../components/StatusBadge';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { classifyError, issueText } from '../lib/apiIssues';
import { formatMoney } from '../lib/money';
import { isLive, PRODUCT_NAMES } from '../types/policies';
import type { ActorRole } from '../types/roles';
import type { PolicyDetail } from '../types/policies';
import './PolicyDetailPage.css';

interface ActionSpec {
  readonly label: string;
  readonly testId: string;
  readonly to: string;
  readonly roles: readonly ActorRole[];
  readonly disabledHint: string;
}

function actionsFor(policyNumber: string): readonly ActionSpec[] {
  return [
    {
      label: 'Endorse',
      testId: 'action-endorse',
      to: `/policies/${policyNumber}/endorse`,
      roles: ['CUSTOMER', 'ADMIN'],
      disabledHint: 'Endorsements are only possible while the policy is active.',
    },
    {
      label: 'Renew',
      testId: 'action-renew',
      to: `/policies/${policyNumber}/renew`,
      roles: ['CUSTOMER'],
      disabledHint: 'Renewal is only possible while the policy is active.',
    },
    {
      label: 'Cancel policy',
      testId: 'action-cancel',
      to: `/policies/${policyNumber}/cancel`,
      roles: ['CUSTOMER', 'ADMIN'],
      disabledHint: 'A policy in a terminal status cannot be cancelled again.',
    },
  ];
}

function ActionLink({
  action,
  enabled,
}: {
  readonly action: ActionSpec;
  readonly enabled: boolean;
}): JSX.Element {
  if (!enabled) {
    return (
      // Kept focusable so keyboard users can reach the explanation (AC-24).
      <a
        className="btn"
        role="link"
        aria-disabled="true"
        tabIndex={0}
        title={action.disabledHint}
        data-testid={action.testId}
      >
        {action.label}
      </a>
    );
  }
  return (
    <Link className="btn" to={action.to} data-testid={action.testId}>
      {action.label}
    </Link>
  );
}

export function PolicyDetailPage(): JSX.Element {
  const { policyNumber = '' } = useParams<{ policyNumber: string }>();
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();

  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setNotFound(false);
    setError(null);
    try {
      setPolicy(await getPolicy(api, policyNumber));
    } catch (caught) {
      setPolicy(null);
      if (caught instanceof ApiError && caught.status === 404) setNotFound(true);
      else setError(issueText(classifyError(caught, 'The policy could not be loaded.')));
    } finally {
      setLoading(false);
    }
  }, [api, policyNumber]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <p className="muted" role="status">
        Loading policy…
      </p>
    );
  }

  if (notFound) {
    return (
      <section className="panel" data-testid="policy-not-found">
        <h1>Policy not found</h1>
        <p role="status">
          Policy <code>{policyNumber}</code> was not found. Check the number on your documents — the
          list of your policies is on <Link to="/policies">My Policies</Link>.
        </p>
      </section>
    );
  }

  if (policy === null) {
    return (
      <section className="panel">
        <h1>My Policies</h1>
        <div className="alert alert-error" role="alert" data-testid="policy-error">
          <p>{error ?? 'The policy could not be loaded.'}</p>
          <button type="button" className="btn btn-sm" onClick={() => void load()}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  const live = isLive(policy.status);
  const currency = policy.currency;

  return (
    <div className="policy-detail" data-testid="policy-detail" data-narrow={String(isNarrow)}>
      <p>
        <Link to="/policies">← Back to My Policies</Link>
      </p>

      <div className="page-head">
        <div>
          <h1>
            {policy.policy_number} <StatusBadge status={policy.status} />
          </h1>
          <p className="route" data-testid="detail-status">
            Status {policy.status} · {PRODUCT_NAMES[policy.product]} · rule v{policy.rule_version}
          </p>
        </div>
        <div className="detail-actions">
          {actionsFor(policy.policy_number)
            .filter((action) => action.roles.includes(role))
            .map((action) => (
              <ActionLink key={action.testId} action={action} enabled={live} />
            ))}
        </div>
      </div>

      <div className="detail-grid">
        <section className="panel" aria-labelledby="cover-h">
          <h2 id="cover-h">Cover details</h2>
          <dl className="kv">
            <dt>Product</dt>
            <dd>
              {PRODUCT_NAMES[policy.product]} (<code>{policy.product}</code>)
            </dd>
            <dt>Sum insured</dt>
            <dd className="num">{formatMoney(policy.sum_insured, currency)}</dd>
            <dt>Premium</dt>
            <dd className="num" data-testid="detail-premium">
              {formatMoney(policy.premium, currency)}
            </dd>
            <dt>Effective date</dt>
            <dd className="num">{policy.effective_date}</dd>
            <dt>Expiry date</dt>
            <dd className="num">{policy.expiry_date}</dd>
            <dt>Next premium due</dt>
            <dd className="num">{policy.next_premium_due_date ?? '—'}</dd>
            <dt>Previous policy</dt>
            <dd>{policy.previous_policy_number ?? '—'}</dd>
            <dt>Renewed as</dt>
            <dd>{policy.successor_policy_number ?? '—'}</dd>
          </dl>
        </section>

        <section className="panel" aria-labelledby="insured-h">
          <h2 id="insured-h">Insured</h2>
          <dl className="kv">
            <dt>Name</dt>
            <dd>{policy.insured.full_name}</dd>
            <dt>Aadhaar</dt>
            <dd className="mono" data-testid="detail-aadhaar">
              {policy.insured.aadhaar_masked}
            </dd>
            <dt>PAN</dt>
            <dd className="mono" data-testid="detail-pan">
              {policy.insured.pan_masked}
            </dd>
            <dt>Address</dt>
            <dd>{policy.insured.address}</dd>
            <dt>Nominees</dt>
            <dd>
              {policy.insured.nominees.length === 0
                ? 'None'
                : policy.insured.nominees
                    .map((n) => `${n.nominee_name} · ${n.relationship} · ${n.share_percent}%`)
                    .join(', ')}
            </dd>
          </dl>
        </section>
      </div>

      <section className="panel" aria-labelledby="endorse-h">
        <h2 id="endorse-h">Endorsement history</h2>
        <EndorsementHistory endorsements={policy.endorsements} currency={currency} />
      </section>

      <div className="detail-grid">
        <section className="panel" aria-labelledby="lifecycle-h">
          <h2 id="lifecycle-h">Lifecycle</h2>
          <LifecycleTimeline transitions={policy.transitions} />
        </section>

        <section className="panel" aria-labelledby="money-h">
          <h2 id="money-h">Premium payments and refunds</h2>
          <PaymentTable payments={policy.payments} currency={currency} />
          <h3 className="section-gap">Refunds</h3>
          <RefundTable refunds={policy.refunds} currency={currency} />
        </section>
      </div>
    </div>
  );
}
