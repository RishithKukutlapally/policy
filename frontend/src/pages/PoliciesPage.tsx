/**
 * My Policies — story E5-S3 (AC-15, AC-24, AC-05), route `/policies`.
 *
 * `GET /api/policies` is actor-scoped by the server: a CUSTOMER receives only their own policies while
 * an UNDERWRITER or ADMIN receives all of them, so this screen renders whatever it is given and only
 * changes its heading. Reached as `/policies?application=<id>` after an AUTO_BIND decision it offers
 * the issuance action (`POST /api/applications/{id}/issue`, §2.16) and then opens the new policy.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { issuePolicy, listPolicies } from '../api/policies';
import { PolicyList } from '../components/policies/PolicyList';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { classifyError, issueText } from '../lib/apiIssues';
import type { PolicySummary } from '../types/policies';
import './PoliciesPage.css';

export function PoliciesPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const applicationId = params.get('application');

  const [policies, setPolicies] = useState<readonly PolicySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      setPolicies(await listPolicies(api));
      setListError(null);
    } catch (error) {
      setPolicies([]);
      setListError(issueText(classifyError(error, 'Your policies could not be loaded.')));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const issue = useCallback(async (): Promise<void> => {
    if (applicationId === null) return;
    setIssuing(true);
    setIssueError(null);
    try {
      const policy = await issuePolicy(api, applicationId);
      navigate(`/policies/${policy.policy_number}`);
    } catch (error) {
      setIssueError(issueText(classifyError(error, 'The policy could not be issued.')));
    } finally {
      setIssuing(false);
    }
  }, [api, applicationId, navigate]);

  const ownView = role === 'CUSTOMER';

  return (
    <div className="policies-page" data-testid="policies-page" data-narrow={String(isNarrow)}>
      <div className="page-head">
        <div>
          <h1>{ownView ? 'My Policies' : 'All policies'}</h1>
          <p className="route">
            {ownView
              ? 'Your issued policies, their premium and the next premium due date.'
              : 'Every policy in the portfolio — read only on this screen.'}
          </p>
        </div>
      </div>

      {applicationId !== null ? (
        <section className="panel policies-issue" aria-labelledby="issue-h">
          <h2 id="issue-h">Issue your policy</h2>
          <p className="small muted">
            Your application was approved (AUTO_BIND). Issuing it creates the policy and its first
            premium payment.
          </p>
          {issueError !== null ? (
            <div className="alert alert-error" role="alert" data-testid="issue-error">
              <p>{issueError}</p>
            </div>
          ) : null}
          <button
            type="button"
            className="btn btn-primary"
            data-testid="issue-policy"
            onClick={() => void issue()}
            disabled={issuing}
          >
            {issuing ? 'Issuing…' : 'Issue policy'}
          </button>
        </section>
      ) : null}

      {listError !== null ? (
        <div className="alert alert-error" role="alert" data-testid="policies-error">
          <p>{listError}</p>
          <button type="button" className="btn btn-sm" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}

      {loading ? (
        <p className="muted" role="status">
          Loading your policies…
        </p>
      ) : null}

      {!loading && listError === null && policies.length === 0 ? (
        <div className="empty" data-testid="policies-empty">
          <p>You have no policies yet.</p>
          <Link className="btn btn-primary" to="/quote">
            Get a Quote
          </Link>
        </div>
      ) : null}

      {!loading && policies.length > 0 ? (
        <>
          <PolicyList
            policies={policies}
            isNarrow={isNarrow}
            caption={ownView ? 'Your policies' : 'All policies'}
          />
          <p className="small muted policies-hint">
            Select a policy number to open its detail, endorsement history and lifecycle.
          </p>
        </>
      ) : null}
    </div>
  );
}
