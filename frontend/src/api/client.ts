/**
 * Typed fetch wrapper for the PolicyForge API.
 *
 * Every request carries the auth-stub headers `X-Actor-Id` / `X-Actor-Role` for the selected demo
 * user plus a freshly generated `X-Correlation-ID` (AC-22). Non-2xx responses are parsed from the
 * canonical error envelope into a typed `ApiError`.
 *
 * This module never logs request or response bodies: they may carry Aadhaar, PAN or health
 * declarations (NFR-03).
 */
import type { ApiErrorCode, ApiErrorDetails, ApiErrorEnvelope } from '../types/api';
import type { ActorRole } from '../types/roles';
import { DEMO_USERS } from '../types/roles';

export const HEADER_ACTOR_ID = 'X-Actor-Id';
export const HEADER_ACTOR_ROLE = 'X-Actor-Role';
export const HEADER_CORRELATION_ID = 'X-Correlation-ID';

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly details: ApiErrorDetails;
  readonly status: number;
  readonly correlationId: string | null;

  constructor(params: {
    code: ApiErrorCode;
    message: string;
    details: ApiErrorDetails;
    status: number;
    correlationId?: string | null;
  }) {
    super(params.message);
    this.name = 'ApiError';
    this.code = params.code;
    this.details = params.details;
    this.status = params.status;
    this.correlationId = params.correlationId ?? null;
  }
}

const KNOWN_CODES: ReadonlySet<string> = new Set<ApiErrorCode>([
  'VALIDATION_ERROR',
  'UNAUTHENTICATED',
  'FORBIDDEN',
  'NOT_FOUND',
  'NO_PUBLISHED_VERSION',
  'VERSION_IMMUTABLE',
  'DRAFT_ALREADY_OPEN',
  'INVALID_POLICY_STATE',
  'INVALID_APPLICATION_STATE',
  'QUOTE_STALE',
  'PREMIUM_ALREADY_PAID',
  'OUTSIDE_RENEWAL_WINDOW',
  'INTERNAL_ERROR',
  'NETWORK_ERROR',
  'UNKNOWN_ERROR',
]);

function toErrorCode(raw: unknown): ApiErrorCode {
  return typeof raw === 'string' && KNOWN_CODES.has(raw) ? (raw as ApiErrorCode) : 'UNKNOWN_ERROR';
}

/** RFC 4122 v4 id; falls back to Math.random where `crypto.randomUUID` is unavailable. */
export function newCorrelationId(): string {
  const cryptoObj: Crypto | undefined = globalThis.crypto;
  if (cryptoObj !== undefined && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const rand = Math.floor(Math.random() * 16);
    const value = ch === 'x' ? rand : (rand & 0x3) | 0x8;
    return value.toString(16);
  });
}

export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  readonly body?: unknown;
  readonly query?: Readonly<Record<string, string | number | boolean | undefined>>;
  readonly signal?: AbortSignal;
}

function buildUrl(path: string, query: RequestOptions['query']): string {
  if (query === undefined) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const qs = params.toString();
  return qs === '' ? path : `${path}?${qs}`;
}

function isEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const inner = (value as { error: unknown }).error;
  return typeof inner === 'object' && inner !== null && 'code' in inner;
}

function toApiError(status: number, payload: unknown, correlationId: string | null): ApiError {
  if (isEnvelope(payload)) {
    const { code, message, details } = payload.error;
    return new ApiError({
      code: toErrorCode(code),
      message: typeof message === 'string' && message !== '' ? message : 'Request failed',
      details: details ?? null,
      status,
      correlationId,
    });
  }
  return new ApiError({
    code: 'UNKNOWN_ERROR',
    message: `Request failed with status ${status}`,
    details: null,
    status,
    correlationId,
  });
}

export class ApiClient {
  constructor(
    private readonly getRole: () => ActorRole,
    private readonly fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args),
    private readonly baseUrl: string = '',
  ) {}

  buildHeaders(correlationId: string = newCorrelationId()): Record<string, string> {
    const role = this.getRole();
    const user = DEMO_USERS[role];
    return {
      Accept: 'application/json',
      [HEADER_ACTOR_ID]: user.actorId,
      [HEADER_ACTOR_ROLE]: user.role,
      [HEADER_CORRELATION_ID]: correlationId,
    };
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const correlationId = newCorrelationId();
    const headers = this.buildHeaders(correlationId);
    const init: RequestInit = {
      method: options.method ?? 'GET',
      headers,
    };
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    if (options.signal !== undefined) init.signal = options.signal;

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${buildUrl(path, options.query)}`, init);
    } catch {
      // Deliberately not logging the cause: it can echo the request body.
      throw new ApiError({
        code: 'NETWORK_ERROR',
        message: 'The server could not be reached. Check that the API is running and retry.',
        details: null,
        status: 0,
        correlationId,
      });
    }

    const responseCorrelationId = response.headers?.get(HEADER_CORRELATION_ID) ?? correlationId;
    const payload = await this.readJson(response);

    if (!response.ok) throw toApiError(response.status, payload, responseCorrelationId);
    return payload as T;
  }

  get<T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  post<T>(path: string, body: unknown, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return this.request<T>(path, { ...options, method: 'POST', body });
  }

  put<T>(path: string, body: unknown, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return this.request<T>(path, { ...options, method: 'PUT', body });
  }

  private async readJson(response: Response): Promise<unknown> {
    if (response.status === 204) return null;
    try {
      return (await response.json()) as unknown;
    } catch {
      return null;
    }
  }
}

export function createApiClient(
  getRole: () => ActorRole,
  fetchImpl?: typeof fetch,
  baseUrl?: string,
): ApiClient {
  return new ApiClient(getRole, fetchImpl, baseUrl);
}
