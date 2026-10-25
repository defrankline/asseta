import { render } from '@testing-library/react';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import type { MandateBadgeDto } from '../api/types';
import { NotificationProvider } from '../notifications/NotificationProvider';
import { SessionContext, type SessionContextValue } from '../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from './fixtures';

interface Options {
  /** Platform permissions granted in platform mode. */
  permissions?: string[];
  route?: string;
  /** When set, renders in tenant mode (TENANT_A, FULL access) with these tenant permissions. */
  tenantPermissions?: string[];
  /** Tenant access state in tenant mode (default FULL). */
  accessState?: 'FULL' | 'READ_ONLY' | 'BLOCKED';
  /** In tenant mode: the session acts under this managed-service mandate. */
  mandate?: MandateBadgeDto | null;
  /** In tenant mode: capabilities the tenant's policy switches off (`/me` disabled_capabilities). */
  disabledCapabilities?: string[];
  /** Overrides on the session value (e.g. a `reload` spy). */
  session?: Partial<SessionContextValue>;
}

/**
 * Render inside date-picker, toast, router and a session: platform mode with `permissions`, or
 * tenant mode when `tenantPermissions` is given.
 */
export function renderWithProviders(
  ui: ReactNode,
  {
    permissions = [],
    route = '/',
    tenantPermissions,
    accessState = 'FULL',
    mandate = null,
    disabledCapabilities = [],
    session: overrides = {},
  }: Options = {},
) {
  const base = makeMe({ platform_permissions: permissions });
  const built =
    tenantPermissions === undefined
      ? makeSession(base, { kind: 'platform' })
      : makeSession(
          {
            ...base,
            tenants: base.tenants.map((t) => ({
              ...t,
              permissions: tenantPermissions,
              access_state: accessState,
              mandate,
              disabled_capabilities: disabledCapabilities,
            })),
          },
          { kind: 'tenant', tenantId: TENANT_A },
        );
  const session = { ...built, ...overrides };
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
