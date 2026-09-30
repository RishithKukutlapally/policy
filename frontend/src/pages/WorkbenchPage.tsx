/**
 * Underwriter Workbench — story E4-S5 (AC-14, AC-24), route `/underwriter/queue`,
 * UNDERWRITER (ADMIN may look too).
 *
 * The queue is `GET /api/underwriting/queue?status=MANUAL_REVIEW`; opening a case reads the
 * application and its audit trail, and a decision posts to `…/decision`. An approved or declined case
 * leaves the queue, so the queue is re-read after every decision.
 */
import { useCallback, useEffect, useState } from 'react';
import { getApplication } from '../api/applications';
import { fetchReasonCodes, getAudit, getQueue, submitDecision } from '../api/underwriting';
import { CaseDetail } from '../components/uw/CaseDetail';
import { QueueView } from '../components/uw/QueueView';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { classifyError, issueText } from '../lib/apiIssues';
import { shortId } from '../lib/maskPii';
import type {
  ApplicationDetail,
  AuditResponse,
  QueueItem,
  UnderwriterDecision,
} from '../types/applications';
import './WorkbenchPage.css';

export function WorkbenchPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();

  const [items, setItems] = useState<readonly QueueItem[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [reasonCodes, setReasonCodes] = useState<Readonly<Record<string, string>>>({});
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const allowed = role === 'UNDERWRITER' || role === 'ADMIN';

  const loadQueue = useCallback(async (): Promise<void> => {
    try {
      setItems(await getQueue(api, 'MANUAL_REVIEW'));
      setQueueError(null);
    } catch (error) {
      setQueueError(issueText(classifyError(error, 'The queue could not be loaded.')));
    }
  }, [api]);

  useEffect(() => {
    if (!allowed) return;
    void loadQueue();
  }, [allowed, loadQueue]);

  const openCase = useCallback(
    async (item: QueueItem): Promise<void> => {
      setDetailLoading(true);
      setAuditLoading(true);
      setDecisionError(null);
      setAudit(null);
      try {
        setDetail(await getApplication(api, item.application_id));
      } catch (error) {
        setDetail(null);
        setQueueError(issueText(classifyError(error, 'The case could not be loaded.')));
      } finally {
        setDetailLoading(false);
      }
      try {
        setAudit(await getAudit(api, item.application_id));
      } finally {
        setAuditLoading(false);
      }
      setReasonCodes(await fetchReasonCodes(api, item.product, item.rule_version));
    },
    [api],
  );

  const decide = useCallback(
    async (
      decision: UnderwriterDecision,
      codes: readonly string[],
      comment: string,
    ): Promise<void> => {
      if (detail === null) return;
      setBusy(true);
      setDecisionError(null);
      try {
        await submitDecision(api, detail.application_id, {
          decision,
          reason_codes: codes,
          comment,
        });
        await loadQueue();
        setDetail(await getApplication(api, detail.application_id));
        setAudit(await getAudit(api, detail.application_id));
      } catch (error) {
        setDecisionError(issueText(classifyError(error, 'The decision could not be recorded.')));
      } finally {
        setBusy(false);
      }
    },
    [api, detail, loadQueue],
  );

  if (!allowed) {
    return (
      <section className="panel" data-testid="not-authorised">
        <h1>Not authorised</h1>
        <p>
          The Workbench is an underwriter screen. Switch the demo user in the header — the API answers
          403 FORBIDDEN for a customer.
        </p>
      </section>
    );
  }

  return (
    <div className="uw-scope" data-testid="workbench-page" data-narrow={String(isNarrow)}>
      <div className="page-head">
        <div>
          <h1>Workbench</h1>
          <p className="route">Route: /underwriter/queue · manual review queue</p>
        </div>
      </div>

      {queueError !== null ? (
        <div className="alert alert-error" role="alert" data-testid="queue-error">
          <p>{queueError}</p>
        </div>
      ) : null}

      <div className="wb-layout">
        <section className="panel" aria-labelledby="wb-queue-h">
          <h2 id="wb-queue-h">Manual review queue</h2>
          <QueueView
            items={items}
            caption="Manual review cases, oldest first"
            emptyText="No cases awaiting manual review."
            isNarrow={isNarrow}
            renderAction={(item) => (
              <button
                type="button"
                className="btn btn-sm"
                data-testid="case-open"
                data-case-id={item.application_id}
                aria-label={`Open case ${shortId(item.application_id)}`}
                onClick={() => void openCase(item)}
              >
                Open
              </button>
            )}
          />
        </section>

        <section className="panel" aria-labelledby="wb-case-h">
          <h2 id="wb-case-h">Case detail</h2>
          <CaseDetail
            detail={detail}
            loading={detailLoading}
            audit={audit}
            auditLoading={auditLoading}
            reasonCodes={reasonCodes}
            busy={busy}
            error={decisionError}
            onDecide={(decision, codes, comment) => void decide(decision, codes, comment)}
          />
        </section>
      </div>
    </div>
  );
}
