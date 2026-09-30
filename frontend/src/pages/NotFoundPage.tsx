import { Link } from 'react-router-dom';

export function NotFoundPage(): JSX.Element {
  return (
    <section className="panel" data-testid="not-found">
      <h1>Page not found</h1>
      <p>There is no screen at this address. Use the navigation to continue.</p>
      <Link className="btn" to="/" data-testid="back-home">
        Back to home
      </Link>
    </section>
  );
}
