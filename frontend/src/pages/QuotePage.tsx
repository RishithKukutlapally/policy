/**
 * Get a Quote — story E3-S3 (AC-01, AC-12, AC-24), route `/quote`, CUSTOMER.
 *
 * Picking a product swaps in that product's canonical risk inputs (docs/conventions.md), submitting
 * calls `POST /api/quotes` and the result panel shows the premium the backend computed. The UI never
 * does money arithmetic: the decimal string is only formatted for display (NFR-01).
 */
import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client';
import { createQuote } from '../api/quotes';
import { QuoteField } from '../components/QuoteField';
import {
  DEFAULT_PRODUCT,
  PRODUCT_LABELS,
  PRODUCT_ORDER,
  buildQuoteRequest,
  defaultsFor,
  fieldsFor,
} from '../components/quoteFields';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { formatMoney } from '../lib/money';
import { isFieldErrorDetails } from '../types/api';
import type { ProductCode, QuoteFormValues, QuoteResponse } from '../types/quotes';
import './QuotePage.css';

interface Banner {
  readonly code: string;
  readonly message: string;
}

function isProductCode(value: string): value is ProductCode {
  return (PRODUCT_ORDER as readonly string[]).includes(value);
}

/** Maps a failure to either inline field issues (422) or a banner (409, 4xx, transport). */
function classify(error: unknown): {
  readonly issues: Readonly<Record<string, string>>;
  readonly banner: Banner | null;
} {
  if (!(error instanceof ApiError)) {
    return { issues: {}, banner: { code: 'UNKNOWN_ERROR', message: 'The quote request failed unexpectedly.' } };
  }
  if (error.code === 'VALIDATION_ERROR' && isFieldErrorDetails(error.details)) {
    const issues: Record<string, string> = {};
    for (const detail of error.details) issues[detail.field] = detail.code;
    return { issues, banner: { code: error.code, message: error.message } };
  }
  return { issues: {}, banner: { code: error.code, message: error.message } };
}

export function QuotePage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();

  const [product, setProduct] = useState<ProductCode>(DEFAULT_PRODUCT);
  const [values, setValues] = useState<QuoteFormValues>(() => defaultsFor(DEFAULT_PRODUCT));
  const [issues, setIssues] = useState<Readonly<Record<string, string>>>({});
  const [banner, setBanner] = useState<Banner | null>(null);
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const fields = useMemo(() => fieldsFor(product), [product]);

  const onProductChange = useCallback((next: string): void => {
    if (!isProductCode(next)) return;
    setProduct(next);
    setValues(defaultsFor(next));
    setIssues({});
    setBanner(null);
    setQuote(null);
  }, []);

  const onFieldChange = useCallback((name: string, value: string): void => {
    setValues((current) => ({ ...current, [name]: value }));
  }, []);

  const onSubmit = useCallback(async (): Promise<void> => {
    setBusy(true);
    setBanner(null);
    setIssues({});
    try {
      // Never logged: quote inputs travel beside KYC answers in later stories (NFR-03).
      setQuote(await createQuote(api, buildQuoteRequest(product, values)));
    } catch (error) {
      const { issues: fieldIssues, banner: failure } = classify(error);
      setQuote(null);
      setIssues(fieldIssues);
      setBanner(failure);
    } finally {
      setBusy(false);
    }
  }, [api, product, values]);

  if (role !== 'CUSTOMER') {
    return (
      <section className="panel" data-testid="not-authorised">
        <h1>Not authorised</h1>
        <p>
          Quoting is a customer action. Switch the demo user to Customer in the header — the API
          answers 403 FORBIDDEN for any other role.
        </p>
      </section>
    );
  }

  return (
    <div data-testid="quote-page" data-narrow={String(isNarrow)}>
      <div className="page-head">
        <div>
          <h1>Get a Quote</h1>
          <p className="route">Route: /quote · premium from the active rule version</p>
        </div>
      </div>

      <div className="quote-layout">
        <section className="panel" aria-labelledby="quote-form-h">
          <h2 id="quote-form-h">Risk details</h2>
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void onSubmit();
            }}
          >
            <fieldset className="quote-fieldset">
              <legend>Product</legend>
              <div className="field">
                <label htmlFor="quote-product">Product</label>
                <select
                  id="quote-product"
                  className="quote-select"
                  data-testid="quote-product"
                  value={product}
                  disabled={busy}
                  onChange={(event) => onProductChange(event.target.value)}
                >
                  {PRODUCT_ORDER.map((code) => (
                    <option key={code} value={code}>
                      {PRODUCT_LABELS[code]}
                    </option>
                  ))}
                </select>
              </div>
            </fieldset>

            <div className="quote-form">
              {fields.map((spec) => (
                <QuoteField
                  key={spec.name}
                  spec={spec}
                  value={values[spec.name] ?? ''}
                  errorCode={issues[spec.name] ?? null}
                  disabled={busy}
                  onChange={onFieldChange}
                />
              ))}
            </div>

            {banner !== null ? (
              <div className="alert alert-error" role="alert" data-testid="quote-banner">
                <p>
                  <strong className="code">{banner.code}</strong> — {banner.message}
                </p>
              </div>
            ) : null}

            <div className="actions">
              <button type="submit" className="btn btn-primary" data-testid="quote-submit" disabled={busy}>
                {busy ? 'Getting quote…' : 'Get quote'}
              </button>
            </div>
          </form>
        </section>

        <section className="panel" aria-labelledby="quote-result-h">
          <h2 id="quote-result-h">Your quote</h2>
          {busy ? (
            <p className="quote-loading" data-testid="quote-loading">
              Contacting the quote service…
            </p>
          ) : null}
          {!busy && quote === null ? (
            <p className="empty" data-testid="quote-empty">
              No quote yet. Fill in the risk details and choose “Get quote”.
            </p>
          ) : null}
          {!busy && quote !== null ? (
            <div role="status" data-testid="quote-result">
              <p className="small muted">{PRODUCT_LABELS[quote.product]} · annual premium</p>
              <p className="quote-premium" data-testid="quote-premium">
                {formatMoney(quote.premium, quote.currency)}
              </p>
              <dl className="kv">
                <dt>Rule version</dt>
                <dd data-testid="quote-rule-version">Rule version v{quote.rule_version}</dd>
                <dt>Sum insured</dt>
                <dd>{formatMoney(quote.sum_insured, quote.currency)}</dd>
                <dt>Quote id</dt>
                <dd>
                  <code className="mono">{quote.quote_id}</code>
                </dd>
              </dl>
              <div className="actions">
                <Link
                  className="btn btn-primary"
                  to={`/apply?quote=${quote.quote_id}`}
                  data-testid="quote-apply"
                >
                  Apply
                </Link>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
