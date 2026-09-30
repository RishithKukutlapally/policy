/**
 * Reads the endorsement types a policy may use (story E6-S3, AC-16).
 *
 * The list comes from the policy's **own** rule version, not the product's active one: an in-force
 * policy is endorsed under the rules it was written against (§2.19). The catalog call is advisory — the
 * server re-validates `type` and answers 422 `NOT_ALLOWED` — so a failure falls back to offering every
 * type rather than blocking the form.
 */
import { useEffect, useState } from 'react';
import { listVersions } from '../../api/catalog';
import { useRole } from '../../app/RoleContext';
import { toEndorsementTypes } from '../../types/endorsements';
import type { EndorsementType, PolicyDetail } from '../../types/policies';

export const ALL_ENDORSEMENT_TYPES: readonly EndorsementType[] = [
  'CHANGE_ADDRESS',
  'ADD_NOMINEE',
  'CHANGE_SUM_INSURED',
];

export interface AllowedTypesState {
  readonly types: readonly EndorsementType[];
  /** False until the rule file has been read, so the selector never flashes a disallowed option. */
  readonly ready: boolean;
}

export function useAllowedTypes(policy: PolicyDetail | null): AllowedTypesState {
  const { api } = useRole();
  const [state, setState] = useState<AllowedTypesState>({
    types: ALL_ENDORSEMENT_TYPES,
    ready: false,
  });

  useEffect(() => {
    if (policy === null) return;
    let cancelled = false;
    void (async (): Promise<void> => {
      try {
        const versions = await listVersions(api, policy.product);
        const own = versions.find((version) => version.version === policy.rule_version);
        const types = own?.rules?.endorsement.allowed_types;
        if (cancelled) return;
        setState({
          types: types === undefined ? ALL_ENDORSEMENT_TYPES : toEndorsementTypes(types),
          ready: true,
        });
      } catch {
        if (!cancelled) setState({ types: ALL_ENDORSEMENT_TYPES, ready: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, policy]);

  return state;
}
