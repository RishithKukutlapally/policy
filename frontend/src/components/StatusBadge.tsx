/** Status badge: the status text plus a shape modifier — never colour alone (AC-24 / a11y). */
export interface StatusBadgeProps {
  readonly status: string;
  readonly label?: string;
  /**
   * Playwright hook. Defaults to `status-badge` (the policy status); a screen showing more than one
   * badge gives the secondary ones their own hook, e.g. `payment-status`, so a test can target each.
   */
  readonly testId?: string;
}

export function StatusBadge({
  status,
  label,
  testId = 'status-badge',
}: StatusBadgeProps): JSX.Element {
  return (
    <span className={`badge b-${status}`} data-testid={testId} data-status={status}>
      {label ?? status}
    </span>
  );
}
