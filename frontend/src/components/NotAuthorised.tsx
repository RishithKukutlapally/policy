/**
 * The panel a route shows when the selected demo user's role cannot open it.
 *
 * Authorisation is enforced by the API (403 `FORBIDDEN`, 404 for another customer's policy — NFR-04);
 * this screen only avoids sending a request that is certain to be rejected and never states whether the
 * underlying record exists.
 */
export interface NotAuthorisedProps {
  /** Roles the route does allow, shown so the demo user knows which one to pick. */
  readonly allowed: readonly string[];
}

export function NotAuthorised({ allowed }: NotAuthorisedProps): JSX.Element {
  return (
    <section className="panel" data-testid="not-authorised">
      <h1>Not authorised</h1>
      <p role="status">
        The selected demo user&rsquo;s role cannot open this screen. Switch the demo user in the header
        to {allowed.join(' or ')}.
      </p>
    </section>
  );
}
