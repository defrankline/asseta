import { PERMISSIONS } from '../access/permissionCodes';
import { HOURS_MENU_PATHS } from './hoursRoutes';
import { RECORD_LIST_ROUTES } from './recordRoutes';

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
  /** Matches the backend `platform.models` menu path (governed ML, ADR-007). */
  platformModels: '/platform/models',
  platformModelDetail: '/platform/models/:modelId',
  /** Matches the backend `platform.system` menu path. */
  systemStatus: '/platform/system',
  forbidden: '/403',
  /** The signed-in user's own notification inbox and preferences (no feature permission). */
  notifications: '/notifications',
  notificationPreferences: '/notifications/preferences',
  /** SMS delivery log of the current console (`*.notification.manage`). */
  notificationDeliveries: '/notifications/deliveries',
  /** Platform audit log (backend `platform.audit` menu). */
  platformAudit: '/platform/audit',
  // Tenant console paths match the backend tenant menu paths (`/me` tenant menus).
  /** Tenant landing page (backend `tenant.dashboard` menu, first item of the Overview group). */
  tenantDashboard: '/tenant/dashboard',
  /** Tenant audit log (backend `tenant.audit` menu). */
  tenantAudit: '/tenant/audit',
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
  /** Matches the backend `tenant.cash_custody` menu path (custody chain, remittances, reconciliation). */
  tenantCashCustody: '/tenant/finance/cash',
  /** Matches the backend `tenant.deposit_accounts` menu path (Finance group). */
  tenantDepositAccounts: '/tenant/finance/deposit-accounts',
  tenantDepositAccountDetail: '/tenant/finance/deposit-accounts/:accountId',
  /** Matches the backend `tenant.accountability` menu path (Overview group). */
  tenantAccountability: '/tenant/accountability',
  /** Matches the backend `tenant.security_events` menu path (Risk & review group). */
  tenantSecurityEvents: '/tenant/security-events',
  /** Matches the backend `tenant.sync_conflicts` menu path (Risk & review group). */
  tenantSyncConflicts: '/tenant/sync-conflicts',
  tenantSyncConflictDetail: '/tenant/sync-conflicts/:operationId',
  /** Matches the backend `tenant.profitability` menu path. */
  tenantProfitability: '/tenant/profitability',
  tenantJobs: '/tenant/jobs',
  tenantJobDetail: '/tenant/jobs/:jobId',
  tenantExceptions: '/tenant/exceptions',
  /** Matches the backend `tenant.meter_resets` menu path (company-wide reset approvals). */
  tenantMeterResets: '/tenant/meter-resets',
  // Engine hours (backend `tenant.engine_hours` group): baselines, reconciliation, explanations, corrections.
  tenantEngineHours: '/tenant/engine-hours',
  tenantEngineHoursMachine: '/tenant/engine-hours/machines/:machineId',
  tenantEngineHoursUnallocated: '/tenant/engine-hours/unallocated',
  tenantEngineHourClassifications: '/tenant/engine-hours/classifications',
  tenantMeterBaselines: '/tenant/meter-baselines',
  tenantMeterCorrections: '/tenant/meter-corrections',
  tenantEngineHourReasons: '/tenant/engine-hour-reasons',
  // Revenue checks (DEC-031; backend menus tenant.engine_hours.daily_sheet / .non_revenue, tenant.revenue_*).
  tenantDailySheet: '/tenant/engine-hours/daily-sheet',
  tenantDailySheetDay: '/tenant/engine-hours/daily-sheet/:machineId/:day',
  tenantRevenueDifferences: '/tenant/revenue-differences',
  tenantRevenueReasons: '/tenant/revenue-reasons',
  tenantNonRevenueApprovals: '/tenant/non-revenue-approvals',
  /** Matches the backend `tenant.cases` menu path ("Investigations"). */
  tenantCases: '/tenant/cases',
  tenantCaseDetail: '/tenant/cases/:caseId',
  /** Matches the backend `tenant.insights` menu path (Risk & review group). */
  tenantInsights: '/tenant/insights',
  tenantAccess: '/tenant/access',
  tenantManagedService: '/tenant/managed-service',
  /** The tenant's own SMS wallet (balance + ledger). */
  tenantSmsWallet: '/tenant/sms-wallet',
  // Field work (backend `tenant.field` group): the supervisor's own capture flows from a browser.
  fieldJobs: '/tenant/field/jobs',
  fieldJobDetail: '/tenant/field/jobs/:jobId',
  fieldReadings: '/tenant/field/readings',
  fieldFuel: '/tenant/field/fuel',
  fieldExpenses: '/tenant/field/expenses',
  fieldCash: '/tenant/field/cash',
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

/** Field work job workspace (readings, start/complete, work log, acknowledgement). */
export function fieldJobPath(jobId: string): string {
  return `${ROUTES.fieldJobs}/${encodeURIComponent(jobId)}`;
}

/** A machine's engine-hour ledger (intervals, segments, totals). */
export function engineHoursMachinePath(machineId: string): string {
  return `${ROUTES.tenantEngineHours}/machines/${encodeURIComponent(machineId)}`;
}

/** One machine-day of the daily machine sheet (readings, segments, jobs, money, fuel, flags). */
export function dailySheetDayPath(machineId: string, day: string): string {
  return `${ROUTES.tenantDailySheet}/${encodeURIComponent(machineId)}/${encodeURIComponent(day)}`;
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

/** Cash tabs that moved from the hire finance hub to the cash custody page (old links keep working). */
export const CASH_TABS_MOVED: ReadonlySet<string> = new Set([
  'supervisors',
  'custody',
  'handovers',
  'reconciliation',
]);

/** Hire finance hub on a given tab (`invoices`, `payments`); cash tabs open the cash custody page. */
export function financeTabPath(tab: string): string {
  if (CASH_TABS_MOVED.has(tab)) return cashTabPath(tab);
  return `${ROUTES.tenantFinance}?tab=${encodeURIComponent(tab)}`;
}

/**
 * Cash custody page on a tab (`supervisors`, `custody`, `transfers`, `floats`, `handovers`,
 * `variances`, `retentions`, `adjustments`, `reconciliation`, `reasons`) with optional filters.
 */
export function cashTabPath(
  tab: string,
  params: Readonly<Record<string, string | undefined>> = {},
): string {
  const q = new URLSearchParams({ tab });
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, v);
  return `${ROUTES.tenantCashCustody}?${q.toString()}`;
}

export function depositAccountDetailPath(accountId: string): string {
  return `${ROUTES.tenantDepositAccounts}/${encodeURIComponent(accountId)}`;
}

export function syncConflictDetailPath(operationId: string): string {
  return `${ROUTES.tenantSyncConflicts}/${encodeURIComponent(operationId)}`;
}

export function hireInvoiceDetailPath(invoiceId: string): string {
  return `${ROUTES.tenantFinance}/invoices/${encodeURIComponent(invoiceId)}`;
}

export function hireInvoicePrintPath(invoiceId: string): string {
  return `${hireInvoiceDetailPath(invoiceId)}/print`;
}

export function modelDetailPath(modelId: string): string {
  return `${ROUTES.platformModels}/${encodeURIComponent(modelId)}`;
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
  ROUTES.platformModels,
  ROUTES.systemStatus,
  ROUTES.platformAudit,
  ROUTES.tenantDashboard,
  ROUTES.tenantAudit,
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
  ROUTES.tenantCashCustody,
  ROUTES.tenantDepositAccounts,
  ROUTES.tenantAccountability,
  ROUTES.tenantSecurityEvents,
  ROUTES.tenantSyncConflicts,
  ROUTES.tenantProfitability,
  ROUTES.tenantJobs,
  ROUTES.tenantExceptions,
  ROUTES.tenantEngineHours,
  ROUTES.tenantEngineHoursUnallocated,
  ROUTES.tenantEngineHourClassifications,
  ROUTES.tenantMeterBaselines,
  ROUTES.tenantMeterCorrections,
  ROUTES.tenantEngineHourReasons,
  ROUTES.tenantDailySheet,
  ROUTES.tenantRevenueReasons,
  ROUTES.tenantCases,
  ROUTES.tenantInsights,
  ROUTES.tenantAccess,
  ROUTES.tenantManagedService,
  ROUTES.fieldJobs,
  ROUTES.fieldReadings,
  ROUTES.fieldFuel,
  ROUTES.fieldExpenses,
  ROUTES.fieldCash,
  ...HOURS_MENU_PATHS,
  // Exact-record list routes (cash ones open the cash custody page on that list).
  ...Object.values(RECORD_LIST_ROUTES),
]);
