/**
 * The result of one end-of-day run (story E7-S4, contract §2.25).
 *
 * The job is idempotent per `as_of`: a repeat run returns all-zero counts (AC-18), which this view
 * calls out explicitly so an operator can tell "nothing to do" apart from "nothing happened". Every
 * figure is the server's — the screen adds nothing up.
 */
import { endOfDayCounts } from '../../types/renewal';
import type { EndOfDayResult } from '../../types/renewal';
import { StatusBadge } from '../StatusBadge';

export interface EndOfDayResultViewProps {
  readonly result: EndOfDayResult;
  /** How many times this `as_of` has been run in this session; > 1 means the zeros are expected. */
  readonly runCount: number;
  readonly actorId: string;
}

export function EndOfDayResultView({
  result,
  runCount,
  actorId,
}: EndOfDayResultViewProps): JSX.Element {
  return (
    <div data-testid="eod-result">
      <p className="small">
        As of <strong className="num">{result.as_of}</strong> · run {runCount} for this date · audited as{' '}
        <code>RUN_END_OF_DAY</code> by <code>{actorId}</code>
      </p>

      <div className="lc-cards">
        {endOfDayCounts(result).map((count) => (
          <div className="lc-stat" key={count.testId}>
            <p className="lbl">{count.label}</p>
            <p className="val" data-testid={count.testId}>
              {count.label}: {count.value}
            </p>
          </div>
        ))}
      </div>

      {runCount > 1 ? (
        <div className="alert" role="status">
          <p>This date was already processed — nothing left to do (the job is idempotent).</p>
        </div>
      ) : null}

      {result.renewed_policies.length === 0 ? null : (
        <section aria-labelledby="eod-renewed-h">
          <h3 id="eod-renewed-h">Renewed</h3>
          <ul className="eod-list" data-testid="eod-renewed">
            {result.renewed_policies.map((pair) => (
              <li key={pair.from}>
                <code>{pair.from}</code> <StatusBadge status="RENEWED" testId="eod-renewed-status" /> →{' '}
                <code>{pair.to}</code>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.lapsed_policies.length === 0 ? null : (
        <section aria-labelledby="eod-lapsed-h">
          <h3 id="eod-lapsed-h">Lapsed</h3>
          <ul className="eod-list" data-testid="eod-lapsed">
            {result.lapsed_policies.map((number) => (
              <li key={number}>
                <code>{number}</code> · grace period expired
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.failed_policies.length === 0 ? null : (
        <div className="alert alert-error" role="alert" data-testid="eod-failures">
          <p>
            <strong>Failed: {result.failed}</strong> — the other policies were still processed.
          </p>
          <ul>
            {result.failed_policies.map((failure) => (
              <li key={failure.policy_number}>
                <code>{failure.policy_number}</code> — {failure.error}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
