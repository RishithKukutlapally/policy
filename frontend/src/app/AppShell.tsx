import { useCallback, useEffect, useState } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { RoleSwitcher } from './RoleSwitcher';
import { SideNav } from './SideNav';
import { useRole } from './RoleContext';
import { useIsNarrow } from './useIsNarrow';

/**
 * Application chrome: header (brand, nav toggle, role switcher), role-based side navigation and the
 * routed page. At >= 768 px the navigation is always visible; below it collapses behind the
 * "Open navigation" button (story E1-S5 AC-24).
 */
export function AppShell(): JSX.Element {
  const { role } = useRole();
  const isNarrow = useIsNarrow();
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (!isNarrow) setNavOpen(false);
  }, [isNarrow]);

  const closeNav = useCallback(() => setNavOpen(false), []);

  useEffect(() => {
    if (!navOpen) return;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setNavOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [navOpen]);

  const navHidden = isNarrow && !navOpen;

  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to main content
      </a>
      <header className="topbar">
        {isNarrow ? (
          <button
            type="button"
            className="menu-btn"
            data-testid="nav-toggle"
            aria-label="Open navigation"
            aria-controls="sidenav"
            aria-expanded={navOpen}
            onClick={() => setNavOpen((open) => !open)}
          >
            <span aria-hidden="true">☰</span>
            <span aria-hidden="true">Menu</span>
          </button>
        ) : null}
        <Link className="brand" to="/">
          PolicyForge <small>Horizon Insurance</small>
        </Link>
        <RoleSwitcher />
      </header>
      <div className="layout">
        <SideNav role={role} hidden={navHidden} floating={isNarrow} onNavigate={closeNav} />
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
