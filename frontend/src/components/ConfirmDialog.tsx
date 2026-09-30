/**
 * Accessible confirm dialog: `role="dialog"`, `aria-modal`, focus moved to the confirm button on
 * open and restored on close, Escape cancels.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

export interface ConfirmDialogProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly confirmLabel: string;
  readonly cancelLabel?: string;
  readonly busy?: boolean;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
  readonly testId?: string;
  /** Playwright hooks for the two buttons; the defaults keep the catalog publish dialog unchanged. */
  readonly confirmTestId?: string;
  readonly cancelTestId?: string;
  /** Label while `busy` is true. */
  readonly busyLabel?: string;
}

export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  cancelLabel = 'Cancel',
  busy = false,
  onConfirm,
  onCancel,
  testId = 'confirm-dialog',
  confirmTestId = 'publish-confirm',
  cancelTestId = 'publish-cancel',
  busyLabel = 'Publishing…',
}: ConfirmDialogProps): JSX.Element {
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  const openerRef = useRef<Element | null>(null);

  useEffect(() => {
    openerRef.current = document.activeElement;
    confirmRef.current?.focus();
    const opener = openerRef.current;
    return () => {
      if (opener instanceof HTMLElement) opener.focus();
    };
  }, []);

  const onKeyDown = useCallback(
    (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onCancel();
      }
    },
    [onCancel],
  );

  useEffect(() => {
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onKeyDown]);

  return (
    <div className="dlg-backdrop" data-testid={`${testId}-backdrop`}>
      <div
        className="dlg"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${testId}-title`}
        data-testid={testId}
      >
        <div className="dlg-body">
          <h2 id={`${testId}-title`}>{title}</h2>
          {children}
        </div>
        <div className="dlg-foot">
          <button type="button" className="btn" onClick={onCancel} data-testid={cancelTestId}>
            {cancelLabel}
          </button>
          <button
            type="button"
            ref={confirmRef}
            className="btn btn-primary"
            onClick={onConfirm}
            disabled={busy}
            data-testid={confirmTestId}
          >
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
