import { useRoutes } from 'react-router-dom';
import { RoleProvider } from './RoleContext';
import { routes } from './routes';

/** Router outlet; the surrounding <BrowserRouter>/<MemoryRouter> is supplied by the caller. */
export function AppRoutes(): JSX.Element | null {
  return useRoutes(routes);
}

export function App(): JSX.Element {
  return (
    <RoleProvider>
      <AppRoutes />
    </RoleProvider>
  );
}
