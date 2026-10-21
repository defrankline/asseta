import { Suspense, type ReactNode } from 'react';
import { Route, Routes } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequirePermission } from '../access/RequirePermission';
import { LoadingState } from '../components/feedback/LoadingState';
import { AppShell } from '../layout/AppShell';
import { ROUTES } from '../navigation/routes';
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
  AlertsPage,
  CustomersPage,
  ExceptionsPage,
  FleetMapPage,
  GeofencesPage,
  JobDetailPage,
  JobsPage,
  MachineDetailPage,
  MachinesPage,
  PoliciesPage,
  StaffPage,
  TenantSubscriptionPage,
  TrackersPage,
} from './lazyPages';

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
          path={ROUTES.platformPayments}
          element={guard(PERMISSIONS.platformPaymentRead, <PaymentsPage />)}
        />
        <Route
          path={ROUTES.systemStatus}
          element={guard(PERMISSIONS.platformSystemRead, <SystemStatusPage />)}
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
          path={ROUTES.tenantTrackers}
          element={guard(PERMISSIONS.tenantTrackerRead, <TrackersPage />)}
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
        <Route path={ROUTES.tenantJobs} element={guard(PERMISSIONS.tenantJobRead, <JobsPage />)} />
        <Route
          path={ROUTES.tenantJobDetail}
          element={guard(PERMISSIONS.tenantJobRead, <JobDetailPage />)}
        />
        <Route
          path={ROUTES.tenantExceptions}
          element={guard(PERMISSIONS.tenantMeterRead, <ExceptionsPage />)}
        />
        <Route path={ROUTES.forbidden} element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
