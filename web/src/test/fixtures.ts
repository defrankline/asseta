import type { MeResponse } from '../api/types';
import { effectivePermissions, isGranted, type ConsoleMode } from '../session/permissions';
import type { SessionContextValue } from '../session/SessionContext';

export const TENANT_A = '11111111-1111-4111-8111-111111111111';
export const TENANT_B = '22222222-2222-4222-8222-222222222222';

export function makeMe(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    user_id: '33333333-3333-4333-8333-333333333333',
    email: 'ops@example.test',
    display_name: 'Ops User',
    platform_permissions: [],
    platform_menus: [],
    tenants: [
      {
        tenant_id: TENANT_A,
        name: 'Tenant A',
        status: 'ACTIVE',
        access_state: 'FULL',
        permissions: ['tenant.machine.read'],
        menus: [{ key: 'machines', label: 'Machines', path: '/machines', order: 1 }],
      },
    ],
    ...overrides,
  };
}

/** Build a SessionContext value the same way SessionProvider does, for component tests. */
export function makeSession(
  me: MeResponse | null,
  mode: ConsoleMode,
  status: SessionContextValue['status'] = 'ready',
): SessionContextValue {
  const permissions = effectivePermissions(me, mode);
  const activeTenant =
    mode.kind === 'tenant'
      ? (me?.tenants.find((t) => t.tenant_id === mode.tenantId) ?? null)
      : null;
  return {
    status,
    me,
    error: null,
    mode,
    activeTenant,
    permissions,
    canUsePlatform: (me?.platform_permissions.length ?? 0) > 0,
    isReadOnly: activeTenant?.access_state === 'READ_ONLY',
    setMode: () => Promise.resolve(),
    hasPermission: (required, match) => isGranted(permissions, required, match),
    reload: () => undefined,
  };
}
