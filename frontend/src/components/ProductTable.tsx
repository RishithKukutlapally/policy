/**
 * The three products (api-contracts.md §2.2) with their active version and currency.
 *
 * Wide: a table. Narrow (< 768 px): stacked cards — same row test ids (AC-24).
 */
import type { ProductCode, ProductSummary } from '../types/catalog';

export interface ProductTableProps {
  readonly products: readonly ProductSummary[];
  readonly expanded: ProductCode | null;
  readonly isNarrow: boolean;
  readonly onToggle: (product: ProductCode) => void;
}

function activeLabel(product: ProductSummary): string {
  return product.active_version === null ? 'None' : `v${product.active_version}`;
}

interface ToggleProps {
  readonly product: ProductSummary;
  readonly expanded: boolean;
  readonly onToggle: (product: ProductCode) => void;
}

function ToggleButton({ product, expanded, onToggle }: ToggleProps): JSX.Element {
  return (
    <button
      type="button"
      className="btn btn-sm"
      aria-expanded={expanded}
      aria-controls="versions-panel"
      data-testid={`expand-${product.product}`}
      onClick={() => onToggle(product.product)}
    >
      {expanded ? 'Hide versions' : 'Show versions'}
    </button>
  );
}

export function ProductTable({ products, expanded, isNarrow, onToggle }: ProductTableProps): JSX.Element {
  if (isNarrow) {
    return (
      <ul className="card-list" data-testid="product-cards" aria-label="Products">
        {products.map((product) => (
          <li className="card" key={product.product} data-testid={`product-row-${product.product}`}>
            <p className="card-title">
              <strong>{product.name}</strong> <code className="mono small">{product.product}</code>
            </p>
            <dl className="kv">
              <dt>Active version</dt>
              <dd>{activeLabel(product)}</dd>
              <dt>Currency</dt>
              <dd>{product.currency}</dd>
            </dl>
            <ToggleButton
              product={product}
              expanded={expanded === product.product}
              onToggle={onToggle}
            />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="table-wrap">
      <table className="rtable" data-testid="product-table">
        <caption className="sr-only">Products and their active rule-set version</caption>
        <thead>
          <tr>
            <th scope="col">Product</th>
            <th scope="col">Code</th>
            <th scope="col">Active version</th>
            <th scope="col">Currency</th>
            <th scope="col">Versions</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => (
            <tr key={product.product} data-testid={`product-row-${product.product}`}>
              <th scope="row" data-label="Product">
                {product.name}
              </th>
              <td data-label="Code">
                <code className="mono small">{product.product}</code>
              </td>
              <td data-label="Active version">{activeLabel(product)}</td>
              <td data-label="Currency">{product.currency}</td>
              <td data-label="Versions" className="cell-actions">
                <ToggleButton
                  product={product}
                  expanded={expanded === product.product}
                  onToggle={onToggle}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
