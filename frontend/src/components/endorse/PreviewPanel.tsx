/**
 * The premium-delta preview of the Endorse screen (story E6-S3, contract §2.19 `?preview=true`).
 *
 * `premium_delta` arrives as a signed decimal string already pro-rated for the unused part of the term;
 * this panel only splits off the sign for display (`formatSignedMoney`) and never recomputes the figure
 * (NFR-01, AC-16).
 */
import { formatMoney } from '../../lib/money';
import { formatSignedMoney } from '../policies/format';
import type { EndorsementPreview } from '../../types/endorsements';

export interface PreviewPanelProps {
  readonly preview: EndorsementPreview;
  readonly currentPremium: string;
  readonly currency: string;
}

export function PreviewPanel({
  preview,
  currentPremium,
  currency,
}: PreviewPanelProps): JSX.Element {
  const prorated =
    preview.unused_days === undefined || preview.term_days === undefined
      ? null
      : `${preview.unused_days} unused of ${preview.term_days} days`;

  return (
    <div className="lc-preview" aria-live="polite" data-testid="preview-result">
      <p className="small muted" style={{ margin: 0 }}>
        Premium change if submitted on {preview.endorsement_date}
      </p>
      <p className="lc-delta" data-testid="preview-delta">
        {formatSignedMoney(preview.premium_delta, currency)}
      </p>
      <dl className="kv small">
        <dt>New annual premium</dt>
        <dd className="num">{formatMoney(preview.new_premium, currency)}</dd>
        <dt>Current premium</dt>
        <dd className="num">{formatMoney(currentPremium, currency)}</dd>
        {prorated === null ? null : (
          <>
            <dt>Pro-rated for</dt>
            <dd>{prorated}</dd>
          </>
        )}
        <dt>Rule version</dt>
        <dd>v{preview.rule_version}</dd>
      </dl>
      <p className="small muted" style={{ margin: 0 }}>
        Preview only — nothing has been saved.
      </p>
    </div>
  );
}
