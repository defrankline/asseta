import { render } from '@testing-library/react';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { NotificationProvider } from '../notifications/NotificationProvider';
import { SessionContext } from '../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from './fixtures';

interface Options {
  /** Platform permissions granted in platform mode. */
  permissions?: string[];
  route?: string;
  /** When set, renders in tenant mode (TENANT_A, FULL access) with these tenant permissions. */
  tenantPermissions?: string[];
  /** Tenant access state in tenant mode (default FULL). */
  accessState?: 'FULL' | 'READ_ONLY' | 'BLOCKED';
}

/**
 * Render inside date-picker, toast, router and a session: platform mode with `permissions`, or
 * tenant mode when `tenantPermissions` is given.
 */
export function renderWithProviders(
  ui: ReactNode,
  { permissions = [], route = '/', tenantPermissions, accessState = 'FULL' }: Options = {},
) {
  const base = makeMe({ platform_permissions: permissions });
  const session =
    tenantPermissions === undefined
      ? makeSession(base, { kind: 'platform' })
      : makeSession(
          {
            ...base,
            tenants: base.tenants.map((t) => ({
              ...t,
              permissions: tenantPermissions,
              access_state: accessState,
            })),
          },
          { kind: 'tenant', tenantId: TENANT_A },
        );
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
