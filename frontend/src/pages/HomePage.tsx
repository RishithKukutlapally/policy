import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useRole } from '../app/RoleContext';
import { ROLE_CAPTION, navItemsFor } from '../app/navigation';
import { ApiError } from '../api/client';
import type { ProductSummary } from '../types/api';

type ProbeState =
  | { readonly kind: 'idle' }
  | { readonly kind: 'loading' }
  | { readonly kind: 'ok'; readonly count: number }
  | { readonly kind: 'error'; readonly code: string; readonly message: string };

/** Role-specific landing screen with shortcuts to the screens this demo user may open. */
export function HomePage(): JSX.Element {
  const { role, user, api } = useRole();
  const [probe, setProbe] = useState<ProbeState>({ kind: 'idle' });

  async function sendTestRequest(): Promise<void> {
    setProbe({ kind: 'loading' });
    try {
      const products = await api.get<ProductSummary[]>('/api/products');
      setProbe({ kind: 'ok', count: products.length });
    } catch (error) {
      if (error instanceof ApiError) {
        setProbe({ kind: 'error', code: error.code, message: error.message });
      } else {
        setProbe({ kind: 'error', code: 'UNKNOWN_ERROR', message: 'Unexpected client error.' });
      }
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Welcome, {ROLE_CAPTION[role]}</h1>
          <p className="route">Signed in as {user.label}</p>
        </div>
      </div>

      <section className="panel" aria-labelledby="shortcuts-h">
        <h2 id="shortcuts-h">Your screens</h2>
        <div className="tiles">
          {navItemsFor(role).map((item) => (
            <Link className="tile" key={item.to} to={item.to}>
              <strong>{item.label}</strong>
              <span className="small muted">{item.to}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="panel" aria-labelledby="client-h">
        <h2 id="client-h">API client</h2>
        <p className="small muted">
          Every request attaches <code>X-Actor-Id</code>, <code>X-Actor-Role</code> and a fresh{' '}
          <code>X-Correlation-ID</code>.
        </p>
        <button
          type="button"
          className="btn"
          data-testid="send-test-request"
          onClick={() => void sendTestRequest()}
        >
          Send test request (GET /api/products)
        </button>
        <p className="status" role="status" data-testid="probe-status">
          {probe.kind === 'idle' ? 'No request sent yet.' : null}
          {probe.kind === 'loading' ? 'Sending…' : null}
          {probe.kind === 'ok' ? `OK — ${probe.count} product(s) returned.` : null}
          {probe.kind === 'error' ? `Error ${probe.code} — ${probe.message}` : null}
        </p>
      </section>
    </>
  );
}
