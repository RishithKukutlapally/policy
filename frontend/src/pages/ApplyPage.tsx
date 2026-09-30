/**
 * Apply — story E4-S5 (AC-03, AC-04, AC-24, NFR-03), route `/apply/:quoteId` (also `/apply?quote=…`),
 * CUSTOMER.
 *
 * The quoted premium is read-only: it is the decimal string the backend computed and the UI only
 * formats it (NFR-01). The KYC stub is posted once to `POST /api/applications` and the raw identifiers
 * are dropped from state as soon as the response arrives; the screen then shows the synchronous
 * underwriting outcome with each reason code and its rule-version description.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { createApplication } from '../api/applications';
import { getQuote } from '../api/quotes';
import { KycForm } from '../components/uw/KycForm';
import { ReasonCodeList } from '../components/uw/ReasonCodeList';
import { StatusBadge } from '../components/StatusBadge';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { classifyError, issueText } from '../lib/apiIssues';
import { formatMoney } from '../lib/money';
import type {
  ApplicationRequest,
  ApplicationResponse,
  KycFormValues,
} from '../types/applications';
import type { StoredQuote } from '../types/quotes';
import './ApplyPage.css';

const EMPTY_KYC: KycFormValues = {
  full_name: '',
  date_of_birth: '',
  aadhaar: '',
  pan: '',
  address: '',
};

function buildBody(quoteId: string, kyc: KycFormValues, hasCondition: boolean, details: string, isTermLife: boolean): ApplicationRequest {
  const body: ApplicationRequest = { quote_id: quoteId, kyc: { ...kyc } };
  if (!isTermLife) return body;
  return {
    ...body,
    health_declaration: { has_pre_existing_condition: hasCondition, details },
  };
}

export function ApplyPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();
  const params = useParams<{ quoteId?: string }>();
  const [search] = useSearchParams();
  const quoteId = params.quoteId ?? search.get('quote') ?? '';

  const [quote, setQuote] = useState<StoredQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [kyc, setKyc] = useState<KycFormValues>(EMPTY_KYC);
  const [hasCondition, setHasCondition] = useState(false);
  const [details, setDetails] = useState('');
  const [issues, setIssues] = useState<Readonly<Record<string, string>>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [result, setResult] = useState<ApplicationResponse | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (quoteId === '' || role !== 'CUSTOMER') return;
    let cancelled = false;
    getQuote(api, quoteId)
      .then((loaded) => {
        if (!cancelled) setQuote(loaded);
      })
      .catch((error: unknown) => {
        if (!cancelled) setQuoteError(issueText(classifyError(error, 'The quote could not be loaded.')));
      });
    return () => {
      cancelled = true;
    };
  }, [api, quoteId, role]);

  const onKycChange = useCallback((field: keyof KycFormValues, value: string): void => {
    setKyc((current) => ({ ...current, [field]: value }));
  }, []);

  const isTermLife = quote?.product === 'TERM_LIFE';

  const onSubmit = useCallback(async (): Promise<void> => {
    setBusy(true);
    setIssues({});
    setBanner(null);
    try {
      // Never logged: this body carries Aadhaar, PAN and the health declaration (NFR-03).
      const response = await createApplication(
        api,
        buildBody(quoteId, kyc, hasCondition, details, isTermLife === true),
      );
      setResult(response);
      // Drop the raw identifiers from memory the moment they are no longer needed.
      setKyc((current) => ({ ...current, aadhaar: '', pan: '' }));
      setDetails('');
    } catch (error) {
      const classified = classifyError(error, 'The application could not be submitted.');
      setResult(null);
      setIssues(classified.fields);
      setBanner(issueText(classified));
    } finally {
      setBusy(false);
    }
  }, [api, quoteId, kyc, hasCondition, details, isTermLife]);

  if (role !== 'CUSTOMER') {
    return (
      <section className="panel" data-testid="not-authorised">
        <h1>Not authorised</h1>
        <p>
          Applying is a customer action. Switch the demo user to Customer in the header — the API
          answers 403 FORBIDDEN for any other role.
        </p>
      </section>
    );
  }

  return (
    <div className="uw-scope" data-testid="apply-page" data-narrow={String(isNarrow)}>
      <div className="page-head">
        <div>
          <h1>Apply</h1>
          <p className="route">
            Route: /apply/<code className="mono">{quoteId === '' ? '—' : quoteId}</code>
          </p>
        </div>
      </div>

      <div className="apply-layout">
        <section className="panel" aria-labelledby="kyc-h">
          <h2 id="kyc-h">Applicant details (KYC)</h2>
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void onSubmit();
            }}
          >
            <KycForm values={kyc} issues={issues} disabled={busy} onChange={onKycChange} />

            {isTermLife === true ? (
              <fieldset className="apply-fieldset">
                <legend>Health declaration</legend>
                <label className="choice" htmlFor="health-condition">
                  <input
                    id="health-condition"
                    data-testid="health-has_pre_existing_condition"
                    type="checkbox"
                    disabled={busy}
                    checked={hasCondition}
                    onChange={(event) => setHasCondition(event.target.checked)}
                  />
                  <span>I have a pre-existing condition</span>
                </label>
                <div className="field">
                  <label htmlFor="health-details">Details</label>
                  <textarea
                    id="health-details"
                    data-testid="health-details"
                    rows={2}
                    disabled={busy}
                    value={details}
                    onChange={(event) => setDetails(event.target.value)}
                  />
                </div>
              </fieldset>
            ) : null}

            {banner !== null ? (
              <div className="alert alert-error" role="alert" data-testid="apply-banner">
                <p>{banner}</p>
                <Link className="btn btn-sm" to="/quote">
                  Get a new quote
                </Link>
              </div>
            ) : null}

            <div className="actions">
              <button
                type="submit"
                className="btn btn-primary"
                data-testid="submit-application"
                disabled={busy || quoteId === ''}
              >
                {busy ? 'Submitting…' : 'Submit application'}
              </button>
            </div>
          </form>
        </section>

        <div className="apply-side">
          <section className="panel" aria-labelledby="apply-quote-h">
            <h2 id="apply-quote-h">Quote</h2>
            {quoteError !== null ? (
              <div className="alert alert-error" role="alert" data-testid="apply-quote-error">
                <p>{quoteError}</p>
              </div>
            ) : null}
            {quote === null ? (
              <p className="empty" data-testid="apply-quote-loading">
                Loading the quote…
              </p>
            ) : (
              <dl className="kv">
                <dt>Quote id</dt>
                <dd>
                  <code className="mono">{quote.quote_id}</code>
                </dd>
                <dt>Product</dt>
                <dd>{quote.product}</dd>
                <dt>Premium</dt>
                <dd className="num" data-testid="apply-premium">
                  {formatMoney(quote.premium, quote.currency)}
                </dd>
                <dt>Rule version</dt>
                <dd>Rule version v{quote.rule_version}</dd>
              </dl>
            )}
          </section>

          <section className="panel" aria-labelledby="apply-decision-h" aria-live="polite">
            <h2 id="apply-decision-h">Decision</h2>
            {result === null ? (
              <p className="empty" data-testid="apply-decision-empty">
                Submit the application to see the underwriting decision.
              </p>
            ) : (
              <div data-testid="application-result">
                <div className="big-status">
                  <StatusBadge status={result.decision} />
                  {result.status === result.decision ? null : (
                    <>
                      <span className="small muted">application status</span>
                      <span className="badge-secondary">{result.status}</span>
                    </>
                  )}
                </div>
                <dl className="kv">
                  <dt>Application id</dt>
                  <dd>
                    <code className="mono">{result.application_id}</code>
                  </dd>
                  <dt>Rule version</dt>
                  <dd>Rule version v{result.rule_version}</dd>
                  <dt>Aadhaar</dt>
                  <dd className="mono" data-testid="aadhaar-masked">
                    {result.kyc.aadhaar_masked}
                  </dd>
                  <dt>PAN</dt>
                  <dd className="mono" data-testid="pan-masked">
                    {result.kyc.pan_masked}
                  </dd>
                </dl>
                <h3>Reason codes</h3>
                <ReasonCodeList codes={result.reason_codes} reasons={result.reasons} />
                {result.decision === 'AUTO_BIND' ? (
                  <div className="actions">
                    <Link
                      className="btn btn-primary"
                      to={`/policies?application=${result.application_id}`}
                      data-testid="issue-policy"
                    >
                      Issue policy
                    </Link>
                  </div>
                ) : result.decision === 'MANUAL_REVIEW' ? (
                  <p className="small">
                    An underwriter will review this application. You will be able to issue the policy
                    once it is approved.
                  </p>
                ) : (
                  <p className="small">
                    This application cannot be issued. An admin may review declined applications.
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
