/**
 * The 404 panel shared by the lifecycle screens.
 *
 * §2.18 returns the same 404 for an unknown policy number and for another customer's policy, so this
 * wording must stay neutral: it never confirms that the number exists (NFR-04).
 */
import { Link } from 'react-router-dom';

export function PolicyNotFound({ policyNumber }: { readonly policyNumber: string }): JSX.Element {
  return (
    <section className="panel" data-testid="policy-not-found">
      <h1>Policy not found</h1>
      <p role="status">
        Policy <code>{policyNumber}</code> was not found. Check the number on your documents — the list
        of your policies is on <Link to="/policies">My Policies</Link>.
      </p>
    </section>
  );
}
