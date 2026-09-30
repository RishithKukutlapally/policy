/**
 * Portfolio dashboard — story E9-S2 (AC-20, AC-24), route `/admin/portfolio`, ADMIN only.
 *
 * `GET /api/admin/portfolio?as_of=` (§2.26) returns every figure already aggregated, so this screen is
 * pure presentation: counts and decimal strings straight through `Intl.NumberFormat('en-IN')` (NFR-01).
 * Changing "As of" refetches; a failure shows an inline alert with a Retry button rather than an empty
 * dashboard that looks like real zero data (AC-20).
 */
import { useCallback, useEffect, useState } from 'react';
import { getPortfolio } from '../api/portfolio';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { PortfolioCards } from '../components/admin/PortfolioCards';
import { LapseForecastView, RenewalPipeline } from '../components/admin/PortfolioTables';
import { FieldError } from '../components/FieldError';
import { NotAuthorised } from '../components/NotAuthorised';
import { classifyError, issueText } from '../lib/apiIssues';
import { formatMoney } from '../lib/money';
import type { PortfolioSnapshot } from '../types/portfolio';
import '../components/lifecycle/lifecycle.css';
import '../components/policies/policies.css';
import './PortfolioPage.css';

export function PortfolioPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();
  const isAdmin = role === 'ADMIN';

  /** Empty means "the server's own business date" (DEC-012) — never the browser clock. */
  const [asOf, setAsOf] = useState('');
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [loading, setLoading] = useState(isAdmin);
  const [error, setError] = useState<string | null>(null);
  const [fieldCode, setFieldCode] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    setFieldCode(null);
    try {
      setSnapshot(await getPortfolio(api, asOf === '' ? undefined : asOf));
    } catch (caught) {
      const issues = classifyError(caught, 'The portfolio could not be loaded.');
      setSnapshot(null);
      setFieldCode(issues.fields.as_of ?? null);
      setError(issueText(issues));
    } finally {
      setLoading(false);
    }
  }, [api, asOf, isAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isAdmin) return <NotAuthorised allowed={['Admin']} />;

  const currency = 'INR';

  return (
    <div className="portfolio-page">
      <div className="page-head">
        <div>
          <h1>Portfolio</h1>
          <p className="route">
            Active cover, premium collected, the renewal pipeline and the lapse forecast
            {snapshot === null ? '' : ` as of ${snapshot.as_of}`}.
          </p>
        </div>
        <form
          className="lc-toolbar"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void load();
          }}
        >
          <div className="field portfolio-asof">
            <label htmlFor="portfolio-as-of">As of</label>
            <input
              type="date"
              id="portfolio-as-of"
              name="as_of"
              className="lc-input"
              value={asOf}
              data-testid="as-of"
              aria-invalid={fieldCode === null ? undefined : true}
              aria-describedby={fieldCode === null ? undefined : 'as_of-error'}
              onChange={(event) => setAsOf(event.target.value)}
            />
            <FieldError name="as_of" code={fieldCode} />
          </div>
        </form>
      </div>

      {loading ? (
        <p className="lc-loading" role="status" data-testid="loading">
          Loading portfolio…
        </p>
      ) : null}

      {!loading && error !== null ? (
        <div className="alert alert-error" role="alert" data-testid="portfolio-error">
          <p>{error}</p>
          <button type="button" className="btn btn-sm" data-testid="retry" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}

      {!loading && snapshot !== null ? (
        <>
          <section aria-labelledby="summary-h">
            <h2 id="summary-h" className="sr-only">
              Summary
            </h2>
            <PortfolioCards snapshot={snapshot} currency={currency} />
          </section>

          <div className="grid-2">
            <section className="panel" aria-labelledby="rp-h">
              <h2 id="rp-h">Renewal pipeline</h2>
              <p className="small muted">Renewals due in the next 30 days</p>
              <RenewalPipeline
                rows={snapshot.renewal_pipeline}
                isNarrow={isNarrow}
                currency={currency}
              />
            </section>

            <section className="panel" aria-labelledby="lf-h">
              <h2 id="lf-h">Lapse forecast</h2>
              <p className="small muted">
                Unpaid policies whose grace period ends in the next 30 days ·{' '}
                <strong>{snapshot.lapse_forecast.count}</strong> at risk · premium at risk{' '}
                <strong className="num">
                  {formatMoney(snapshot.lapse_forecast.premium_at_risk, currency)}
                </strong>
              </p>
              <LapseForecastView
                forecast={snapshot.lapse_forecast}
                isNarrow={isNarrow}
                currency={currency}
              />
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
