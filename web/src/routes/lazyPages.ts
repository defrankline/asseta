import { lazy } from 'react';

/**
 * Tenant console pages are code-split so MapLibre and map-heavy views load on demand.
 * Each module keeps its named export; `lazy` needs a default, so we adapt here.
 */
export const FleetMapPage = lazy(() =>
  import('../pages/tenant/fleet/FleetMapPage').then((m) => ({ default: m.FleetMapPage })),
);
export const MachinesPage = lazy(() =>
  import('../pages/tenant/machines/MachinesPage').then((m) => ({ default: m.MachinesPage })),
);
export const MachineDetailPage = lazy(() =>
  import('../pages/tenant/machineDetail/MachineDetailPage').then((m) => ({
    default: m.MachineDetailPage,
  })),
);
export const StaffPage = lazy(() =>
  import('../pages/tenant/staff/StaffPage').then((m) => ({ default: m.StaffPage })),
);
export const TrackersPage = lazy(() =>
  import('../pages/tenant/trackers/TrackersPage').then((m) => ({ default: m.TrackersPage })),
);
export const TrackerDetailPage = lazy(() =>
  import('../pages/tenant/trackers/TrackerDetailPage').then((m) => ({
    default: m.TrackerDetailPage,
  })),
);
export const StaffDetailPage = lazy(() =>
  import('../pages/tenant/staff/StaffDetailPage').then((m) => ({ default: m.StaffDetailPage })),
);
export const CustomerDetailPage = lazy(() =>
  import('../pages/tenant/customers/CustomerDetailPage').then((m) => ({
    default: m.CustomerDetailPage,
  })),
);
export const ExpenseCategoriesPage = lazy(() =>
  import('../pages/tenant/expenses/ExpenseCategoriesPage').then((m) => ({
    default: m.ExpenseCategoriesPage,
  })),
);
export const TelemetryCatalogPage = lazy(() =>
  import('../pages/platform/telemetry/TelemetryCatalogPage').then((m) => ({
    default: m.TelemetryCatalogPage,
  })),
);
export const GeofencesPage = lazy(() =>
  import('../pages/tenant/geofences/GeofencesPage').then((m) => ({ default: m.GeofencesPage })),
);
export const AlertsPage = lazy(() =>
  import('../pages/tenant/alerts/AlertsPage').then((m) => ({ default: m.AlertsPage })),
);
export const PoliciesPage = lazy(() =>
  import('../pages/tenant/policies/PoliciesPage').then((m) => ({ default: m.PoliciesPage })),
);
export const TenantSubscriptionPage = lazy(() =>
  import('../pages/tenant/subscription/TenantSubscriptionPage').then((m) => ({
    default: m.TenantSubscriptionPage,
  })),
);
export const CustomersPage = lazy(() =>
  import('../pages/tenant/customers/CustomersPage').then((m) => ({ default: m.CustomersPage })),
);
export const JobsPage = lazy(() =>
  import('../pages/tenant/jobs/JobsPage').then((m) => ({ default: m.JobsPage })),
);
export const JobDetailPage = lazy(() =>
  import('../pages/tenant/jobDetail/JobDetailPage').then((m) => ({ default: m.JobDetailPage })),
);
export const ExceptionsPage = lazy(() =>
  import('../pages/tenant/exceptions/ExceptionsPage').then((m) => ({ default: m.ExceptionsPage })),
);
export const MeterResetsPage = lazy(() =>
  import('../pages/tenant/meterResets/MeterResetsPage').then((m) => ({
    default: m.MeterResetsPage,
  })),
);
export const EngineHoursMachinesPage = lazy(() =>
  import('../pages/tenant/engineHours/EngineHoursMachinesPage').then((m) => ({
    default: m.EngineHoursMachinesPage,
  })),
);
export const MachineEngineHoursPage = lazy(() =>
  import('../pages/tenant/engineHours/MachineEngineHoursPage').then((m) => ({
    default: m.MachineEngineHoursPage,
  })),
);
export const UnallocatedHoursPage = lazy(() =>
  import('../pages/tenant/engineHours/UnallocatedHoursPage').then((m) => ({
    default: m.UnallocatedHoursPage,
  })),
);
export const ClassificationsPage = lazy(() =>
  import('../pages/tenant/engineHours/ClassificationsPage').then((m) => ({
    default: m.ClassificationsPage,
  })),
);
export const MeterBaselinesPage = lazy(() =>
  import('../pages/tenant/engineHours/MeterBaselinesPage').then((m) => ({
    default: m.MeterBaselinesPage,
  })),
);
export const MeterCorrectionsPage = lazy(() =>
  import('../pages/tenant/engineHours/MeterCorrectionsPage').then((m) => ({
    default: m.MeterCorrectionsPage,
  })),
);
export const EngineHourReasonsPage = lazy(() =>
  import('../pages/tenant/engineHours/EngineHourReasonsPage').then((m) => ({
    default: m.EngineHourReasonsPage,
  })),
);
export const CasesPage = lazy(() =>
  import('../pages/tenant/cases/CasesPage').then((m) => ({ default: m.CasesPage })),
);
export const CaseDetailPage = lazy(() =>
  import('../pages/tenant/cases/CaseDetailPage').then((m) => ({ default: m.CaseDetailPage })),
);
export const InsightsPage = lazy(() =>
  import('../pages/tenant/insights/InsightsPage').then((m) => ({ default: m.InsightsPage })),
);
export const ModelsPage = lazy(() =>
  import('../pages/platform/models/ModelsPage').then((m) => ({ default: m.ModelsPage })),
);
export const ModelDetailPage = lazy(() =>
  import('../pages/platform/models/ModelDetailPage').then((m) => ({
    default: m.ModelDetailPage,
  })),
);
export const AccessPage = lazy(() =>
  import('../pages/tenant/access/AccessPage').then((m) => ({ default: m.AccessPage })),
);
export const ClientManagedServicePage = lazy(() =>
  import('../pages/tenant/managedService/ClientManagedServicePage').then((m) => ({
    default: m.ClientManagedServicePage,
  })),
);
export const ManagedServicePage = lazy(() =>
  import('../pages/platform/managedService/ManagedServicePage').then((m) => ({
    default: m.ManagedServicePage,
  })),
);
export const ExpensesPage = lazy(() =>
  import('../pages/tenant/expenses/ExpensesPage').then((m) => ({ default: m.ExpensesPage })),
);
export const ApprovalsPage = lazy(() =>
  import('../pages/tenant/approvals/ApprovalsPage').then((m) => ({ default: m.ApprovalsPage })),
);
export const FinancePage = lazy(() =>
  import('../pages/tenant/finance/FinancePage').then((m) => ({ default: m.FinancePage })),
);
export const HireInvoiceDetailPage = lazy(() =>
  import('../pages/tenant/finance/invoices/HireInvoiceDetailPage').then((m) => ({
    default: m.HireInvoiceDetailPage,
  })),
);
export const HireInvoicePrintPage = lazy(() =>
  import('../pages/tenant/finance/invoices/HireInvoicePrintPage').then((m) => ({
    default: m.HireInvoicePrintPage,
  })),
);
export const ProfitabilityPage = lazy(() =>
  import('../pages/tenant/profitability/ProfitabilityPage').then((m) => ({
    default: m.ProfitabilityPage,
  })),
);

// ---- DEC-022: notifications and platform invoicing ----
export const NotificationsPage = lazy(() =>
  import('../pages/notifications/NotificationsPage').then((m) => ({
    default: m.NotificationsPage,
  })),
);
export const NotificationPreferencesPage = lazy(() =>
  import('../pages/notifications/NotificationPreferencesPage').then((m) => ({
    default: m.NotificationPreferencesPage,
  })),
);
export const CatalogPage = lazy(() =>
  import('../pages/platform/catalog/CatalogPage').then((m) => ({ default: m.CatalogPage })),
);
export const PlatformInvoiceDetailPage = lazy(() =>
  import('../pages/platform/invoiceDetail/PlatformInvoiceDetailPage').then((m) => ({
    default: m.PlatformInvoiceDetailPage,
  })),
);
export const PlatformSmsWalletsPage = lazy(() =>
  import('../pages/platform/smsWallet/SmsWalletPages').then((m) => ({
    default: m.PlatformSmsWalletsPage,
  })),
);
export const TenantSmsWalletPage = lazy(() =>
  import('../pages/platform/smsWallet/SmsWalletPages').then((m) => ({
    default: m.TenantSmsWalletPage,
  })),
);
export const SmsDeliveriesPage = lazy(() =>
  import('../pages/notifications/SmsDeliveriesPage').then((m) => ({
    default: m.SmsDeliveriesPage,
  })),
);
export const DashboardPage = lazy(() =>
  import('../pages/tenant/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
export const AccountabilityPage = lazy(() =>
  import('../pages/tenant/accountability/AccountabilityPage').then((m) => ({
    default: m.AccountabilityPage,
  })),
);
export const SecurityEventsPage = lazy(() =>
  import('../pages/tenant/accountability/SecurityEventsPage').then((m) => ({
    default: m.SecurityEventsPage,
  })),
);
export const SyncConflictsPage = lazy(() =>
  import('../pages/tenant/accountability/SyncConflictsPage').then((m) => ({
    default: m.SyncConflictsPage,
  })),
);
export const SyncConflictDetailPage = lazy(() =>
  import('../pages/tenant/accountability/SyncConflictsPage').then((m) => ({
    default: m.SyncConflictDetailPage,
  })),
);
export const CashCustodyPage = lazy(() =>
  import('../pages/tenant/finance/cash/CashCustodyPage').then((m) => ({
    default: m.CashCustodyPage,
  })),
);
export const AuditLogPage = lazy(() =>
  import('../pages/audit/AuditLogPage').then((m) => ({ default: m.AuditLogPage })),
);

// ---- Field work: the supervisor's capture flows from a browser ----
export const MyJobsPage = lazy(() =>
  import('../pages/tenant/field/MyJobsPage').then((m) => ({ default: m.MyJobsPage })),
);
export const FieldJobPage = lazy(() =>
  import('../pages/tenant/field/FieldJobPage').then((m) => ({ default: m.FieldJobPage })),
);
export const FieldReadingsPage = lazy(() =>
  import('../pages/tenant/field/FieldReadingsPage').then((m) => ({
    default: m.FieldReadingsPage,
  })),
);
export const FieldFuelPage = lazy(() =>
  import('../pages/tenant/field/FieldFuelPage').then((m) => ({ default: m.FieldFuelPage })),
);
export const FieldExpensesPage = lazy(() =>
  import('../pages/tenant/field/FieldExpensesPage').then((m) => ({
    default: m.FieldExpensesPage,
  })),
);
export const FieldCashPage = lazy(() =>
  import('../pages/tenant/field/FieldCashPage').then((m) => ({ default: m.FieldCashPage })),
);
