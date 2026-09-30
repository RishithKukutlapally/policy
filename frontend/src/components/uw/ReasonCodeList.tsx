/**
 * Reason codes with the description from the case's rule version (AC-04).
 *
 * Descriptions come from the API (`reasons[]`) or from the rule version's `reason_codes` map — never
 * from a hardcoded table in the UI.
 */
import type { ReasonDetail } from '../../types/applications';
import './uw.css';

export interface ReasonCodeListProps {
  readonly codes: readonly string[];
  readonly reasons?: readonly ReasonDetail[];
  readonly descriptions?: Readonly<Record<string, string>>;
  readonly testId?: string;
  readonly emptyText?: string;
}

function describe(
  code: string,
  reasons: readonly ReasonDetail[],
  descriptions: Readonly<Record<string, string>>,
): string | null {
  const fromApi = reasons.find((reason) => reason.code === code)?.description;
  return fromApi ?? descriptions[code] ?? null;
}

export function ReasonCodeList({
  codes,
  reasons = [],
  descriptions = {},
  testId = 'reason-codes',
  emptyText = 'No reason codes — no underwriting rule matched.',
}: ReasonCodeListProps): JSX.Element {
  if (codes.length === 0) {
    return (
      <p className="small muted" data-testid={`${testId}-empty`}>
        {emptyText}
      </p>
    );
  }
  return (
    <ul className="reason-list" data-testid={testId}>
      {codes.map((code) => {
        const description = describe(code, reasons, descriptions);
        return (
          <li key={code}>
            <code>{code}</code>
            {description === null ? null : ` — ${description}`}
          </li>
        );
      })}
    </ul>
  );
}
