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
