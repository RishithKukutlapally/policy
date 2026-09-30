import type { ChangeEvent } from 'react';
import { useRole } from './RoleContext';
import { ACTOR_ROLES, DEMO_USERS, isActorRole } from '../types/roles';

/** Header control that selects one of the three demo users (story E1-S5 AC-2). */
export function RoleSwitcher(): JSX.Element {
  const { role, setRole } = useRole();

  function onChange(event: ChangeEvent<HTMLSelectElement>): void {
    const next = event.target.value;
    if (isActorRole(next)) setRole(next);
  }

  return (
    <div className="role">
      <label htmlFor="role-switcher">Demo user</label>
      <select id="role-switcher" data-testid="role-switcher" value={role} onChange={onChange}>
        {ACTOR_ROLES.map((value) => (
          <option key={value} value={value}>
            {DEMO_USERS[value].label}
          </option>
        ))}
      </select>
      <code className="hdrs" data-testid="actor-headers">
        {`X-Actor-Id: ${DEMO_USERS[role].actorId} · X-Actor-Role: ${role}`}
      </code>
    </div>
  );
}
