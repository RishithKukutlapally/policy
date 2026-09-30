/**
 * Loads the renewal quote and the current term for the Renew screen (story E7-S4, §2.18 + §2.20).
 *
 * Both requests are issued together and settled independently: the quote drives the screen, while the
 * current-term panel is informational, so a failure to read the policy must not hide a usable quote.
 * A 404 from either (unknown number or another customer's policy) is the shared not-found case.
 */
import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import { getPolicy } from '../../api/policies';
import { getRenewalQuote } from '../../api/renewal';
import { useRole } from '../../app/RoleContext';
import { classifyError, issueText } from '../../lib/apiIssues';
import type { PolicyDetail } from '../../types/policies';
import type { RenewalQuote } from '../../types/renewal';

export interface RenewalLoadState {
  readonly policy: PolicyDetail | null;
  readonly quote: RenewalQuote | null;
  readonly loading: boolean;
  readonly notFound: boolean;
  readonly error: string | null;
}

export function useRenewalLoad(policyNumber: string, enabled: boolean): RenewalLoadState {
  const { api } = useRole();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [quote, setQuote] = useState<RenewalQuote | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    if (!enabled) return;
    setLoading(true);
    setNotFound(false);
    setError(null);
    const [policyResult, quoteResult] = await Promise.allSettled([
      getPolicy(api, policyNumber),
      getRenewalQuote(api, policyNumber),
    ]);

    setPolicy(policyResult.status === 'fulfilled' ? policyResult.value : null);

    if (quoteResult.status === 'fulfilled') {
      setQuote(quoteResult.value);
    } else {
      setQuote(null);
      const reason: unknown = quoteResult.reason;
      if (reason instanceof ApiError && reason.status === 404) setNotFound(true);
      else setError(issueText(classifyError(reason, 'The renewal quote could not be loaded.')));
    }
    setLoading(false);
  }, [api, policyNumber, enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  return { policy, quote, loading, notFound, error };
}
