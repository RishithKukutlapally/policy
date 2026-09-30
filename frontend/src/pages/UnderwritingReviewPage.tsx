/**
 * Underwriting Review — story E4-S5 (AC-09, AC-24), route `/admin/underwriting`, ADMIN.
 *
 * Lists the queue (DECLINED by default) and overrides a decline through
 * `POST …/override`: exactly one reason code from the case's own rule version plus a comment of at
 * least 10 characters, audited as `UW_OVERRIDE_DECLINE` with the admin's actor id (NFR-04).
 */
import { useCallback, useEffect, useState } from 'react';
import { fetchReasonCodes, getQueue, submitOverride } from '../api/underwriting';
import { OverrideDialog } from '../components/uw/OverrideDialog';
import { QueueView } from '../components/uw/QueueView';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { classifyError, issueText } from '../lib/apiIssues';
import { shortId } from '../lib/maskPii';
import type { OverrideRequest, QueueItem, QueueStatus } from '../types/applications';
import './UnderwritingReviewPage.css';

type Filter = QueueStatus | 'ALL';

const FILTER_LABELS: Readonly<Record<Filter, string>> = {
  DECLINED: 'DECLINED',
  MANUAL_REVIEW: 'MANUAL_REVIEW',
  ALL: 'All (MANUAL_REVIEW + DECLINED)',
};

export function UnderwritingReviewPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();

  const [filter, setFilter] = useState<Filter>('DECLINED');
  const [items, setItems] = useState<readonly QueueItem[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [target, setTarget] = useState<QueueItem | null>(null);
  const [reasonCodes, setReasonCodes] = useState<Readonly<Record<string, string>>>({});
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isAdmin = role === 'ADMIN';

  const loadQueue = useCallback(async (): Promise<void> => {
    try {
      setItems(await getQueue(api, filter === 'ALL' ? undefined : filter));
      setQueueError(null);
    } catch (error) {
      setQueueError(issueText(classifyError(error, 'The queue could not be loaded.')));
    }
  }, [api, filter]);

  useEffect(() => {
    if (!isAdmin) return;
    void loadQueue();
  }, [isAdmin, loadQueue]);

  const openOverride = useCallback(
    async (item: QueueItem): Promise<void> => {
      setTarget(item);
      setOverrideError(null);
      setReasonCodes(await fetchReasonCodes(api, item.product, item.rule_version));
    },
    [api],
  );

  const doOverride = useCallback(
    async (body: OverrideRequest): Promise<void> => {
      if (target === null) return;
      setBusy(true);
      setOverrideError(null);
      try {
        const result = await submitOverride(api, target.application_id, body);
        setTarget(null);
        setNotice(
          `Application ${shortId(result.application_id)}… overridden to ${result.status} by ${result.override.actor_id}.`,
        );
        await loadQueue();
      } catch (error) {
        setOverrideError(issueText(classifyError(error, 'The override could not be recorded.')));
      } finally {
        setBusy(false);
      }
    },
    [api, target, loadQueue],
  );

  if (!isAdmin) {
    return (
      <section className="panel" data-testid="not-authorised">
        <h1>Not authorised</h1>
        <p>
          Overriding a decline is an admin action. Switch the demo user to Admin in the header — the API
          answers 403 FORBIDDEN for any other role.
        </p>
      </section>
    );
  }

  return (
    <div className="uw-scope" data-testid="underwriting-review-page" data-narrow={String(isNarrow)}>
      <div className="page-head">
        <div>
          <h1>Underwriting Review</h1>
          <p className="route">Route: /admin/underwriting · queue review and DECLINE override</p>
        </div>
        <div className="field review-filter">
          <label htmlFor="queue-status-filter">Show</label>
          <select
            id="queue-status-filter"
            data-testid="queue-status-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value as Filter)}
          >
            {(['ALL', 'DECLINED', 'MANUAL_REVIEW'] as readonly Filter[]).map((value) => (
              <option key={value} value={value}>
                {FILTER_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {queueError !== null ? (
        <div className="alert alert-error" role="alert" data-testid="queue-error">
          <p>{queueError}</p>
        </div>
      ) : null}
      {notice !== null ? (
        <div className="alert alert-ok" role="status" data-testid="override-notice">
          <p>{notice}</p>
        </div>
      ) : null}

      <section className="panel" aria-labelledby="review-queue-h">
        <h2 id="review-queue-h">Underwriting queue</h2>
        <QueueView
          items={items}
          caption="Underwriting queue, oldest first"
          emptyText={
            filter === 'DECLINED' ? 'No declined applications.' : 'No applications in the queue.'
          }
          isNarrow={isNarrow}
          renderAction={(item) =>
            item.status === 'DECLINED' ? (
              <button
                type="button"
                className="btn btn-sm btn-primary"
                data-testid="case-override"
                data-case-id={item.application_id}
                aria-label={`Override decline ${shortId(item.application_id)}`}
                onClick={() => void openOverride(item)}
              >
                Override
              </button>
            ) : (
              <span className="small muted">Awaiting underwriter</span>
            )
          }
        />
      </section>

      {target === null ? null : (
        <OverrideDialog
          item={target}
          reasonCodes={reasonCodes}
          busy={busy}
          error={overrideError}
          onSubmit={(body) => void doOverride(body)}
          onCancel={() => setTarget(null)}
        />
      )}
    </div>
  );
}
