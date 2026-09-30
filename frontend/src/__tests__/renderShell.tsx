import { render } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../app/App';
import { RoleProvider } from '../app/RoleContext';

/** Renders the whole shell (provider + router + routes) at an initial route. */
export function renderShell(initialRoute = '/'): RenderResult {
  return render(
    <RoleProvider>
      <MemoryRouter initialEntries={[initialRoute]}>
        <AppRoutes />
      </MemoryRouter>
    </RoleProvider>,
  );
}
