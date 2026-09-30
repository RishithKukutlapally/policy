/**
 * Typed calls for the quote endpoints (api-contracts.md §2.7–2.8).
 *
 * Request bodies are never logged: quote inputs sit next to KYC data in later stories (NFR-03).
 */
import type { ApiClient } from './client';
import type { QuoteRequest, QuoteResponse, StoredQuote } from '../types/quotes';

export function quotesPath(): string {
  return '/api/quotes';
}

export function quotePath(quoteId: string): string {
  return `${quotesPath()}/${encodeURIComponent(quoteId)}`;
}

/** §2.7 — quote a risk on the product's active PUBLISHED version. CUSTOMER only. */
export function createQuote(api: ApiClient, body: QuoteRequest): Promise<QuoteResponse> {
  return api.post<QuoteResponse>(quotesPath(), body);
}

/** §2.8 — re-read a stored quote with its inputs (404 `NOT_FOUND` for another customer's quote). */
export function getQuote(api: ApiClient, quoteId: string): Promise<StoredQuote> {
  return api.get<StoredQuote>(quotePath(quoteId));
}
