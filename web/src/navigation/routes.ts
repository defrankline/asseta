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
  // Tenant console paths match the backend tenant menu paths (`/me` tenant menus).
  tenantFleet: '/tenant/fleet',
  tenantMachines: '/tenant/machines',
  tenantMachineDetail: '/tenant/machines/:machineId',
  tenantStaff: '/tenant/staff',
  tenantTrackers: '/tenant/trackers',
  tenantGeofences: '/tenant/geofences',
  tenantAlerts: '/tenant/alerts',
  tenantPolicies: '/tenant/policies',
  tenantSubscription: '/tenant/subscription',
  tenantCustomers: '/tenant/customers',
  tenantJobs: '/tenant/jobs',
  tenantJobDetail: '/tenant/jobs/:jobId',
  tenantExceptions: '/tenant/exceptions',
} as const;

export function machineDetailPath(machineId: string): string {
  return `${ROUTES.tenantMachines}/${encodeURIComponent(machineId)}`;
}

export function jobDetailPath(jobId: string): string {
  return `${ROUTES.tenantJobs}/${encodeURIComponent(jobId)}`;
}

/** Exceptions page, optionally pre-filtered to one job. */
export function exceptionsPath(jobId?: string): string {
  return jobId === undefined
    ? ROUTES.tenantExceptions
    : `${ROUTES.tenantExceptions}?job_id=${encodeURIComponent(jobId)}`;
}

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
  ROUTES.tenantFleet,
  ROUTES.tenantMachines,
  ROUTES.tenantStaff,
  ROUTES.tenantTrackers,
  ROUTES.tenantGeofences,
  ROUTES.tenantAlerts,
  ROUTES.tenantPolicies,
  ROUTES.tenantSubscription,
  ROUTES.tenantCustomers,
  ROUTES.tenantJobs,
  ROUTES.tenantExceptions,
]);
