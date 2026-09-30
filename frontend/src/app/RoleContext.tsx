import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { ApiClient } from '../api/client';
import type { ActorRole, DemoUser } from '../types/roles';
import { DEMO_USERS, isActorRole } from '../types/roles';

export const ROLE_STORAGE_KEY = 'policyforge.demoRole';
const DEFAULT_ROLE: ActorRole = 'CUSTOMER';

export interface RoleContextValue {
  readonly role: ActorRole;
  readonly actorId: string;
  readonly user: DemoUser;
  readonly setRole: (role: ActorRole) => void;
  readonly api: ApiClient;
}

const RoleContext = createContext<RoleContextValue | null>(null);

function readStoredRole(): ActorRole {
  try {
    const stored = globalThis.localStorage?.getItem(ROLE_STORAGE_KEY);
    if (stored !== null && stored !== undefined && isActorRole(stored)) return stored;
  } catch {
    // localStorage can be unavailable (private mode / sandboxed iframe) — fall back to the default.
  }
  return DEFAULT_ROLE;
}

function writeStoredRole(role: ActorRole): void {
  try {
    globalThis.localStorage?.setItem(ROLE_STORAGE_KEY, role);
  } catch {
    // Persistence is a convenience; ignore storage failures.
  }
}

export function RoleProvider({ children }: { children: ReactNode }): JSX.Element {
  const [role, setRoleState] = useState<ActorRole>(readStoredRole);

  const setRole = useCallback((next: ActorRole): void => {
    setRoleState(next);
    writeStoredRole(next);
  }, []);

  // The client reads the role through a ref-like getter so a role switch needs no new instance.
  const roleRef = useMemo(() => ({ current: role }), [role]);
  roleRef.current = role;
  const api = useMemo(() => new ApiClient(() => roleRef.current), [roleRef]);

  const value = useMemo<RoleContextValue>(
    () => ({ role, actorId: DEMO_USERS[role].actorId, user: DEMO_USERS[role], setRole, api }),
    [role, setRole, api],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const value = useContext(RoleContext);
  if (value === null) throw new Error('useRole must be used inside a <RoleProvider>');
  return value;
}
