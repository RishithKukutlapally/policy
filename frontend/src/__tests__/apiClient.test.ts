import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, newCorrelationId } from '../api/client';
import type { ActorRole } from '../types/roles';
import type { ProductSummary } from '../types/api';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function jsonResponse(status: number, body: unknown, correlationId = 'c-1'): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Correlation-ID': correlationId },
  });
}

type FetchArgs = [input: string | URL | Request, init?: RequestInit];

function mockFetch(handler: () => Promise<Response>) {
  return vi.fn((..._args: FetchArgs) => handler());
}

type FetchMock = ReturnType<typeof mockFetch>;

function clientFor(role: ActorRole, impl: FetchMock): ApiClient {
  return new ApiClient(() => role, impl as unknown as typeof fetch);
}

function initOfCall(mock: FetchMock, index: number): RequestInit {
  const init = mock.mock.calls[index]?.[1];
  if (init === undefined) throw new Error(`fetch call ${index} had no init`);
  return init;
}

function headersOfCall(mock: FetchMock, index: number): Headers {
  return new Headers(initOfCall(mock, index).headers);
}

describe('ApiClient headers (AC-22)', () => {
  it('attaches the actor and correlation headers for the selected demo user', async () => {
    const products: ProductSummary[] = [
      { product: 'MOTOR', name: 'Motor', active_version: 1, currency: 'INR' },
    ];
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(200, products)));
    const client = clientFor('UNDERWRITER', fetchMock);

    const result = await client.get<ProductSummary[]>('/api/products');

    expect(result).toEqual(products);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const headers = headersOfCall(fetchMock, 0);
    expect(headers.get('X-Actor-Id')).toBe('uw-001');
    expect(headers.get('X-Actor-Role')).toBe('UNDERWRITER');
    expect(headers.get('X-Correlation-ID')).toMatch(UUID_RE);
  });

  it('uses the customer actor id and a fresh correlation id per request', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(200, [])));
    const client = clientFor('CUSTOMER', fetchMock);

    await client.get('/api/policies');
    await client.get('/api/policies');

    expect(headersOfCall(fetchMock, 0).get('X-Actor-Id')).toBe('cust-001');
    expect(headersOfCall(fetchMock, 0).get('X-Actor-Role')).toBe('CUSTOMER');
    expect(headersOfCall(fetchMock, 0).get('X-Correlation-ID')).not.toBe(
      headersOfCall(fetchMock, 1).get('X-Correlation-ID'),
    );
  });

  it('sends a JSON body with a content type for POST', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(200, { ok: true })));
    const client = clientFor('ADMIN', fetchMock);

    await client.post('/api/quotes', { product: 'MOTOR' });

    const init = initOfCall(fetchMock, 0);
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ product: 'MOTOR' }));
    expect(headersOfCall(fetchMock, 0).get('X-Actor-Id')).toBe('admin-001');
  });

  it('appends defined query parameters only', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(200, [])));
    const client = clientFor('ADMIN', fetchMock);

    await client.get('/api/underwriting/queue', { query: { status: 'DECLINED', page: undefined } });

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/underwriting/queue?status=DECLINED');
  });

  it('generates UUID-shaped correlation ids', () => {
    expect(newCorrelationId()).toMatch(UUID_RE);
  });
});

describe('ApiClient error mapping', () => {
  it('maps the canonical error envelope to a typed ApiError', async () => {
    const envelope = {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        details: [{ field: 'kyc.pan', code: 'INVALID_FORMAT' }],
      },
    };
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(422, envelope, 'corr-42')));
    const client = clientFor('CUSTOMER', fetchMock);

    const error = await client.get('/api/applications').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.code).toBe('VALIDATION_ERROR');
    expect(apiError.status).toBe(422);
    expect(apiError.message).toBe('Request validation failed');
    expect(apiError.details).toEqual([{ field: 'kyc.pan', code: 'INVALID_FORMAT' }]);
    expect(apiError.correlationId).toBe('corr-42');
  });

  it('maps an object-details envelope such as INVALID_POLICY_STATE', async () => {
    const envelope = {
      error: {
        code: 'INVALID_POLICY_STATE',
        message: 'Policy is CANCELLED',
        details: { current: 'CANCELLED', target: 'ENDORSED' },
      },
    };
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(409, envelope)));
    const client = clientFor('ADMIN', fetchMock);

    const error = (await client
      .post('/api/policies/MO-2026-000123/endorsements', {})
      .catch((e: unknown) => e)) as ApiError;

    expect(error.code).toBe('INVALID_POLICY_STATE');
    expect(error.details).toEqual({ current: 'CANCELLED', target: 'ENDORSED' });
  });

  it('falls back to UNKNOWN_ERROR for a non-envelope failure body', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(jsonResponse(502, 'bad gateway')));
    const client = clientFor('CUSTOMER', fetchMock);

    const error = (await client.get('/api/products').catch((e: unknown) => e)) as ApiError;

    expect(error.code).toBe('UNKNOWN_ERROR');
    expect(error.status).toBe(502);
    expect(error.details).toBeNull();
  });

  it('raises NETWORK_ERROR when the request cannot be sent', async () => {
    const fetchMock = mockFetch(() => Promise.reject(new TypeError('failed to fetch')));
    const client = clientFor('CUSTOMER', fetchMock);

    const error = (await client.get('/api/products').catch((e: unknown) => e)) as ApiError;

    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.status).toBe(0);
    expect(error.correlationId).toMatch(UUID_RE);
  });
});
