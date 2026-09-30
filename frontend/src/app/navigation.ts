import type { ActorRole } from '../types/roles';

export interface NavItem {
  readonly label: string;
  readonly to: string;
  /** Playwright hook; defaults to a slug derived from the route (see `navTestId`). */
  readonly testId?: string;
}

/** `/admin/portfolio` → `nav-admin-portfolio` (mockup convention). */
export function navTestId(item: NavItem): string {
  return item.testId ?? `nav-${item.to.replace(/\W+/g, '-').replace(/^-|-$/g, '')}`;
}

/** Role-based navigation (story E1-S5 AC-4). */
export const NAV_ITEMS: Readonly<Record<ActorRole, readonly NavItem[]>> = {
  CUSTOMER: [
    { label: 'Get a Quote', to: '/quote' },
    { label: 'My Policies', to: '/policies' },
  ],
  UNDERWRITER: [{ label: 'Workbench', to: '/underwriter/queue' }],
  ADMIN: [
    // Story E2-S4 pins this hook to `nav-catalog`.
    { label: 'Product Catalog', to: '/admin/catalog', testId: 'nav-catalog' },
    { label: 'Underwriting Review', to: '/admin/underwriting' },
    { label: 'Portfolio', to: '/admin/portfolio' },
    // Story E7-S4 — the admin-only end-of-day run (§2.25).
    { label: 'End of day', to: '/admin/end-of-day' },
  ],
};

export const ROLE_CAPTION: Readonly<Record<ActorRole, string>> = {
  CUSTOMER: 'Customer',
  UNDERWRITER: 'Underwriter',
  ADMIN: 'Admin',
};

export function navItemsFor(role: ActorRole): readonly NavItem[] {
  return NAV_ITEMS[role];
}
