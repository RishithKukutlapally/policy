import { NavLink } from 'react-router-dom';
import { ROLE_CAPTION, navItemsFor, navTestId } from './navigation';
import type { ActorRole } from '../types/roles';

export interface SideNavProps {
  readonly role: ActorRole;
  readonly hidden: boolean;
  readonly floating: boolean;
  readonly onNavigate: () => void;
}

/** Role-based side navigation; below 768 px it floats over the page and is toggled (AC-24). */
export function SideNav({ role, hidden, floating, onNavigate }: SideNavProps): JSX.Element {
  const classes = ['sidenav'];
  if (floating) classes.push('sidenav--floating');

  return (
    <nav
      id="sidenav"
      className={classes.join(' ')}
      aria-label="Main navigation"
      data-testid="side-nav"
      hidden={hidden}
    >
      <p className="nav-caption">{ROLE_CAPTION[role]}</p>
      <ul>
        {navItemsFor(role).map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              onClick={onNavigate}
              data-testid={navTestId(item)}
              data-route={item.to}
              className={({ isActive }) => (isActive ? 'nav-link is-active' : 'nav-link')}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
