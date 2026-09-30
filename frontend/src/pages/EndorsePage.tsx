/**
 * Endorse — story E6-S3 (AC-06, AC-16, AC-10, AC-22, AC-24), route `/policies/:policyNumber/endorse`.
 *
 * The type selector is limited to the policy's own rule version's `endorsement.allowed_types`
 * (`useAllowedTypes`), and the form waits for that list so a disallowed option is never offered.
 * "Preview" posts `?preview=true` and persists nothing; the signed pro-rated delta it shows is the
 * server's decimal string (NFR-01). After a 201 the screen re-reads the policy so the confirmation shows
 * the real append-only history row (NFR-02).
 */
import { useCallback, useMemo, useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { createEndorsement, previewEndorsement } from '../api/endorsements';
import { getPolicy } from '../api/policies';
import { useRole } from '../app/RoleContext';
import { FieldError } from '../components/FieldError';
import { NotAuthorised } from '../components/NotAuthorised';
import { EndorsementDone } from '../components/endorse/EndorsementDone';
import { EMPTY_DRAFT, EndorsementFields } from '../components/endorse/EndorsementFields';
import type { EndorsementDraft } from '../components/endorse/EndorsementFields';
import { PreviewPanel } from '../components/endorse/PreviewPanel';
import { useAllowedTypes } from '../components/endorse/useAllowedTypes';
import { PolicyFactsPanel } from '../components/lifecycle/PolicyFactsPanel';
import { PolicyNotFound } from '../components/lifecycle/PolicyNotFound';
import { usePolicyLoad } from '../components/lifecycle/usePolicyLoad';
import { StatusBadge } from '../components/StatusBadge';
import { classifyError, issueText } from '../lib/apiIssues';
import { ENDORSEMENT_LABELS } from '../types/endorsements';
import type { EndorsementPreview, EndorsementRequest, NomineeRelationship } from '../types/endorsements';
import type { EndorsementType, PolicyDetail } from '../types/policies';
import { PRODUCT_NAMES } from '../types/policies';
import '../components/lifecycle/lifecycle.css';
import './EndorsePage.css';

/** Builds the discriminated request body from the draft — only the chosen type's fields are sent. */
function toRequest(type: EndorsementType, draft: EndorsementDraft): EndorsementRequest {
  if (type === 'CHANGE_ADDRESS') return { type, address: draft.address.trim() };
  if (type === 'ADD_NOMINEE') {
    return {
      type,
      nominee_name: draft.nominee_name.trim(),
      relationship: draft.relationship as NomineeRelationship,
      share_percent: draft.share_percent.trim(),
    };
  }
  return { type, new_sum_insured: draft.new_sum_insured.trim() };
}

export function EndorsePage(): JSX.Element {
  const { policyNumber = '' } = useParams<{ policyNumber: string }>();
  const { api, role } = useRole();
  const mayEndorse = role === 'CUSTOMER' || role === 'ADMIN';

  const { policy, loading, notFound, error: loadError } = usePolicyLoad(policyNumber, mayEndorse);
  const { types: allowedTypes, ready: typesReady } = useAllowedTypes(policy);

  const [type, setType] = useState<EndorsementType>('CHANGE_ADDRESS');
  const [draft, setDraft] = useState<EndorsementDraft>(EMPTY_DRAFT);
  const [preview, setPreview] = useState<EndorsementPreview | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Readonly<Record<string, string>>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ delta: string; type: EndorsementType } | null>(null);
  const [endorsed, setEndorsed] = useState<PolicyDetail | null>(null);

  // Keep the selected type inside the allowed list once the rule file has been read.
  useEffect(() => {
    setType((current) => (allowedTypes.includes(current) ? current : (allowedTypes[0] ?? current)));
  }, [allowedTypes]);

  const currency = policy?.currency ?? 'INR';

  const reset = useCallback((): void => {
    setPreview(null);
    setFieldErrors({});
    setBanner(null);
  }, []);

  const onChange = useCallback((name: keyof EndorsementDraft, value: string): void => {
    setDraft((current) => ({ ...current, [name]: value }));
    setPreview(null);
  }, []);

  const handleFailure = useCallback((caught: unknown): void => {
    const issues = classifyError(caught, 'The endorsement could not be saved.');
    setFieldErrors(issues.fields);
    setBanner(issueText(issues));
    setPreview(null);
  }, []);

  const onPreview = useCallback(async (): Promise<void> => {
    reset();
    setBusy(true);
    try {
      setPreview(await previewEndorsement(api, policyNumber, toRequest(type, draft)));
    } catch (caught) {
      handleFailure(caught);
    } finally {
      setBusy(false);
    }
  }, [api, policyNumber, type, draft, reset, handleFailure]);

  const onSubmit = useCallback(async (): Promise<void> => {
    reset();
    setBusy(true);
    try {
      const result = await createEndorsement(api, policyNumber, toRequest(type, draft));
      setDone({ delta: result.premium_delta, type: result.type });
      // Re-read the policy so the history row shown is the persisted one (NFR-02).
      try {
        setEndorsed(await getPolicy(api, policyNumber));
      } catch {
        setEndorsed(null);
      }
    } catch (caught) {
      handleFailure(caught);
    } finally {
      setBusy(false);
    }
  }, [api, policyNumber, type, draft, reset, handleFailure]);

  const typeOptions = useMemo(
    () => allowedTypes.map((value) => ({ value, label: `${value} — ${ENDORSEMENT_LABELS[value]}` })),
    [allowedTypes],
  );

  if (!mayEndorse) return <NotAuthorised allowed={['Customer', 'Admin']} />;
  if (notFound) return <PolicyNotFound policyNumber={policyNumber} />;
  // The form waits for the rule file too: AC-16 requires the selector to list only allowed types.
  if (loading || (policy !== null && !typesReady)) {
    return (
      <p className="muted" role="status">
        Loading policy…
      </p>
    );
  }
  if (policy === null) {
    return (
      <section className="panel">
        <h1>Endorse policy</h1>
        <div className="alert alert-error" role="alert" data-testid="endorse-error">
          <p>{loadError ?? 'The policy could not be loaded.'}</p>
        </div>
      </section>
    );
  }

  if (done !== null) {
    return (
      <EndorsementDone
        policyNumber={policy.policy_number}
        type={done.type}
        premiumDelta={done.delta}
        currency={currency}
        endorsed={endorsed}
      />
    );
  }

  return (
    <div className="endorse-page">
      <p>
        <Link to={`/policies/${policy.policy_number}`}>← Back to Policy Detail</Link>
      </p>
      <div className="page-head">
        <div>
          <h1>
            Endorse {policy.policy_number} <StatusBadge status={policy.status} />
          </h1>
          <p className="route">
            {PRODUCT_NAMES[policy.product]} · rule version v{policy.rule_version}
          </p>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel" aria-labelledby="endorse-h">
          <h2 id="endorse-h">Change request</h2>
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void onSubmit();
            }}
          >
            <div className="field endorse-type">
              <label htmlFor="endorsement-type">Endorsement type</label>
              <span className="hint" id="endorsement-type-hint">
                Allowed by rule version v{policy.rule_version}
              </span>
              <select
                id="endorsement-type"
                name="type"
                className="lc-select"
                value={type}
                disabled={busy}
                data-testid="endorsement-type"
                aria-describedby="endorsement-type-hint"
                aria-invalid={fieldErrors.type === undefined ? undefined : true}
                onChange={(event) => {
                  setType(event.target.value as EndorsementType);
                  reset();
                }}
              >
                {typeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <FieldError name="type" code={fieldErrors.type ?? null} />
            </div>

            <EndorsementFields
              type={type}
              draft={draft}
              policy={policy}
              fieldErrors={fieldErrors}
              disabled={busy}
              onChange={onChange}
            />

            {type === 'CHANGE_SUM_INSURED' ? (
              <>
                <div className="actions">
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    data-testid="preview"
                    onClick={() => void onPreview()}
                  >
                    Preview premium change
                  </button>
                </div>
                {preview === null ? null : (
                  <PreviewPanel
                    preview={preview}
                    currentPremium={policy.premium}
                    currency={currency}
                  />
                )}
              </>
            ) : null}

            {banner === null ? null : (
              <div className="alert alert-error" role="alert" data-testid="endorse-error">
                <p>{banner}</p>
              </div>
            )}

            <div className="actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy}
                data-testid="submit-endorsement"
              >
                {busy ? 'Saving…' : 'Submit endorsement'}
              </button>
              <Link className="btn" to={`/policies/${policy.policy_number}`}>
                Cancel
              </Link>
            </div>
          </form>
        </section>

        <PolicyFactsPanel
          policy={policy}
          footnote="Premium deltas are pro-rated for the unused part of the term by the server and recorded on the endorsement; they are not collected now."
          extra={
            <>
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
            </>
          }
        />
      </div>
    </div>
  );
}
