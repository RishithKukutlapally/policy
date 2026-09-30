/**
 * Rule-set versions of one product (api-contracts.md §2.3).
 *
 * Wide: a table. Narrow (< 768 px): stacked cards — same rows, same test ids (AC-24).
 * "Publish" and "Edit draft" appear only on DRAFT rows; PUBLISHED versions are immutable.
 */
import { StatusBadge } from './StatusBadge';
import { formatMoney } from '../lib/money';
import type { CatalogVersion, ProductCode } from '../types/catalog';

export interface VersionTableProps {
  readonly product: ProductCode;
  readonly currency: string;
  readonly versions: readonly CatalogVersion[];
  readonly isNarrow: boolean;
  readonly onPublish: (version: CatalogVersion) => void;
  readonly onEditDraft: (version: CatalogVersion) => void;
}

function minPremiumOf(version: CatalogVersion, currency: string): string {
  const raw = version.rules?.premium.minimum_premium;
  return raw === undefined ? '—' : formatMoney(raw, currency);
}

interface RowContentProps extends Pick<VersionTableProps, 'product' | 'onPublish' | 'onEditDraft'> {
  readonly version: CatalogVersion;
  readonly currency: string;
}

function Badges({ version }: { readonly version: CatalogVersion }): JSX.Element {
  return (
    <span className="row">
      <StatusBadge status={version.status} />
      {version.is_active ? <StatusBadge status="Active" /> : null}
    </span>
  );
}

function Actions({ product, version, onPublish, onEditDraft }: RowContentProps): JSX.Element {
  if (version.status !== 'DRAFT') {
    return <span className="small muted">No actions — published versions are immutable</span>;
  }
  return (
    <span className="row">
      <button
        type="button"
        className="btn btn-primary btn-sm"
        aria-label={`Publish ${product} v${version.version}`}
        data-testid={`publish-v${version.version}`}
        onClick={() => onPublish(version)}
      >
        Publish
      </button>
      <button
        type="button"
        className="btn btn-sm"
        aria-label={`Edit draft ${product} v${version.version}`}
        data-testid={`edit-draft-v${version.version}`}
        onClick={() => onEditDraft(version)}
      >
        Edit draft
      </button>
    </span>
  );
}

export function VersionTable(props: VersionTableProps): JSX.Element {
  const { product, currency, versions, isNarrow } = props;
  const ordered = [...versions].sort((a, b) => b.version - a.version);

  if (ordered.length === 0) {
    return (
      <p className="empty" data-testid="versions-empty">
        No rule-set versions yet for {product}.
      </p>
    );
  }

  if (isNarrow) {
    return (
      <ul className="card-list" data-testid="versions-cards" aria-label={`${product} versions`}>
        {ordered.map((version) => (
          <li className="card" key={version.version} data-testid={`version-row-${version.version}`}>
            <p className="card-title">
              <strong>v{version.version}</strong> <Badges version={version} />
            </p>
            <dl className="kv">
              <dt>Effective from</dt>
              <dd>{version.effective_from}</dd>
              <dt>Minimum premium</dt>
              <dd data-testid={`min-premium-${version.version}`}>{minPremiumOf(version, currency)}</dd>
            </dl>
            <Actions
              product={product}
              version={version}
              currency={currency}
              onPublish={props.onPublish}
              onEditDraft={props.onEditDraft}
            />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="versions-table">
        <caption className="sr-only">{product} rule-set versions</caption>
        <thead>
          <tr>
            <th scope="col">Version</th>
            <th scope="col">Status</th>
            <th scope="col">Effective from</th>
            <th scope="col">Minimum premium</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((version) => (
            <tr key={version.version} data-testid={`version-row-${version.version}`}>
              <td data-label="Version">
                <strong>v{version.version}</strong>
              </td>
              <td data-label="Status">
                <Badges version={version} />
              </td>
              <td data-label="Effective from">{version.effective_from}</td>
              <td data-label="Minimum premium" data-testid={`min-premium-${version.version}`}>
                {minPremiumOf(version, currency)}
              </td>
              <td data-label="Actions" className="cell-actions">
                <Actions
              product={product}
              version={version}
              currency={currency}
              onPublish={props.onPublish}
              onEditDraft={props.onEditDraft}
            />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
