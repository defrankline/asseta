import { PERMISSIONS } from '../access/permissionCodes';

export const ROUTES = {
  home: '/',
  myAccess: '/me',
  platformDashboard: '/platform',
  platformTenants: '/platform/tenants',
  platformTenantDetail: '/platform/tenants/:tenantId',
  platformInvoices: '/platform/invoices',
  platformPayments: '/platform/payments',
  /** Matches the backend `platform.system` menu path. */
  systemStatus: '/platform/system',
  forbidden: '/403',
} as const;

export function tenantDetailPath(tenantId: string): string {
  return `${ROUTES.platformTenants}/${encodeURIComponent(tenantId)}`;
}

export interface NavItem {
  key: string;
  label: string;
  path: string;
}

interface StaticNavItem extends NavItem {
  /** Required permission in platform mode. */
  permission: string;
}

/** Platform-console items; tenant items come from the active tenant's /me menus. */
export const PLATFORM_NAV: readonly StaticNavItem[] = [
  {
    key: 'platform.system-status',
    label: 'System status',
    path: ROUTES.systemStatus,
    permission: PERMISSIONS.platformSystemRead,
  },
];

export const ACCOUNT_NAV: readonly NavItem[] = [
  { key: 'account.my-access', label: 'My access', path: ROUTES.myAccess },
];

/** Paths with a page in this build; used to avoid landing users on not-yet-built menu targets. */
export const IMPLEMENTED_PATHS: ReadonlySet<string> = new Set([
  ROUTES.myAccess,
  ROUTES.platformDashboard,
  ROUTES.platformTenants,
  ROUTES.platformInvoices,
  ROUTES.platformPayments,
  ROUTES.systemStatus,
]);
