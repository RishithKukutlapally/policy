/**
 * Summary tiles of the Portfolio dashboard (story E9-S2, contract §2.26, AC-20).
 *
 * The three product tiles carry server-side counts and the two money tiles carry server-side decimal
 * strings; nothing here is summed or divided (NFR-01).
 */
import { formatMoney } from '../../lib/money';
import { PRODUCT_NAMES } from '../../types/policies';
import { PRODUCT_ORDER } from '../../types/portfolio';
import type { PortfolioSnapshot } from '../../types/portfolio';

function Tile({
  label,
  value,
  testId,
  sub,
}: {
  readonly label: string;
  readonly value: string;
  readonly testId: string;
  readonly sub: string;
}): JSX.Element {
  return (
    <div className="lc-stat" data-testid={testId}>
      <p className="lbl">{label}</p>
      <p className="val">{value}</p>
      <p className="sub">{sub}</p>
    </div>
  );
}

export function PortfolioCards({
  snapshot,
  currency = 'INR',
}: {
  readonly snapshot: PortfolioSnapshot;
  readonly currency?: string;
}): JSX.Element {
  return (
    <div className="lc-cards" data-testid="portfolio-cards">
      <div className="portfolio-products" data-testid="portfolio-by-product">
        {PRODUCT_ORDER.map((product) => (
          <Tile
            key={product}
            label={PRODUCT_NAMES[product]}
            value={String(snapshot.active_by_product[product] ?? 0)}
            testId={`card-${product}`}
            sub="active policies"
          />
        ))}
      </div>
      <Tile
        label="Premium collected"
        value={formatMoney(snapshot.premium_collected, currency)}
        testId="card-premium-collected"
        sub="all premium payments"
      />
      <Tile
        label="Refunds paid"
        value={formatMoney(snapshot.refunds_paid, currency)}
        testId="card-refunds-paid"
        sub="all refunds"
      />
    </div>
  );
}
