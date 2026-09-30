/**
 * Admin override of a DECLINED application (AC-09).
 *
 * Submit stays disabled until a reason code from the case's own rule version is chosen and the
 * comment reaches 10 characters (§2.14). `role="dialog"` + `aria-modal`, Escape cancels, focus is
 * trapped inside the dialog and restored to the opener on close.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { shortId } from '../../lib/maskPii';
import type { OverrideRequest, QueueItem } from '../../types/applications';
import './uw.css';

export const MIN_COMMENT_LENGTH = 10;

export interface OverrideDialogProps {
  readonly item: QueueItem;
  readonly reasonCodes: Readonly<Record<string, string>>;
  readonly busy: boolean;
  /** Rendered inside the dialog, e.g. a 422 `UNKNOWN_REASON_CODE`. */
  readonly error: string | null;
  readonly onSubmit: (body: OverrideRequest) => void;
  readonly onCancel: () => void;
}

const FOCUSABLE = 'button:not([disabled]), select, textarea, input, [href]';

export function OverrideDialog({
  item,
  reasonCodes,
  busy,
  error,
  onSubmit,
  onCancel,
}: OverrideDialogProps): JSX.Element {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const openerRef = useRef<Element | null>(null);
  const [reasonCode, setReasonCode] = useState('');
  const [comment, setComment] = useState('');

  const options = useMemo(() => Object.entries(reasonCodes), [reasonCodes]);
  const trimmed = comment.trim();
  const canSubmit = reasonCode !== '' && trimmed.length >= MIN_COMMENT_LENGTH && !busy;

  useEffect(() => {
    openerRef.current = document.activeElement;
    const opener = openerRef.current;
    dialogRef.current?.querySelector<HTMLElement>('select')?.focus();
    return () => {
      if (opener instanceof HTMLElement) opener.focus();
    };
  }, []);

  const onKeyDown = useCallback(
    (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onCancel();
        return;
      }
      if (event.key !== 'Tab') return;
      const nodes = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (nodes === undefined || nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (first === undefined || last === undefined) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onCancel],
  );

  useEffect(() => {
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onKeyDown]);

  return (
    <div className="dlg-backdrop" data-testid="override-dialog-backdrop">
      <div
        className="dlg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="override-dialog-title"
        data-testid="override-dialog"
        ref={dialogRef}
      >
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit) onSubmit({ reason_code: reasonCode, comment: trimmed });
          }}
        >
          <div className="dlg-body">
            <h2 id="override-dialog-title">Override DECLINE</h2>
            <p className="small">
              Application <code className="mono">{shortId(item.application_id)}…</code> · moves the
              application from <strong>DECLINED</strong> to <strong>AUTO_BIND</strong>. Audited as{' '}
              <code>UW_OVERRIDE_DECLINE</code> with your actor id.
            </p>
            <div className="field">
              <label htmlFor="override-reason">Reason code</label>
              <select
                id="override-reason"
                data-testid="override-reason"
                value={reasonCode}
                disabled={busy}
                onChange={(event) => setReasonCode(event.target.value)}
              >
                <option value="">Select a reason code</option>
                {options.map(([code, description]) => (
                  <option key={code} value={code}>
                    {code} — {description}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="override-comment">Comment</label>
              <span className="hint" id="override-comment-hint">
                At least {MIN_COMMENT_LENGTH} characters. Stored in the audit record.
              </span>
              <textarea
                id="override-comment"
                rows={3}
                data-testid="override-comment"
                value={comment}
                disabled={busy}
                aria-describedby="override-comment-hint override-comment-count"
                onChange={(event) => setComment(event.target.value)}
              />
              <span className="counter" id="override-comment-count">
                {trimmed.length} / {MIN_COMMENT_LENGTH} characters minimum
              </span>
            </div>
            {error === null ? null : (
              <div className="alert alert-error" role="alert" data-testid="override-error">
                <p>{error}</p>
              </div>
            )}
          </div>
          <div className="dlg-foot">
            <button
              type="button"
              className="btn"
              onClick={onCancel}
              data-testid="override-cancel"
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              data-testid="override-submit"
              disabled={!canSubmit}
            >
              {busy ? 'Overriding…' : 'Override to AUTO_BIND'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
