/**
 * Turns a failed request into what the screen shows: inline 422 field issues plus a banner line
 * `CODE — message` (and the failing field codes appended, so `reason_codes: REQUIRED` is visible even
 * when the field has no inline slot).
 */
import { ApiError } from '../api/client';
import { isFieldErrorDetails } from '../types/api';

export interface ApiIssues {
  /** 422 `details[].field` → `details[].code`, e.g. `{"kyc.pan": "INVALID_FORMAT"}`. */
  readonly fields: Readonly<Record<string, string>>;
  readonly code: string;
  readonly message: string;
}

export function classifyError(error: unknown, fallback: string): ApiIssues {
  if (!(error instanceof ApiError)) {
    return { fields: {}, code: 'UNKNOWN_ERROR', message: fallback };
  }
  if (!isFieldErrorDetails(error.details)) {
    return { fields: {}, code: error.code, message: error.message };
  }
  const fields: Record<string, string> = {};
  for (const detail of error.details) fields[detail.field] = detail.code;
  const listed = error.details.map((detail) => `${detail.field}: ${detail.code}`).join(', ');
  return {
    fields,
    code: error.code,
    message: listed === '' ? error.message : `${error.message} (${listed})`,
  };
}

/** Single-line banner text: `422 VALIDATION_ERROR — …`. */
export function issueText(issues: ApiIssues): string {
  return `${issues.code} — ${issues.message}`;
}
