import { render } from '@testing-library/react';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { NotificationProvider } from '../notifications/NotificationProvider';
import { SessionContext } from '../session/SessionContext';
import { makeMe, makeSession } from './fixtures';

interface Options {
  /** Platform permissions granted in platform mode. */
  permissions?: string[];
  route?: string;
}

/** Render inside date-picker, toast, router and a platform-mode session with the given permissions. */
export function renderWithProviders(
  ui: ReactNode,
  { permissions = [], route = '/' }: Options = {},
) {
  const session = makeSession(makeMe({ platform_permissions: permissions }), { kind: 'platform' });
  return render(
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <NotificationProvider>
        <SessionContext.Provider value={session}>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </SessionContext.Provider>
      </NotificationProvider>
    </LocalizationProvider>,
  );
}
