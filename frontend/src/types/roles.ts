/** Demo actor roles accepted by the auth stub (docs/conventions.md → API / auth stub). */
export const ACTOR_ROLES = ['CUSTOMER', 'UNDERWRITER', 'ADMIN'] as const;

export type ActorRole = (typeof ACTOR_ROLES)[number];

export interface DemoUser {
  readonly role: ActorRole;
  readonly actorId: string;
  /** Label shown in the header role switcher. */
  readonly label: string;
}

export const DEMO_USERS: Readonly<Record<ActorRole, DemoUser>> = {
  CUSTOMER: { role: 'CUSTOMER', actorId: 'cust-001', label: 'Customer (cust-001)' },
  UNDERWRITER: { role: 'UNDERWRITER', actorId: 'uw-001', label: 'Underwriter (uw-001)' },
  ADMIN: { role: 'ADMIN', actorId: 'admin-001', label: 'Admin (admin-001)' },
};

export function isActorRole(value: string): value is ActorRole {
  return (ACTOR_ROLES as readonly string[]).includes(value);
}
