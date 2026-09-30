/**
 * Audit trail of one application (§2.15): every action with the actor that performed it — the
 * automatic decision shows `decided_by SYSTEM`, an underwriter action reads `UW_APPROVE by uw-001`
 * (AC-14, NFR-04). Comments are shown; no PII is present in `detail`.
 */
import type { AuditResponse, DecisionRow } from '../../types/applications';
import './uw.css';

export interface AuditTrailProps {
  readonly audit: AuditResponse | null;
  readonly loading: boolean;
}

interface Entry {
  readonly key: string;
  readonly action: string;
  readonly actor: string;
  readonly role: string | null;
  readonly summary: string;
  readonly at: string;
  readonly comment: string | null;
}

function decisionEntry(row: DecisionRow): Entry {
  const automatic = row.decided_by === 'SYSTEM';
  return {
    key: `decision-${row.decision_id}`,
    action: automatic ? `AUTO_${row.decision}` : `UW_${row.decision === 'DECLINE' ? 'DECLINE' : 'APPROVE'}`,
    actor: row.decided_by,
    role: automatic ? null : 'UNDERWRITER',
    summary: `${row.reason_codes.join(', ') || 'no reason codes'} · rule version v${row.rule_version}`,
    at: row.created_at,
    comment: row.comment,
  };
}

function toEntries(audit: AuditResponse): readonly Entry[] {
  const fromRecords = audit.audit_records.map((record, index) => ({
    key: `record-${index}-${record.created_at}`,
    action: record.action,
    actor: record.actor_id,
    role: record.actor_role,
    summary: record.entity_type,
    at: record.created_at,
    comment: typeof record.detail?.['comment'] === 'string' ? (record.detail['comment'] as string) : null,
  }));
  const systemDecisions = audit.decisions.filter((row) => row.decided_by === 'SYSTEM').map(decisionEntry);
  return [...systemDecisions, ...fromRecords].sort((a, b) => a.at.localeCompare(b.at));
}

export function AuditTrail({ audit, loading }: AuditTrailProps): JSX.Element {
  if (loading) {
    return (
      <p className="small muted" data-testid="audit-loading">
        Loading the audit trail…
      </p>
    );
  }
  const entries = audit === null ? [] : toEntries(audit);
  if (entries.length === 0) {
    return (
      <p className="small muted" data-testid="audit-empty">
        No audited actions yet.
      </p>
    );
  }
  return (
    <ol className="timeline" data-testid="audit-trail">
      {entries.map((entry) => (
        <li key={entry.key}>
          <strong>
            <code>{entry.action}</code>
          </strong>{' '}
          {entry.role === null ? 'decided_by ' : 'by '}
          <code>{entry.actor}</code>
          {entry.role === null ? null : ` (${entry.role})`} · {entry.summary}
          <br />
          <span className="small muted">
            {entry.at.replace('T', ' ').replace('Z', '')}
            {entry.comment === null ? null : ` · comment: “${entry.comment}”`}
          </span>
        </li>
      ))}
    </ol>
  );
}
