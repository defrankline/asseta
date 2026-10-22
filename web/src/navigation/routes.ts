import { PERMISSIONS } from '../access/permissionCodes';

export const ROUTES = {
  home: '/',
  myAccess: '/me',
  platformDashboard: '/platform',
  platformTenants: '/platform/tenants',
  platformTenantDetail: '/platform/tenants/:tenantId',
  platformInvoices: '/platform/invoices',
  /** Platform invoice with per-line payment / fulfilment (DEC-022). */
  platformInvoiceDetail: '/platform/invoices/:invoiceId',
  /** Product catalog: subscription fees, SMS bundles, services (DEC-022). */
  platformCatalog: '/platform/catalog',
  /** Tenant SMS wallets (balance + ledger) for platform staff. */
  platformSmsWallets: '/platform/sms-wallets',
  platformPayments: '/platform/payments',
  platformManagedService: '/platform/managed-service',
  /** Approved tracker models and telemetry gateways (platform catalog). */
  platformTelemetry: '/platform/telemetry',
  /** Matches the backend `platform.system` menu path. */
  systemStatus: '/platform/system',
  forbidden: '/403',
  /** The signed-in user's own notification inbox and preferences (no feature permission). */
  notifications: '/notifications',
  notificationPreferences: '/notifications/preferences',
  /** SMS delivery log of the current console (`*.notification.manage`). */
  notificationDeliveries: '/notifications/deliveries',
  // Tenant console paths match the backend tenant menu paths (`/me` tenant menus).
  tenantFleet: '/tenant/fleet',
  tenantMachines: '/tenant/machines',
  tenantMachineDetail: '/tenant/machines/:machineId',
  tenantStaff: '/tenant/staff',
  tenantStaffDetail: '/tenant/staff/:staffId',
  tenantTrackers: '/tenant/trackers',
  tenantTrackerDetail: '/tenant/trackers/:trackerId',
  tenantGeofences: '/tenant/geofences',
  tenantAlerts: '/tenant/alerts',
  tenantPolicies: '/tenant/policies',
  tenantSubscription: '/tenant/subscription',
  tenantCustomers: '/tenant/customers',
  tenantCustomerDetail: '/tenant/customers/:customerId',
  /** Matches the backend `tenant.expenses` menu path; expense categories live here. */
  tenantExpenses: '/tenant/expenses',
  /** Expense categories (linked from Expenses & fuel). */
  tenantExpenseCategories: '/tenant/expenses/categories',
  /** Matches the backend `tenant.approvals` menu path. */
  tenantApprovals: '/tenant/approvals',
  /** Matches the backend `tenant.finance` menu path (invoices, payments, cash custody). */
  tenantFinance: '/tenant/finance',
  tenantHireInvoiceDetail: '/tenant/finance/invoices/:invoiceId',
  tenantHireInvoicePrint: '/tenant/finance/invoices/:invoiceId/print',
  /** Matches the backend `tenant.profitability` menu path. */
  tenantProfitability: '/tenant/profitability',
  tenantJobs: '/tenant/jobs',
  tenantJobDetail: '/tenant/jobs/:jobId',
  tenantExceptions: '/tenant/exceptions',
  /** Matches the backend `tenant.cases` menu path ("Investigations"). */
  tenantCases: '/tenant/cases',
  tenantCaseDetail: '/tenant/cases/:caseId',
  tenantAccess: '/tenant/access',
  tenantManagedService: '/tenant/managed-service',
  /** The tenant's own SMS wallet (balance + ledger). */
  tenantSmsWallet: '/tenant/sms-wallet',
} as const;

export function platformInvoiceDetailPath(invoiceId: string): string {
  return `${ROUTES.platformInvoices}/${encodeURIComponent(invoiceId)}`;
}

export function machineDetailPath(machineId: string): string {
  return `${ROUTES.tenantMachines}/${encodeURIComponent(machineId)}`;
}

export function trackerDetailPath(trackerId: string): string {
  return `${ROUTES.tenantTrackers}/${encodeURIComponent(trackerId)}`;
}

export function staffDetailPath(staffId: string): string {
  return `${ROUTES.tenantStaff}/${encodeURIComponent(staffId)}`;
}

export function customerDetailPath(customerId: string): string {
  return `${ROUTES.tenantCustomers}/${encodeURIComponent(customerId)}`;
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

export function caseDetailPath(caseId: string): string {
  return `${ROUTES.tenantCases}/${encodeURIComponent(caseId)}`;
}

/** Hire finance hub on a given tab (`invoices`, `payments`, `custody`, `handovers`, `reconciliation`). */
export function financeTabPath(tab: string): string {
  return `${ROUTES.tenantFinance}?tab=${encodeURIComponent(tab)}`;
}

export function hireInvoiceDetailPath(invoiceId: string): string {
  return `${ROUTES.tenantFinance}/invoices/${encodeURIComponent(invoiceId)}`;
}

export function hireInvoicePrintPath(invoiceId: string): string {
  return `${hireInvoiceDetailPath(invoiceId)}/print`;
}

export function tenantDetailPath(tenantId: string): string {
  return `${ROUTES.platformTenants}/${encodeURIComponent(tenantId)}`;
}

export interface NavItem {
  key: string;
  label: string;
  path: string;
}

/** A side-navigation section (parent) and its links (children), in display order. */
export interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
}

/** Gates the shared inbox pages; the inbox links themselves are server menus of each console. */
export const NOTIFICATION_READ = [
  PERMISSIONS.tenantNotificationRead,
  PERMISSIONS.platformNotificationRead,
] as const;

/** Self-service links every signed-in user has (no feature permission), outside the server catalog. */
export const ACCOUNT_NAV: readonly NavItem[] = [
  { key: 'account.my-access', label: 'My access', path: ROUTES.myAccess },
];

/** Group used for ACCOUNT_NAV when the console's Administration group has no visible server menu. */
export const ACCOUNT_GROUP = { label: 'Administration' } as const;

/** Paths with a page in this build; used to avoid landing users on not-yet-built menu targets. */
export const IMPLEMENTED_PATHS: ReadonlySet<string> = new Set([
  ROUTES.myAccess,
  ROUTES.notifications,
  ROUTES.notificationPreferences,
  ROUTES.notificationDeliveries,
  ROUTES.platformCatalog,
  ROUTES.platformSmsWallets,
  ROUTES.tenantSmsWallet,
  ROUTES.platformDashboard,
  ROUTES.platformTenants,
  ROUTES.platformInvoices,
  ROUTES.platformPayments,
  ROUTES.platformManagedService,
  ROUTES.platformTelemetry,
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
  ROUTES.tenantExpenses,
  ROUTES.tenantExpenseCategories,
  ROUTES.tenantApprovals,
  ROUTES.tenantFinance,
  ROUTES.tenantProfitability,
  ROUTES.tenantJobs,
  ROUTES.tenantExceptions,
  ROUTES.tenantCases,
  ROUTES.tenantAccess,
  ROUTES.tenantManagedService,
]);
