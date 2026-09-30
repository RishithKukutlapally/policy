/**
 * Run end-of-day — story E7-S4 (AC-07, AC-18, NFR-04), route `/admin/end-of-day`, ADMIN only.
 *
 * `POST /api/admin/end-of-day` renews paid policies and lapses unpaid ones past their grace period, and
 * writes one `RUN_END_OF_DAY` audit row per run with the acting admin (§2.25). The job is idempotent per
 * `as_of`, so re-running a processed date legitimately returns zero counts (AC-18) — the result view
 * says so rather than leaving the operator guessing.
 */
import { useCallback, useRef, useState } from 'react';
import { runEndOfDay } from '../api/renewal';
import { useRole } from '../app/RoleContext';
import { EndOfDayResultView } from '../components/admin/EndOfDayResultView';
import { FieldError } from '../components/FieldError';
import { NotAuthorised } from '../components/NotAuthorised';
import { classifyError, issueText } from '../lib/apiIssues';
import type { EndOfDayResult } from '../types/renewal';
import '../components/lifecycle/lifecycle.css';
import './EndOfDayPage.css';

/** Today in the browser's timezone, used only as the date field's starting value. */
function localToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

export function EndOfDayPage(): JSX.Element {
  const { api, role, actorId } = useRole();
  const [asOf, setAsOf] = useState<string>(localToday);
  const [result, setResult] = useState<EndOfDayResult | null>(null);
  const [runCount, setRunCount] = useState(0);
  const [banner, setBanner] = useState<string | null>(null);
  const [fieldCode, setFieldCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** How many times each date has been run in this session, so the zeros can be explained. */
  const runs = useRef<Map<string, number>>(new Map());

  const onRun = useCallback(async (): Promise<void> => {
    setBanner(null);
    setFieldCode(null);
    setBusy(true);
    try {
      const next = await runEndOfDay(api, asOf);
      const count = (runs.current.get(asOf) ?? 0) + 1;
      runs.current.set(asOf, count);
      setResult(next);
      setRunCount(count);
    } catch (caught) {
      const issues = classifyError(caught, 'The end-of-day run could not be started.');
      setFieldCode(issues.fields.as_of ?? null);
      setBanner(issueText(issues));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }, [api, asOf]);

  if (role !== 'ADMIN') return <NotAuthorised allowed={['Admin']} />;

  return (
    <div className="eod-page">
      <div className="page-head">
        <div>
          <h1>Run end-of-day</h1>
          <p className="route">
            Renews paid policies and lapses unpaid ones once their grace period has ended.
          </p>
        </div>
      </div>

      <section className="panel" aria-labelledby="eod-h">
        <h2 id="eod-h">Run</h2>
        <form
          className="lc-toolbar"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void onRun();
          }}
        >
          <div className="field eod-date">
            <label htmlFor="eod-as-of">As of</label>
            <input
              type="date"
              id="eod-as-of"
              name="as_of"
              className="lc-input"
              value={asOf}
              disabled={busy}
              data-testid="eod-as-of"
              aria-invalid={fieldCode === null ? undefined : true}
              aria-describedby={fieldCode === null ? undefined : 'as_of-error'}
              onChange={(event) => setAsOf(event.target.value)}
            />
            <FieldError name="as_of" code={fieldCode} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy} data-testid="run-eod">
            {busy ? 'Running…' : 'Run end-of-day'}
          </button>
        </form>

        {banner === null ? null : (
          <div className="alert alert-error" role="alert" data-testid="eod-error">
            <p>{banner}</p>
          </div>
        )}
      </section>

      <section className="panel" aria-labelledby="eod-res-h" aria-live="polite">
        <h2 id="eod-res-h">Result</h2>
        {result === null ? (
          <div className="empty" data-testid="eod-empty">
            No run yet in this session.
          </div>
        ) : (
          <EndOfDayResultView result={result} runCount={runCount} actorId={actorId} />
        )}
      </section>
    </div>
  );
}
