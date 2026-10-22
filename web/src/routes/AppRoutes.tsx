import { Suspense, type ReactNode } from 'react';
import { Route, Routes } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequirePermission } from '../access/RequirePermission';
import { LoadingState } from '../components/feedback/LoadingState';
import { AppShell } from '../layout/AppShell';
import { NOTIFICATION_READ, ROUTES } from '../navigation/routes';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { HomeRedirect } from '../pages/HomeRedirect';
import { MyAccessPage } from '../pages/MyAccessPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlatformDashboardPage } from '../pages/platform/dashboard/PlatformDashboardPage';
import { InvoicesPage } from '../pages/platform/invoices/InvoicesPage';
import { PaymentsPage } from '../pages/platform/payments/PaymentsPage';
import { TenantDetailPage } from '../pages/platform/tenantDetail/TenantDetailPage';
import { TenantsPage } from '../pages/platform/tenants/TenantsPage';
import { SystemStatusPage } from '../pages/SystemStatusPage';
import {
  AccessPage,
  CatalogPage,
  NotificationPreferencesPage,
  NotificationsPage,
  PlatformInvoiceDetailPage,
  PlatformSmsWalletsPage,
  SmsDeliveriesPage,
  TenantSmsWalletPage,
  AlertsPage,
  ApprovalsPage,
  ClientManagedServicePage,
  CustomerDetailPage,
  CustomersPage,
  ExpenseCategoriesPage,
  ExceptionsPage,
  CasesPage,
  CaseDetailPage,
  InsightsPage,
  ModelDetailPage,
  ModelsPage,
  ExpensesPage,
  FinancePage,
  FleetMapPage,
  GeofencesPage,
  HireInvoiceDetailPage,
  HireInvoicePrintPage,
  JobDetailPage,
  JobsPage,
  MachineDetailPage,
  MachinesPage,
  ManagedServicePage,
  PoliciesPage,
  ProfitabilityPage,
  StaffDetailPage,
  StaffPage,
  TelemetryCatalogPage,
  TenantSubscriptionPage,
  TrackerDetailPage,
  TrackersPage,
  DashboardPage,
  AuditLogPage,
} from './lazyPages';

const NOTIFICATION_MANAGE = [
  PERMISSIONS.tenantNotificationManage,
  PERMISSIONS.platformNotificationManage,
] as const;

/** Console-agnostic pages: the current console's code of either kind grants access. */
function guardAny(permissions: readonly string[], page: ReactNode) {
  return (
    <RequirePermission permission={[...permissions]} match="any">
      <Suspense fallback={<LoadingState label="Loading page" />}>{page}</Suspense>
    </RequirePermission>
  );
}

function guard(permission: string, page: ReactNode) {
  return (
    <RequirePermission permission={permission}>
      <Suspense fallback={<LoadingState label="Loading page" />}>{page}</Suspense>
    </RequirePermission>
  );
}

/**
 * Every feature route must be wrapped in RequirePermission (deny by default).
 * Exceptions: My access (the user's own /me data), 403 and 404.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomeRedirect />} />
        <Route path={ROUTES.myAccess} element={<MyAccessPage />} />
        <Route
          path={ROUTES.notifications}
          element={guardAny(NOTIFICATION_READ, <NotificationsPage />)}
        />
        <Route
          path={ROUTES.notificationPreferences}
          element={guardAny(NOTIFICATION_READ, <NotificationPreferencesPage />)}
        />
        <Route
          path={ROUTES.notificationDeliveries}
          element={guardAny(NOTIFICATION_MANAGE, <SmsDeliveriesPage />)}
        />
        <Route
          path={ROUTES.platformDashboard}
          element={guard(PERMISSIONS.platformDashboardRead, <PlatformDashboardPage />)}
        />
        <Route
          path={ROUTES.platformTenants}
          element={guard(PERMISSIONS.platformTenantRead, <TenantsPage />)}
        />
        <Route
          path={ROUTES.platformTenantDetail}
          element={guard(PERMISSIONS.platformTenantRead, <TenantDetailPage />)}
        />
        <Route
          path={ROUTES.platformInvoices}
          element={guard(PERMISSIONS.platformInvoiceRead, <InvoicesPage />)}
        />
        <Route
          path={ROUTES.platformInvoiceDetail}
          element={guard(PERMISSIONS.platformInvoiceRead, <PlatformInvoiceDetailPage />)}
        />
        <Route
          path={ROUTES.platformCatalog}
          element={guard(PERMISSIONS.platformCatalogRead, <CatalogPage />)}
        />
        <Route
          path={ROUTES.platformSmsWallets}
          element={guard(PERMISSIONS.platformSmsWalletRead, <PlatformSmsWalletsPage />)}
        />
        <Route
          path={ROUTES.tenantSmsWallet}
          element={guard(PERMISSIONS.tenantBillingRead, <TenantSmsWalletPage />)}
        />
        <Route
          path={ROUTES.platformPayments}
          element={guard(PERMISSIONS.platformPaymentRead, <PaymentsPage />)}
        />
        <Route
          path={ROUTES.platformManagedService}
          element={guard(PERMISSIONS.platformMandateRead, <ManagedServicePage />)}
        />
        <Route
          path={ROUTES.platformTelemetry}
          element={guard(PERMISSIONS.platformTrackerModelRead, <TelemetryCatalogPage />)}
        />
        <Route
          path={ROUTES.platformModels}
          element={guard(PERMISSIONS.platformMlRead, <ModelsPage />)}
        />
        <Route
          path={ROUTES.platformModelDetail}
          element={guard(PERMISSIONS.platformMlRead, <ModelDetailPage />)}
        />
        <Route
          path={ROUTES.systemStatus}
          element={guard(PERMISSIONS.platformSystemRead, <SystemStatusPage />)}
        />
        <Route
          path={ROUTES.platformAudit}
          element={guard(PERMISSIONS.platformAuditRead, <AuditLogPage scope="platform" />)}
        />
        <Route
          path={ROUTES.tenantDashboard}
          element={guard(PERMISSIONS.tenantFleetRead, <DashboardPage />)}
        />
        <Route
          path={ROUTES.tenantAudit}
          element={guard(PERMISSIONS.tenantAuditRead, <AuditLogPage scope="tenant" />)}
        />
        <Route
          path={ROUTES.tenantFleet}
          element={guard(PERMISSIONS.tenantFleetRead, <FleetMapPage />)}
        />
        <Route
          path={ROUTES.tenantMachines}
          element={guard(PERMISSIONS.tenantMachineRead, <MachinesPage />)}
        />
        <Route
          path={ROUTES.tenantMachineDetail}
          element={guard(PERMISSIONS.tenantMachineRead, <MachineDetailPage />)}
        />
        <Route
          path={ROUTES.tenantStaff}
          element={guard(PERMISSIONS.tenantStaffRead, <StaffPage />)}
        />
        <Route
          path={ROUTES.tenantStaffDetail}
          element={guard(PERMISSIONS.tenantStaffRead, <StaffDetailPage />)}
        />
        <Route
          path={ROUTES.tenantTrackers}
          element={guard(PERMISSIONS.tenantTrackerRead, <TrackersPage />)}
        />
        <Route
          path={ROUTES.tenantTrackerDetail}
          element={guard(PERMISSIONS.tenantTrackerRead, <TrackerDetailPage />)}
        />
        <Route
          path={ROUTES.tenantGeofences}
          element={guard(PERMISSIONS.tenantGeofenceRead, <GeofencesPage />)}
        />
        <Route
          path={ROUTES.tenantAlerts}
          element={guard(PERMISSIONS.tenantFleetRead, <AlertsPage />)}
        />
        <Route
          path={ROUTES.tenantPolicies}
          element={guard(PERMISSIONS.tenantPolicyRead, <PoliciesPage />)}
        />
        <Route
          path={ROUTES.tenantSubscription}
          element={guard(PERMISSIONS.tenantBillingRead, <TenantSubscriptionPage />)}
        />
        <Route
          path={ROUTES.tenantCustomers}
          element={guard(PERMISSIONS.tenantCustomerRead, <CustomersPage />)}
        />
        <Route
          path={ROUTES.tenantCustomerDetail}
          element={guard(PERMISSIONS.tenantCustomerRead, <CustomerDetailPage />)}
        />
        <Route
          path={ROUTES.tenantExpenses}
          element={guard(PERMISSIONS.tenantExpenseRead, <ExpensesPage />)}
        />
        <Route
          path={ROUTES.tenantExpenseCategories}
          element={guard(PERMISSIONS.tenantExpenseRead, <ExpenseCategoriesPage />)}
        />
        <Route
          path={ROUTES.tenantApprovals}
          element={guard(PERMISSIONS.tenantApprovalRead, <ApprovalsPage />)}
        />
        <Route
          path={ROUTES.tenantFinance}
          element={guard(PERMISSIONS.tenantFinanceRead, <FinancePage />)}
        />
        <Route
          path={ROUTES.tenantHireInvoiceDetail}
          element={guard(PERMISSIONS.tenantFinanceRead, <HireInvoiceDetailPage />)}
        />
        <Route
          path={ROUTES.tenantHireInvoicePrint}
          element={guard(PERMISSIONS.tenantFinanceRead, <HireInvoicePrintPage />)}
        />
        <Route
          path={ROUTES.tenantProfitability}
          element={guard(PERMISSIONS.tenantFinanceReport, <ProfitabilityPage />)}
        />
        <Route path={ROUTES.tenantJobs} element={guard(PERMISSIONS.tenantJobRead, <JobsPage />)} />
        <Route
          path={ROUTES.tenantJobDetail}
          element={guard(PERMISSIONS.tenantJobRead, <JobDetailPage />)}
        />
        <Route
          path={ROUTES.tenantExceptions}
          element={guard(PERMISSIONS.tenantMeterRead, <ExceptionsPage />)}
        />
        <Route
          path={ROUTES.tenantCases}
          element={guard(PERMISSIONS.tenantCaseRead, <CasesPage />)}
        />
        <Route
          path={ROUTES.tenantCaseDetail}
          element={guard(PERMISSIONS.tenantCaseRead, <CaseDetailPage />)}
        />
        <Route
          path={ROUTES.tenantInsights}
          element={guard(PERMISSIONS.tenantFleetRead, <InsightsPage />)}
        />
        <Route
          path={ROUTES.tenantAccess}
          element={guard(PERMISSIONS.tenantAccessRead, <AccessPage />)}
        />
        <Route
          path={ROUTES.tenantManagedService}
          element={guard(PERMISSIONS.tenantManagedServiceRead, <ClientManagedServicePage />)}
        />
        <Route path={ROUTES.forbidden} element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
