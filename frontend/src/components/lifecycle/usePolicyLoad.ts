/**
 * Loads one policy for a lifecycle screen (Endorse, Renew, Cancel).
 *
 * `GET /api/policies/{policy_number}` answers 404 both for an unknown number and for another
 * customer's policy (§2.18), so `notFound` covers either case and the caller must render the same
 * neutral panel for both — never a hint that the policy exists (AC-10 / NFR-04).
 */
import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import { getPolicy } from '../../api/policies';
import { useRole } from '../../app/RoleContext';
import { classifyError, issueText } from '../../lib/apiIssues';
import type { PolicyDetail } from '../../types/policies';

export interface PolicyLoadState {
  readonly policy: PolicyDetail | null;
  readonly loading: boolean;
  readonly notFound: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
}

export function usePolicyLoad(policyNumber: string, enabled: boolean): PolicyLoadState {
  const { api } = useRole();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (!enabled) return;
    setLoading(true);
    setNotFound(false);
    setError(null);
    try {
      setPolicy(await getPolicy(api, policyNumber));
    } catch (caught) {
      setPolicy(null);
      if (caught instanceof ApiError && caught.status === 404) setNotFound(true);
      else setError(issueText(classifyError(caught, 'The policy could not be loaded.')));
    } finally {
      setLoading(false);
    }
  }, [api, policyNumber, enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { policy, loading, notFound, error, reload };
}
